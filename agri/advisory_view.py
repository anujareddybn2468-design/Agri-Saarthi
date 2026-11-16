"""Advisory tab: shows the advisory in fixed sections, labelled with the source that produced it."""

import html

import streamlit as st

from agri.advisory import SOURCE_GEMINI
from agri.ui import pill

TOPIC_ICONS = {
    "Irrigation": "water_drop",
    "Soil moisture": "grass",
    "Nutrients": "science",
    "Pest and disease": "bug_report",
    "Harvest or sowing": "agriculture",
}


def _source_banner(result: dict) -> None:
    tag_class = "source-tag" if result["source"] == SOURCE_GEMINI else "source-tag source-rules"
    st.markdown(
        f'<div class="source-banner"><span class="{tag_class}">{html.escape(result["source"])}</span>'
        f'<span>{html.escape(result["note"])}</span></div>',
        unsafe_allow_html=True,
    )


def _farm_status(status: dict) -> None:
    st.markdown("#### 1. Farm status")
    st.markdown(pill(status["level"].upper()), unsafe_allow_html=True)
    st.write(status["summary"])


def _top_priority(priority: dict | None) -> None:
    st.markdown("#### 2. Top priority")
    if not priority:
        st.info("No single action stands out in the data available.")
        return
    st.markdown(
        '<div class="priority-card"><div class="card-label">Most urgent action</div>'
        f'<div class="priority-action">{html.escape(priority["action"])}</div>'
        f'<div class="priority-meta"><strong>Why:</strong> {html.escape(priority["why"])}</div>'
        f'<div class="priority-meta"><strong>When:</strong> {html.escape(priority["when"])}</div></div>',
        unsafe_allow_html=True,
    )


def _weather_advice(block: dict) -> None:
    st.markdown("#### 3. Weather-based advice")
    with st.container(border=True):
        st.markdown("**Expected weather**")
        st.write(block["expected"])
        st.markdown("**Effect on the crop**")
        st.write(block["crop_effect"])
        st.markdown("**Precautions**")
        for item in block["precautions"]:
            st.markdown(f"- {item}")


def _crop_recommendations(items: list[dict]) -> None:
    st.markdown("#### 4. Crop-specific recommendations")
    if not items:
        st.info("No crop-specific action is supported by the data available.")
        return
    for item in items:
        with st.container(border=True):
            st.markdown(f":material/{TOPIC_ICONS.get(item['topic'], 'info')}: **{item['topic']}**")
            st.write(item["advice"])
            st.caption(f"Basis: {item['basis']}")


def _next_seven_days(plan: list[dict]) -> None:
    st.markdown("#### 5. Next 7 days")
    if not plan:
        st.info("No forecast is available, so a day-wise plan cannot be made.")
        return
    with st.container(border=True):
        for entry in plan:
            st.markdown(f"**{entry['day']}:** {entry['action']}")


def _preventive(items: list[str]) -> None:
    st.markdown("#### 6. Preventive measures")
    for item in items:
        st.markdown(f"- {item}")


def _data_confidence(confidence: dict) -> None:
    st.markdown("#### 7. Data confidence")
    sections = [
        ("Measured observations", confidence["measured"]),
        ("Weather forecasts", confidence["forecast"]),
        ("Model-based estimates", confidence["model_estimates"]),
        ("Missing or unavailable", confidence["missing"]),
    ]
    for start in range(0, len(sections), 2):
        columns = st.columns(2, gap="medium")
        for column, (title, lines) in zip(columns, sections[start:start + 2]):
            with column, st.container(border=True):
                st.markdown(f"**{title}**")
                for line in lines:
                    st.markdown(f"- {line}")


def render_advisory(result: dict) -> None:
    advisory = result["advisory"]
    _source_banner(result)
    _farm_status(advisory["farm_status"])
    _top_priority(advisory["top_priority"])
    _weather_advice(advisory["weather_advice"])
    _crop_recommendations(advisory["crop_recommendations"])
    _next_seven_days(advisory["next_7_days"])
    _preventive(advisory["preventive_measures"])
    _data_confidence(advisory["data_confidence"])
