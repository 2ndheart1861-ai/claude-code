# -*- coding: utf-8 -*-
"""
의료광고 자동 검수기 (풋클리닉 블로그 원고용)

사용법
  1. input 폴더에 원고(.txt 또는 .md)를 넣는다.
  2. 이 폴더에서 `python checker.py` 실행
  3. output 폴더의 [검수완료]_파일명.md 리포트를 확인한다.

※ 이 도구는 사람이 검토하기 전에 한 번 거르는 '1차 스크리닝' 도구입니다.
  키워드/패턴 기반이라 놓치는 표현이나 과잉 적발이 있을 수 있으므로
  최종 판단은 담당자 검토와 의료광고 자율심의기구 심의로 하세요.
"""
import re
import sys
from datetime import date
from pathlib import Path

BASE = Path(__file__).resolve().parent
INPUT_DIR = BASE / "input"
OUTPUT_DIR = BASE / "output"

# ─────────────────────────────────────────────────────────────
# 1차 검수: 절대 금지어  (표시 이름, 정규식, 위반 사유, 수정 가이드)
#   규정이 바뀌면 이 목록에 한 줄씩 추가/수정하면 됩니다.
# ─────────────────────────────────────────────────────────────
FORBIDDEN = [
    ("완치", r"완치",
     "치료 효과를 단정·보장하는 표현 (의료법 제56조 제2항 제2·3호 소지)",
     "'증상 개선에 도움을 줄 수 있습니다'처럼 가능성 표현으로 바꾸세요."),
    ("100%", r"100\s*(%|％|퍼센트|프로)",
     "치료 효과·만족도를 수치로 단정하는 표현",
     "수치를 삭제하고 '개인에 따라 결과가 다를 수 있습니다'를 함께 표기하세요."),
    ("최초", r"최초",
     "객관적 근거 없는 배타적 표현 (제56조 제2항 제8호 소지)",
     "삭제하세요. 공인된 근거가 있다면 출처·기준일을 명시해야 합니다."),
    ("유일", r"유일",
     "객관적 근거 없는 배타적 표현 (제56조 제2항 제8호 소지)",
     "'OO 장비를 보유하고 있습니다'처럼 사실만 서술하세요."),
    ("최고", r"최고",
     "객관적 근거 없는 최상급 표현 (제56조 제2항 제8호 소지)",
     "'풍부한 진료 경험을 바탕으로'처럼 검증 가능한 사실 표현으로 바꾸세요."),
    ("부작용 없음", r"부작용\s*(이|은|도)?\s*(전혀\s*)?(없|제로|0\b)",
     "부작용 등 중요 정보를 누락·부정하는 표현 (제56조 제2항 제7호)",
     "'시술 후 일시적인 붓기·통증이 있을 수 있으며, 개인에 따라 차이가 있습니다'처럼 부작용을 안내하세요."),
    ("내돈내산", r"내\s*돈\s*내\s*산",
     "환자 치료경험담으로 오인되는 표현 (제56조 제2항 제2호)",
     "문장을 삭제하고 치료 과정·원리 중심의 정보성 문장으로 바꾸세요."),
    ("협찬 없음", r"협찬\s*(없|X|x|아님|아닙)|노\s*협찬",
     "환자 치료경험담으로 오인되는 표현 (제56조 제2항 제2호)",
     "문장을 삭제하세요. 병원이 작성한 글임을 분명히 하는 것이 안전합니다."),
    ("할인", r"할인",
     "가격 할인으로 환자를 유인하는 표현 (의료법 제27조 제3항 소지)",
     "할인·이벤트 문구를 삭제하고 진료 안내 중심으로 작성하세요."),
    ("무료", r"무료",
     "무료 제공으로 환자를 유인하는 표현 (의료법 제27조 제3항 소지)",
     "무료 진료·검사 문구를 삭제하세요. (단순 '무료 주차' 등 편의 안내는 담당자 판단)"),
    ("상품권", r"상품권|기프티콘",
     "금품 제공으로 환자를 유인하는 표현 (의료법 제27조 제3항)",
     "금품·경품 제공 문구를 삭제하세요."),
    ("수술 보장", r"(수술|시술|치료|효과|결과)\s*(을|를|이|가)?\s*보장",
     "치료 효과·결과를 보장하는 표현 (제56조 제2항 제3호 소지)",
     "'정확한 진단 후 적합한 치료 방법을 안내해 드립니다'로 바꾸세요."),
]

