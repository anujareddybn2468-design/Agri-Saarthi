
"""Dashboard section renderers. Each function draws one tab from already-loaded data."""

import html

import pandas as pd
import streamlit as st

from agri import charts
from agri.crop_risk import Indicator
from agri.crops import CROP_PROFILES, crop_relevance
from agri.mandi import DATASET_NAME, market_trends
from agri.ndvi import classify_ndvi
from agri.risk import INSUFFICIENT, PRELIMINARY_NOTE, RiskResult
from agri.soil import SOIL_PROPERTIES
from agri.ui import metric_card, pill


def unavailable_notice(messages: list[str]) -> None:
    for message in messages:
        st.caption(f"Unavailable: {message}")


def _value(number: float | None) -> str | None:
    return None if number is None else f"{number:g}"


def _metric_grid(cards: list[tuple], per_row: int = 2) -> None:
    for start in range(0, len(cards), per_row):
        columns = st.columns(per_row, gap="medium")
        for column, card in zip(columns, cards[start:start + per_row]):
            with column:
                metric_card(*card)


def _overview_cards(current: dict, ndvi_value: float | None) -> list[tuple]:
    cards = [
        ("thermostat", "Temperature", _value(current["temperature_c"]), "°C", "Current reading"),
        ("water_drop", "Humidity", _value(current["humidity_pct"]), "%", "Relative humidity"),
        ("rainy", "Rainfall now", _value(current["rain_mm"]), "mm", "Current reading"),
        ("air", "Wind speed", _value(current["wind_kmh"]), "km/h", "Wind at 10 m height"),
    ]
    moisture = current["soil_moisture_m3m3"]
    if moisture is not None:
        cards.append(("grass", "Soil moisture", f"{moisture * 100:.0f}", "%", "Model estimate, 0-7 cm depth"))
    if ndvi_value is not None:
        description, _ = classify_ndvi(ndvi_value)
        cards.append(("eco", "Crop health (NDVI)", f"{ndvi_value:.2f}", "", f"{description}. Value entered by you."))
    return cards


def render_overview(
    place: dict,
    current: dict | None,
    forecast: pd.DataFrame | None,
    error: str | None,
    ndvi_value: float | None,
) -> None:
    left, right = st.columns([1.4, 1], gap="large")
    with left:
        st.markdown("#### Farm overview")
        if error:
            st.warning(f"Live weather is unavailable. {error}")
        elif current:
            _metric_grid(_overview_cards(current, ndvi_value))
            st.caption("Readings come from the Open-Meteo weather model, not a physical station.")
    with right:
        st.markdown("#### Location")
        st.map(pd.DataFrame({"lat": [place["lat"]], "lon": [place["lon"]]}), zoom=8, height=260)

    st.markdown("#### Seven-day forecast")
    st.caption("Forecast for the coming days from the Open-Meteo weather model. Not observed readings.")
    if error or forecast is None or forecast.empty:
        st.info("The seven-day forecast could not be loaded, so forecast charts are not shown.")
        return
    rain_column, temperature_column = st.columns(2, gap="medium")
    with rain_column:
        st.plotly_chart(charts.rainfall_forecast_chart(forecast), width="stretch")
    with temperature_column:
        st.plotly_chart(charts.temperature_forecast_chart(forecast), width="stretch")
    table = forecast.assign(date=forecast["date"].dt.strftime("%a %d %b")).rename(
        columns={
            "date": "Day",
            "tmax": "Max °C",
            "tmin": "Min °C",
            "rain_mm": "Rain mm",
            "rain_prob_pct": "Rain chance %",
            "wind_max_kmh": "Max wind km/h",
        }
    )
    st.dataframe(table, hide_index=True, width="stretch")


