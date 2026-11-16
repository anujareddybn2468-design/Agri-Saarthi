"""AgriSaarthi: Predict Climate Risks. Protect Crops. Empower Farmers."""

import html
import json
from pathlib import Path

import pandas as pd
import streamlit as st

from agri import views
from agri.advisory import generate_advisory
from agri.advisory_facts import build_facts
from agri.advisory_view import render_advisory
from agri.config import get_secret
from agri.crop_risk import assess_crop
from agri.crops import CROP_NAMES
from agri.gemini_client import DEFAULT_MODEL
from agri.geocoding import place_label, search_places
from agri.http_client import ApiError
from agri.mandi import fetch_mandi_prices
from agri.risk import assess_all_risks, overall_level
from agri.soil import fetch_soil
from agri.ui import pill
from agri.weather import fetch_forecast, fetch_history

st.set_page_config(page_title="AgriSaarthi", layout="wide")

STYLE_PATH = Path(__file__).parent / "assets" / "style.css"
st.markdown(f"<style>{STYLE_PATH.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)

LOGO_SVG = (
    '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20 3C10 3 4 8 4 15c0 1.3.3 2.4.8 3.4'
    'C5.6 12.5 9.5 9.5 15 9c-3.5 1.2-6.8 4-8.8 8.2 1.3.6 2.8.8 4.3.8C18 18 20 8 20 3z"/></svg>'
)


@st.cache_data(ttl=86400, show_spinner=False)
def cached_search(query: str) -> list[dict]:
    return search_places(query)


@st.cache_data(ttl=900, show_spinner=False)
def cached_forecast(lat: float, lon: float) -> dict:
    return fetch_forecast(lat, lon)


@st.cache_data(ttl=21600, show_spinner=False)
def cached_history(lat: float, lon: float) -> pd.DataFrame:
    return fetch_history(lat, lon)


@st.cache_data(ttl=604800, show_spinner=False)
def cached_soil(lat: float, lon: float) -> dict:
    return fetch_soil(lat, lon)


@st.cache_data(ttl=900, show_spinner=False)
def cached_advisory(facts_json: str, api_key: str | None) -> dict:
    return generate_advisory(json.loads(facts_json), api_key, DEFAULT_MODEL)


@st.cache_data(ttl=21600, show_spinner=False)
def cached_mandi(api_key: str, crop: str, state: str) -> dict:
    return fetch_mandi_prices(api_key, crop, state)


def parse_coordinates(text: str) -> tuple[float, float] | None:
    parts = [part.strip() for part in text.split(",")]
    if len(parts) != 2:
        return None
    try:
        lat, lon = float(parts[0]), float(parts[1])
    except ValueError:
        return None
    if -90 <= lat <= 90 and -180 <= lon <= 180:
        return lat, lon
    return None


def load_place_data(place: dict, crop: str, ndvi_value: float | None) -> dict:
    lat, lon = round(place["lat"], 4), round(place["lon"], 4)
    errors: dict[str, str] = {}
    data: dict = {}

    try:
        data["forecast"] = cached_forecast(lat, lon)
    except ApiError as exc:
        errors["forecast"] = str(exc)
    try:
        data["history"] = cached_history(lat, lon)
    except ApiError as exc:
        errors["history"] = str(exc)
    try:
        data["soil"] = cached_soil(lat, lon)
    except ApiError as exc:
        errors["soil"] = str(exc)

    forecast_df = data.get("forecast", {}).get("daily")
    history_df = data.get("history")
    soil = data.get("soil")
    ph = soil.get("phh2o", {}).get("value") if soil else None

    risks = assess_all_risks(forecast_df, history_df)
    indicators = assess_crop(crop, forecast_df, history_df, ph)
    facts = build_facts(place, crop, data.get("forecast"), history_df, soil, risks, indicators, ndvi_value)
    advisory = cached_advisory(json.dumps(facts, ensure_ascii=False, default=str), get_secret("GEMINI_API_KEY"))
    return {
        "data": data,
        "errors": errors,
        "risks": risks,
        "indicators": indicators,
        "advisory": advisory,
    }


def load_mandi(place: dict, crop: str) -> tuple[str | None, dict | None, str | None]:
    api_key = get_secret("DATA_GOV_IN_API_KEY")
    if not api_key:
        return "Mandi prices are not connected for this app yet, so no market prices are shown.", None, None
    state = place.get("state")
    if not state:
        return (
            "This place has no state name in the location data, so market prices cannot be matched. "
            "Search by district name.",
            None,
            None,
        )
    try:
        return None, cached_mandi(api_key, crop, state), None
    except ApiError as exc:
        return None, None, str(exc)


def render_header(place: dict | None, risk_level: str | None) -> None:
    location_html = ""
    if place and risk_level:
        names = [html.escape(name) for name in dict.fromkeys(
            value for value in (place["name"], place.get("district"), place.get("state")) if value
        )]
        location_html = (
            '<div class="brand-location">'
            + "".join(f"<strong>{names[0]}</strong>" if i == 0 else f"<span>{name}</span>" for i, name in enumerate(names))
            + '<div class="brand-risk"><div class="brand-risk-label">Overall farm risk</div>'
            + pill(risk_level)
            + "</div></div>"
        )
    st.markdown(
        '<div class="brand-hero"><div class="brand-row">'
        f'<div class="brand-logo">{LOGO_SVG}</div>'
        '<div><div class="brand-name">AgriSaarthi</div>'
        '<div class="brand-tagline">Predict Climate Risks. Protect Crops. Empower Farmers.</div></div>'
        "</div>"
        f"{location_html}</div>",
        unsafe_allow_html=True,
    )


def render_sidebar() -> tuple[dict | None, str, float | None]:
    with st.sidebar:
        st.markdown("### 1. Choose a location")
        with st.form("search_form", border=False):
            query = st.text_input(
                "Village, town or district",
                placeholder="e.g. Baramati",
                help="Enter a place name, or latitude and longitude such as 18.15, 74.58.",
            )
            submitted = st.form_submit_button("Search", width="stretch", type="primary")

        if submitted and query.strip():
            coords = parse_coordinates(query)
            if coords:
                st.session_state["place"] = {
                    "name": f"Coordinates {coords[0]:.3f}, {coords[1]:.3f}",
                    "district": "",
                    "state": "",
                    "country": "",
                    "lat": coords[0],
                    "lon": coords[1],
                }
                st.session_state.pop("candidates", None)
            else:
                try:
                    st.session_state["candidates"] = cached_search(query.strip())
                    st.session_state["search_error"] = None
                except ApiError as exc:
                    st.session_state["candidates"] = []
                    st.session_state["search_error"] = str(exc)
        elif submitted:
            st.warning("Please enter a place name.")

        if st.session_state.get("search_error"):
            st.error(f"Location search failed. {st.session_state['search_error']}")

        candidates = st.session_state.get("candidates")
        if candidates is not None and not st.session_state.get("search_error"):
            if not candidates:
                st.warning("No matching place found. Try the district name or enter coordinates.")
            else:
                labels = [place_label(place) for place in candidates]
                choice = st.selectbox("Did you mean", range(len(labels)), format_func=lambda i: labels[i])
                if st.button("Use this location", width="stretch"):
                    st.session_state["place"] = candidates[choice]
                    st.session_state.pop("candidates", None)

        st.markdown("### 2. Choose a crop")
        crop = st.selectbox("Crop", CROP_NAMES, index=CROP_NAMES.index(st.session_state.get("crop", "Rice")))
        st.session_state["crop"] = crop

        st.markdown("### Optional")
        ndvi_value = None
        if st.checkbox("I have a vegetation index (NDVI) value"):
            ndvi_value = st.number_input("NDVI (-1 to 1)", min_value=-1.0, max_value=1.0, value=0.5, step=0.01)

        st.caption("Data: Open-Meteo weather and SoilGrids soil estimates.")
    return st.session_state.get("place"), crop, ndvi_value


def main() -> None:
    place, crop, ndvi_value = render_sidebar()

    if place is None:
        render_header(None, None)
        st.info("Search for a village, town or district in the sidebar to see its weather, soil and crop risks.")
        return

    with st.spinner("Loading weather, soil, risks, mandi prices and your advisory..."):
        loaded = load_place_data(place, crop, ndvi_value)
        mandi_notice, mandi, mandi_error = load_mandi(place, crop)
    data, errors = loaded["data"], loaded["errors"]
    render_header(place, overall_level([risk.level for risk in loaded["risks"]]))

    tabs = st.tabs([
        "Overview",
        "Climate risks",
        "Soil",
        "Crop risk",
        "AI advisory",
        "Mandi prices",
        "NDVI (optional)",
        "Method and limits",
    ])
    with tabs[0]:
        views.render_overview(
            place,
            data.get("forecast", {}).get("current"),
            data.get("forecast", {}).get("daily"),
            errors.get("forecast"),
            ndvi_value,
        )
        views.render_history(data.get("history"), errors.get("history"))
    with tabs[1]:
        views.render_risks(loaded["risks"], crop)
    with tabs[2]:
        views.render_soil(data.get("soil"), errors.get("soil"))
    with tabs[3]:
        views.render_crop_risk(crop, loaded["indicators"])
    with tabs[4]:
        render_advisory(loaded["advisory"])
    with tabs[5]:
        views.render_mandi(crop, mandi_notice, mandi, mandi_error)
    with tabs[6]:
        views.render_ndvi(ndvi_value)
    with tabs[7]:
        views.render_method()


main()