# ─────────────────────────────────────────────────────────────
# 1차 검수: 주의 필요 키워드  (키워드, 확인 포인트)
#   바로 위반은 아니지만, 쓰임새에 따라 문제가 될 수 있는 단어입니다.
# ─────────────────────────────────────────────────────────────
CAUTION = [
    ("전후", "치료 전후 사진·비교는 치료경험담으로 간주될 수 있습니다."),
    ("비교", "타 병원·타 치료법과의 우열 비교가 아닌지 확인하세요."),
    ("후기", "환자 후기 인용·링크는 치료경험담 광고에 해당할 수 있습니다."),
    ("임상", "임상 결과 인용 시 출처(논문·기관)를 명시해야 합니다."),
    ("특허", "특허는 효과를 인증하는 것이 아닙니다. 특허 번호·범위를 사실대로만 쓰세요."),
    ("보장", "효과·결과를 보장하는 뉘앙스가 아닌지 확인하세요."),
    ("추천", "환자 추천·권유 형태의 문장이 아닌지 확인하세요."),
    ("주사", "시술 효과만 쓰지 말고 부작용·주의사항을 함께 안내하세요."),
    ("시술", "시술 효과만 쓰지 말고 부작용·주의사항을 함께 안내하세요."),
    ("핀포인트", "장비명 사용 시 효과 과장·단정 표현이 없는지 확인하세요."),
    ("레이저", "레이저 치료 효과 단정 여부, 부작용 안내 여부를 확인하세요."),
    ("무지외반증", "질환 치료 효과를 단정하지 않았는지 확인하세요."),
    ("족저근막염", "질환 치료 효과를 단정하지 않았는지 확인하세요."),
    ("내성발톱", "질환 치료 효과를 단정하지 않았는지 확인하세요."),
    ("인솔", "인솔(의료기기 여부 포함)의 효능을 과장하지 않았는지 확인하세요."),
]

# ─────────────────────────────────────────────────────────────
# 2차 검수: 문맥 패턴  (분류명, [정규식들], 위반 사유, 수정 가이드)
# ─────────────────────────────────────────────────────────────
CONTEXT_RULES = [
    ("환자 경험담·후기 문체",
     [r"(했더니|받았더니|받고\s*나(서|니)|치료\s*받고|다녀왔더니).{0,25}(나았|좋아졌|사라졌|없어졌|편해졌|괜찮아졌)",
      r"(싹|씻은\s*듯|깨끗이|말끔히)\s*(나았|나아|사라|없어)",
      r"(나았어요|좋아졌어요|사라졌어요|추천해요|추천합니다|강추)",
      r"(원장님|선생님|실장님).{0,20}(친절|믿음|최고|꼼꼼하셔서|잘\s*해\s*주셔)",
      r"(저도|제가|저희\s*(엄마|아빠|어머니|아버지|남편|아내))\s*.{0,20}(치료|시술|받았|다녔)"],
     "환자의 주관적 치료경험담으로 오인될 수 있음 (제56조 제2항 제2호)",
     "개인 경험 대신 '1:1 맞춤 진료로 진행됩니다'처럼 진료 과정을 객관적으로 설명하세요."),
    ("타 병원 비교·비방",
     [r"(다른|타|여러|일반|동네)\s*(병원|의원|클리닉|정형외과|피부과|곳)",
      r"(보다|에\s*비해|대비).{0,15}(훨씬|덜|더\s*(좋|빠르|효과|정확|안전))",
      r"(엉터리|잘못된\s*치료|돈만\s*쓰|헛걸음)"],
     "다른 의료기관과 비교하거나 비방하는 표현 (제56조 제2항 제4·5호)",
     "비교 대상을 지우고 '당원에서는 ~한 방식으로 진료합니다'처럼 자체 설명만 남기세요."),
    ("부작용·통증 없음 강조",
     [r"(통증|흉터|재발|붓기|회복\s*기간|부작용).{0,6}(없|제로|걱정\s*(없|마))",
      r"(전혀|하나도|조금도).{0,8}(아프지|안\s*아|통증)",
      r"(무통|안전한\s*(시술|치료|수술)|안심하고\s*받)",
      r"(바로|즉시|당일)\s*(일상|출근|걸을|운동).{0,10}(가능|복귀)"],
     "위험·부작용 없이 장점만 강조하는 표현 (제56조 제2항 제7호 소지)",
     "'개인에 따라 통증·붓기가 있을 수 있으며, 시술 전 충분히 상담해 드립니다'를 함께 넣으세요."),
]

