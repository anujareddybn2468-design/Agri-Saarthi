"""Shared dashboard building blocks: pills, metric cards and section headings."""

import html

import streamlit as st

from agri.risk import CRITICAL, HIGH, INSUFFICIENT, LOW, MODERATE

PILL_CLASSES = {
    LOW: "sev-low",
    MODERATE: "sev-moderate",
    HIGH: "sev-high",
    CRITICAL: "sev-critical",
    INSUFFICIENT: "sev-none",
    "Favourable": "sev-low",
    "Watch": "sev-moderate",
    "At risk": "sev-high",
    "Unknown": "sev-none",
}


def pill(label: str) -> str:
    css = PILL_CLASSES.get(label, "sev-none")
    return f'<span class="pill {css}">{html.escape(label)}</span>'


def section_heading(icon: str, title: str, subtitle: str | None = None) -> None:
    st.markdown(f"### :material/{icon}: {title}")
    if subtitle:
        st.markdown(f'<div class="disclaimer">{html.escape(subtitle)}</div>', unsafe_allow_html=True)


def metric_card(icon: str, label: str, value: str | None, unit: str = "", note: str = "") -> None:
    with st.container(border=True):
        st.markdown(f":material/{icon}: <span class='card-label'>{html.escape(label)}</span>", unsafe_allow_html=True)
        if value is None:
            st.markdown("<div class='metric-note'>Unavailable right now</div>", unsafe_allow_html=True)
            return
        st.markdown(
            f"<div class='metric-value'>{html.escape(value)}<span class='metric-unit'>{html.escape(unit)}</span></div>",
            unsafe_allow_html=True,
        )
        if note:
            st.markdown(f"<div class='metric-note'>{html.escape(note)}</div>", unsafe_allow_html=True)