def render_history(history: pd.DataFrame | None, error: str | None) -> None:
    st.markdown("#### Historical weather archive (30 days)")
    if error or history is None or history.empty:
        st.info(f"Historical weather archive is unavailable. {error or ''}".strip())
        return
    st.plotly_chart(charts.history_chart(history), width="stretch")
    st.caption(
        "Historical archive/reanalysis estimates from Open-Meteo. "
        "These are not direct measurements from a local weather station. "
        "The most recent 5 days are not yet included."
    )


def render_risks(risks: list[RiskResult], crop: str) -> None:
    st.caption(PRELIMINARY_NOTE)
    st.caption(
        "Forecast evidence covers the next 7 days. Historical archive estimates cover the last 30 days."
    )
    st.caption("Levels come from risk points: 0 LOW, 1-2 MODERATE, 3-4 HIGH, 5 or more CRITICAL.")
    columns = st.columns(2, gap="medium")
    for index, risk in enumerate(risks):
        with columns[index % 2], st.container(border=True):
            st.markdown(f"**{risk.name}**")
            st.markdown(pill(risk.level), unsafe_allow_html=True)
            st.caption(f"Why it matters for {crop}: {crop_relevance(risk.name, crop)}")
            for line in risk.evidence:
                st.markdown(f"- {line}")
            unavailable_notice(risk.unavailable)
            if risk.level != INSUFFICIENT:
                st.caption(f"Risk points reached: {risk.points}")


def render_soil(soil: dict[str, dict] | None, error: str | None) -> None:
    st.markdown("#### Soil properties (SoilGrids, 0-5 cm, estimated)")
    st.caption("Values are model estimates for a 250 m grid cell, not laboratory tests on your field.")
    if error:
        st.warning(f"Soil data is unavailable. {error}")
        return
    if not soil:
        st.info("SoilGrids returned no values for this location.")
        return
    cards = [
        ("science", data["label"], f"{data['value']:g}", data["unit"], data["relevance"])
        for data in soil.values()
    ]
    _metric_grid(cards)
    missing = [label for code, (label, _) in SOIL_PROPERTIES.items() if code not in soil]
    if missing:
        unavailable_notice([f"{label} not provided for this location." for label in missing])


def render_crop_risk(crop: str, indicators: list[Indicator]) -> None:
    profile = CROP_PROFILES[crop]
    st.markdown(f"#### {crop}: {profile['season']}")
    st.caption(profile["note"])
    st.caption(PRELIMINARY_NOTE + " Crop reference values are general agronomy guidance and are not locally validated.")
    for indicator in indicators:
        st.markdown(
            f'<div class="indicator-row"><div><strong>{html.escape(indicator.name)}</strong><br>'
            f'<span class="card-note">{html.escape(indicator.explanation)}</span></div>'
            f'<div>{pill(indicator.status)}</div></div>',
            unsafe_allow_html=True,
        )
    st.info(
        "This is a risk indicator, not a yield prediction. AgriSaarthi does not have validated yield "
        "training data, so no yield number is shown."
    )


def render_mandi(crop: str, notice: str | None, result: dict | None, error: str | None) -> None:
    st.markdown(f"#### Mandi prices: {crop}")
    st.caption("Wholesale prices as published in the data.gov.in daily market dataset, in rupees per quintal.")
    if notice:
        st.info(notice)
        return
    if error:
        st.warning(f"Mandi prices are unavailable right now. {error}")
        return
    rows = result["rows"]
    source_line = f"Source: {DATASET_NAME}. Fetched {result['fetched_at']}."
    if rows.empty:
        st.info(f"The dataset has no price records for {crop} in this state.")
        st.caption(source_line)
        return

    latest_date = rows["arrival_date"].max()
    latest = rows[rows["arrival_date"] == latest_date]
    metric_cols = st.columns(3, gap="medium")
    with metric_cols[0]:
        metric_card("storefront", "Markets reporting", str(latest["market"].nunique()), "", f"On {latest_date:%d %b %Y}")
    with metric_cols[1]:
        metric_card("payments", "Average modal price", f"₹{latest['modal_price'].mean():,.0f}", "/quintal", "Latest reported date")
    with metric_cols[2]:
        metric_card("trending_up", "Price range", f"₹{latest['modal_price'].min():,.0f}-{latest['modal_price'].max():,.0f}", "", "Latest reported date")

    st.plotly_chart(charts.mandi_price_chart(latest), width="stretch")

    table = market_trends(rows).rename(
        columns={
            "market": "Market",
            "district": "District",
            "variety": "Variety",
            "arrival_date": "Arrival date",
            "min_price": "Min ₹/quintal",
            "modal_price": "Modal ₹/quintal",
            "max_price": "Max ₹/quintal",
            "change_pct": "Change vs previous report (%)",
        }
    )
    table["Arrival date"] = table["Arrival date"].dt.strftime("%d %b %Y")
    st.dataframe(
        table[
            [
                "Market", "District", "Variety", "Arrival date", "Min ₹/quintal",
                "Modal ₹/quintal", "Max ₹/quintal", "Change vs previous report (%)",
            ]
        ],
        hide_index=True,
        width="stretch",
    )
    st.caption(
        source_line + " A blank change means the market has only one reported date in the data, so no trend is computed."
    )