# 시술 관련 단어가 있는데 부작용·개인차 안내 문구가 전혀 없으면 문서 단위 경고
#   ('치료'는 면책 문구에도 흔히 쓰여 오탐이 많아 제외)
TREATMENT_WORDS = r"시술|주사|레이저|수술"
SIDE_EFFECT_NOTICE = (r"부작용|개인(에\s*따라|차|의\s*상태에\s*따라)|다를\s*수\s*있|차이가\s*있을\s*수"
                      r"|주의\s*사항|이상\s*반응")

SCORE_FORBIDDEN, SCORE_CONTEXT, SCORE_CAUTION, SCORE_NO_NOTICE = 10, 5, 1, 5


def read_text(path):
    for enc in ("utf-8-sig", "cp949"):  # 메모장 저장(ANSI) 원고까지 대응
        try:
            return path.read_text(encoding=enc)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="replace")


def split_sentences(text):
    """(줄번호, 문장) 목록으로 분리"""
    result = []
    for lineno, line in enumerate(text.splitlines(), 1):
        for s in re.split(r"(?<=[.!?。~])\s+", line.strip()):
            s = s.strip()
            if len(s) >= 2:
                result.append((lineno, s))
    return result


def highlight(sentence, spans):
    """적발 구간을 **굵게** 표시"""
    out, last = [], 0
    for start, end in sorted(set(spans)):
        if start < last:
            continue
        out.append(sentence[last:start] + "**" + sentence[start:end] + "**")
        last = end
    out.append(sentence[last:])
    return "".join(out)


def check(text):
    sentences = split_sentences(text)
    forbidden_hits, context_hits = [], []
    caution_hits = {}  # 키워드 -> [(줄, 문장)]

    for lineno, s in sentences:
        # 1차: 금지어
        forbidden_spans = []
        for name, pattern, reason, fix in FORBIDDEN:
            spans = [m.span() for m in re.finditer(pattern, s)]
            if spans:
                forbidden_spans += spans
                forbidden_hits.append(dict(line=lineno, sentence=highlight(s, spans),
                                           keyword=name, reason=reason, fix=fix))
        # 1차: 주의 키워드 (이미 금지어로 잡힌 구간은 제외)
        for kw, note in CAUTION:
            for m in re.finditer(re.escape(kw), s):
                if any(a <= m.start() and m.end() <= b for a, b in forbidden_spans):
                    continue
                caution_hits.setdefault(kw, []).append((lineno, highlight(s, [m.span()])))
                break
        # 2차: 문맥
        for name, patterns, reason, fix in CONTEXT_RULES:
            spans = [m.span() for p in patterns for m in re.finditer(p, s)]
            if spans:
                context_hits.append(dict(line=lineno, sentence=highlight(s, spans),
                                         category=name, reason=reason, fix=fix))

    missing_notice = bool(re.search(TREATMENT_WORDS, text)) and not re.search(SIDE_EFFECT_NOTICE, text)

    score = (SCORE_FORBIDDEN * len(forbidden_hits) + SCORE_CONTEXT * len(context_hits)
             + SCORE_CAUTION * len(caution_hits) + (SCORE_NO_NOTICE if missing_notice else 0))
    if forbidden_hits or score >= 20:
        grade = "🔴 빨강 (게시 불가 - 수정 필수)"
    elif score >= 5:
        grade = "🟡 노랑 (주의 필요 - 담당자 검토)"
    else:
        grade = "🟢 초록 (양호)"

    return dict(forbidden=forbidden_hits, context=context_hits, caution=caution_hits,
                missing_notice=missing_notice, score=score, grade=grade)


