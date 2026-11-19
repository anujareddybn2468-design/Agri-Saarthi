
"""Optional API keys. Values are read at runtime and never displayed or logged."""

import os
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / "assets" / ".env")

def get_secret(name: str) -> str | None:
    value = os.environ.get(name)
    if value and value.strip():
        return value.strip()
    try:
        value = st.secrets.get(name)
    except Exception:
        return None
    return value.strip() if isinstance(value, str) and value.strip() else None
