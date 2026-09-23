# -*- coding: utf-8 -*-
"""
의료광고 자동 검수기 - 웹 버전 (Streamlit)

실행: streamlit run app.py
검수 규칙(금지어·주의 키워드·문맥 패턴)은 checker.py 한 곳에서 관리합니다.
"""
import html
import re
from datetime import date

import streamlit as st

from checker import CAUTION, SCORE_CAUTION, SCORE_CONTEXT, SCORE_FORBIDDEN, SCORE_NO_NOTICE, build_report, check

st.set_page_config(page_title="의료광고 자동 검수기", page_icon="🩺", layout="centered")

st.markdown(
    """
    <style>
    .grade-box {padding: 1.4rem 1.2rem; border-radius: 12px; text-align: center; margin: 0.5rem 0 1rem;}
    .grade-box .label {font-size: 1.9rem; font-weight: 800;}
    .grade-box .desc {font-size: 1rem; margin-top: 0.3rem;}
    .grade-red    {background: #fde8e8; color: #9b1c1c; border: 2px solid #f05252;}
    .grade-yellow {background: #fdf6b2; color: #723b13; border: 2px solid #e3a008;}
    .grade-green  {background: #def7ec; color: #03543f; border: 2px solid #31c48d;}
    .hit {padding: 0.8rem 1rem; border-radius: 8px; margin-bottom: 0.7rem; background: rgba(128,128,128,0.08);}
    .hit .sent {font-size: 1.02rem; margin-bottom: 0.4rem;}
    .hit .meta {font-size: 0.92rem; line-height: 1.6;}
    .hit mark {background: #fbd38d; color: inherit; padding: 0 2px; border-radius: 3px;}
    .hit-red {border-left: 5px solid #f05252;}
    .hit-yellow {border-left: 5px solid #e3a008;}
    </style>
    """,
    unsafe_allow_html=True,
)


def to_html(sentence):
    """checker가 **굵게** 표시한 적발 구간을 형광펜(<mark>)으로 바꿔 안전하게 출력"""
    return re.sub(r"\*\*(.+?)\*\*", r"<mark>\1</mark>", html.escape(sentence))


def hit_card(h, color, title_key, title_label):
    st.markdown(
        f"""<div class="hit hit-{color}">
        <div class="sent">📌 <b>{h['line']}번째 줄</b> · "{to_html(h['sentence'])}"</div>
        <div class="meta">
        <b>{title_label}:</b> {html.escape(h[title_key])}<br>
        <b>위반 사유:</b> {html.escape(h['reason'])}<br>
        <b>✏️ 수정 가이드:</b> {html.escape(h['fix'])}
        </div></div>""",
        unsafe_allow_html=True,
    )


# ─── 사이드바: 사용법 · 점수 기준 ───
with st.sidebar:
    st.header("사용 방법")
    st.markdown("1. 블로그 원고를 복사해 붙여넣기\n2. **[검수하기]** 클릭\n3. 빨강·노랑 항목을 수정 가이드대로 고치기")
    st.header("점수 기준")
    st.markdown(
        f"- 금지어 1건: **{SCORE_FORBIDDEN}점**\n"
        f"- 문맥 경고 1건: **{SCORE_CONTEXT}점**\n"
        f"- 주의 키워드 1종: **{SCORE_CAUTION}점**\n"
        f"- 부작용 안내 누락: **{SCORE_NO_NOTICE}점**\n\n"
        "🔴 금지어 1건 이상 또는 20점 이상\n\n🟡 5점 이상\n\n🟢 5점 미만"
    )
    st.caption("※ 키워드·패턴 기반 1차 스크리닝 도구입니다. 최종 게시 전 담당자 검토 및 의료광고 자율심의를 거치세요.")

# ─── 본문 ───
st.title("🩺 의료광고 자동 검수기")
st.caption("블로그·마케팅 원고를 붙여넣으면 의료광고법 위반 소지 표현을 바로 찾아드립니다.")

text = st.text_area("검수할 원고", height=320, placeholder="여기에 블로그 원고를 붙여넣으세요.")
run = st.button("🔍 검수하기", type="primary", use_container_width=True)

if run:
    if not text.strip():
        st.warning("원고를 입력해 주세요.")
        st.stop()

    r = check(text)

    if r["grade"].startswith("🔴"):
        color, label, desc = "red", "🔴 빨강", "게시 불가 · 아래 항목을 반드시 수정하세요"
    elif r["grade"].startswith("🟡"):
        color, label, desc = "yellow", "🟡 노랑", "주의 필요 · 담당자 검토 후 게시하세요"
    else:
        color, label, desc = "green", "🟢 초록", "양호 · 큰 위험 요소가 발견되지 않았습니다"
    st.markdown(
        f'<div class="grade-box grade-{color}"><div class="label">{label}</div><div class="desc">{desc}</div></div>',
        unsafe_allow_html=True,
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("위험 점수", f"{r['score']}점")
    c2.metric("금지어", f"{len(r['forbidden'])}건")
    c3.metric("문맥 경고", f"{len(r['context'])}건")
    c4.metric("주의 키워드", f"{len(r['caution'])}종")

    st.subheader("🔴 1차 금지어 적발")
    if r["forbidden"]:
        for h in r["forbidden"]:
            hit_card(h, "red", "keyword", "적발 키워드")
    else:
        st.success("적발된 금지어가 없습니다.")

    st.subheader("🟡 2차 문맥 주의 경고")
    if r["context"]:
        for h in r["context"]:
            hit_card(h, "yellow", "category", "분류")
    else:
        st.success("문맥상 경고 사항이 없습니다.")

    if r["missing_notice"]:
        st.warning(
            "**⚠️ 부작용·주의사항 안내 누락** — 시술 내용이 있으나 부작용/개인차 안내가 없습니다 "
            "(의료법 제56조 제2항 제7호 소지). 글 하단에 아래 문구를 추가하세요."
        )
        st.code(
            "모든 시술은 개인에 따라 통증, 붓기 등 부작용이 발생할 수 있으며, 결과에는 개인차가 있습니다. "
            "시술 전 전문의와 충분히 상담하시기 바랍니다.",
            language=None,
        )

    with st.expander(f"🔎 주의 키워드 (담당자 확인용) · {len(r['caution'])}종", expanded=False):
        if r["caution"]:
            note = dict(CAUTION)
            for kw, hits in r["caution"].items():
                st.markdown(f"**`{kw}`** ({len(hits)}회) — {note[kw]}")
                for lineno, s in hits[:3]:
                    st.markdown(f"<div style='margin-left:1rem'>· {lineno}번째 줄: \"{to_html(s)}\"</div>",
                                unsafe_allow_html=True)
                if len(hits) > 3:
                    st.caption(f"…외 {len(hits) - 3}건")
        else:
            st.write("주의 키워드가 없습니다.")

    st.download_button(
        "📄 검수 리포트 다운로드 (.md)",
        data=build_report("웹 입력 원고", r).encode("utf-8"),
        file_name=f"[검수완료]_원고_{date.today().isoformat()}.md",
        mime="text/markdown",
        use_container_width=True,
    )