def render_ndvi(ndvi_value: float | None) -> None:
    st.markdown("#### Satellite NDVI (optional)")
    st.caption(
        "No satellite feed is connected yet. If you or an advisor have an NDVI value for your field "
        "(from a satellite app or drone survey), enter it here. It is labelled as user-provided."
    )
    if ndvi_value is None:
        st.info("No NDVI value entered yet.")
        return
    description, status = classify_ndvi(ndvi_value)
    metric_card("eco", "User-provided NDVI", f"{ndvi_value:.2f}", "", f"{description} ({status})")
    st.caption("NDVI bands are general guidance (below 0.2 sparse, 0.2-0.4 moderate, 0.4-0.6 healthy, above 0.6 dense). Not locally validated.")


def render_method() -> None:
    st.markdown("#### Data sources")
    st.markdown(
        "- **Location search:** Open-Meteo geocoding.\n"
        "- **Live weather and 7-day forecast:** Open-Meteo forecast API.\n"
        "- **Historical weather (30 days):** Open-Meteo archive/reanalysis estimates, ending 5 days ago; not direct station measurements.\n"
        "- **Soil properties:** ISRIC SoilGrids v2.0 (0-5 cm mean estimate).\n"
        "- **Mandi prices:** data.gov.in daily market prices (needs an API key to be connected).\n"
        "- **AI advisory:** Gemini AI when connected, otherwise the rule-based engine.\n"
        "- **NDVI:** Optional, user-entered only."
    )
    st.markdown("#### Risk rules (preliminary)")
    st.markdown(
        "- **Drought:** historical 30-day archive rainfall estimate under 30 mm (+2) or under 60 mm (+1); dry spell of 14+ days (+1); forecast 7-day rain under 5 mm (+1).\n"
        "- **Heat stress:** forecast peak 40 °C+ (+2) or 38 °C+ (+1); historical archive hot-day estimates (35 °C+) 10+ (+2) or 5+ (+1).\n"
        "- **Excessive rainfall:** forecast 7-day total 100 mm+ (+2) or 50 mm+ (+1); heaviest day 115.5 mm+ (+2) or 64.5 mm+ (+1); historical 30-day archive rainfall estimate 300 mm+ (+1).\n"
        "- **Levels:** 0 LOW, 1-2 MODERATE, 3-4 HIGH, 5+ CRITICAL."
    )
    st.markdown("#### Limits")
    st.markdown(
        "- Forecasts are model predictions and can be wrong.\n"
        "- Historical weather values are archive/reanalysis estimates, not direct station observations.\n"
        "- Soil values are estimates from a 250 m grid, not field tests.\n"
        "- No yield predictions are made because there is no validated training data.\n"
        "- The AI advisory only states figures present in the collected data. It is not a trained machine-learning model.\n"
        "- All thresholds must be validated locally before operational use."
    )