def build_report(filename, r):
    total = len(r["forbidden"]) + len(r["context"]) + (1 if r["missing_notice"] else 0)
    lines = [
        f"# 🚨 의료광고법 검수 리포트: {filename}",
        f"- **검수 일자:** {date.today().isoformat()}",
        f"- **종합 위험도:** {r['grade']}",
        f"- **위험 점수:** {r['score']}점 (금지어 {len(r['forbidden'])}건 · 문맥 경고 {len(r['context'])}건"
        f" · 주의 키워드 {len(r['caution'])}종{' · 부작용 안내 누락' if r['missing_notice'] else ''})",
        f"- **수정 필요 항목:** {total}건",
        "",
        "> 점수 기준: 금지어 1건당 10점 · 문맥 경고 5점 · 주의 키워드 1종당 1점 · 부작용 안내 누락 5점  ",
        "> 🔴 금지어 1건 이상 또는 20점 이상 / 🟡 5점 이상 / 🟢 5점 미만",
        "",
        "---",
        "",
        "## 🔴 1차 금지어 적발",
        "",
    ]
    if r["forbidden"]:
        for i, h in enumerate(r["forbidden"], 1):
            lines += [
                f"{i}. **발견된 문장 ({h['line']}번째 줄):** \"{h['sentence']}\"",
                f"   - **적발 키워드:** `{h['keyword']}`",
                f"   - **위반 사유:** {h['reason']}",
                f"   - **수정 가이드:** {h['fix']}",
                "",
            ]
    else:
        lines += ["적발된 금지어가 없습니다. ✅", ""]

    lines += ["---", "", "## 🟡 2차 문맥 주의 경고", ""]
    if r["context"]:
        for i, h in enumerate(r["context"], 1):
            lines += [
                f"{i}. **발견된 문장 ({h['line']}번째 줄):** \"{h['sentence']}\"",
                f"   - **분류:** {h['category']}",
                f"   - **위반 사유:** {h['reason']}",
                f"   - **수정 가이드:** {h['fix']}",
                "",
            ]
    else:
        lines += ["문맥상 경고 사항이 없습니다. ✅", ""]

    if r["missing_notice"]:
        lines += [
            "### ⚠️ 문서 전체 경고: 부작용·주의사항 안내 누락",
            "- **위반 사유:** 시술·치료 내용이 있으나 부작용/개인차 안내 문구가 없습니다 (제56조 제2항 제7호 소지).",
            "- **수정 가이드:** 글 하단에 다음 문구를 추가하세요.  ",
            "  \"모든 시술은 개인에 따라 통증, 붓기 등 부작용이 발생할 수 있으며, 결과에는 개인차가 있습니다."
            " 시술 전 전문의와 충분히 상담하시기 바랍니다.\"",
            "",
        ]

    lines += ["---", "", "## 🔎 주의 키워드 (담당자 확인용)", ""]
    if r["caution"]:
        note = dict(CAUTION)
        for kw, hits in r["caution"].items():
            lines.append(f"- **`{kw}`** ({len(hits)}회) — {note[kw]}")
            for lineno, s in hits[:3]:
                lines.append(f"  - {lineno}번째 줄: \"{s}\"")
            if len(hits) > 3:
                lines.append(f"  - …외 {len(hits) - 3}건")
        lines.append("")
    else:
        lines += ["주의 키워드가 없습니다.", ""]

    lines += [
        "---",
        "",
        "_※ 본 리포트는 키워드·패턴 기반 1차 스크리닝 결과입니다. 표현이 교묘하게 바뀐 경우 놓칠 수 있고,"
        " 부정문(예: '완치를 보장하지 않습니다')도 적발될 수 있으니 최종 게시 전 담당자 검토 및"
        " 의료광고 자율심의를 거치세요._",
    ]
    return "\n".join(lines) + "\n"


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    INPUT_DIR.mkdir(exist_ok=True)
    OUTPUT_DIR.mkdir(exist_ok=True)

    files = sorted(p for p in INPUT_DIR.iterdir() if p.suffix.lower() in (".txt", ".md"))
    if not files:
        print(f"input 폴더에 검수할 .txt/.md 파일이 없습니다: {INPUT_DIR}")
        return

    for path in files:
        result = check(read_text(path))
        out_path = OUTPUT_DIR / f"[검수완료]_{path.stem}.md"
        out_path.write_text(build_report(path.name, result), encoding="utf-8")
        print(f"{result['grade'][:2]} {path.name}  →  {out_path.name}  "
              f"(금지어 {len(result['forbidden'])} / 문맥 {len(result['context'])} / 점수 {result['score']})")

    print(f"\n완료: {len(files)}개 파일 검수 → {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
