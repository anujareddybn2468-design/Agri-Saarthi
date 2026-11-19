"""Collects the facts the advisory is allowed to use. Missing values stay None and are listed in `missing`."""

import json

import pandas as pd

from agri.crop_risk import Indicator
from agri.crops import CROP_PROFILES
from agri.ndvi import classify_ndvi
from agri.risk import RiskResult


def _round(value, digits=1):
    return None if value is None or pd.isna(value) else round(float(value), digits)


def _forecast_records(daily: pd.DataFrame) -> list[dict]:
    return [
        {
            "date": row.date.strftime("%Y-%m-%d"),
            "tmax_c": _round(row.tmax),
            "tmin_c": _round(row.tmin),
            "rain_mm": _round(row.rain_mm),
            "rain_chance_pct": _round(row.rain_prob_pct, 0),
            "wind_max_kmh": _round(row.wind_max_kmh, 0),
        }
        for row in daily.itertuples()
    ]


def _history_summary(history: pd.DataFrame) -> dict:
    return {
        "period": f"{history['date'].min():%d %b %Y} to {history['date'].max():%d %b %Y}",
        "rain_total_mm": _round(history["rain_mm"].sum(), 0),
        "rainy_days": int((history["rain_mm"] >= 1).sum()),
        "hot_days_35c_or_more": int((history["tmax"] >= 35).sum()),
        "mean_max_c": _round(history["tmax"].mean()),
    }


def build_facts(
    place: dict,
    crop: str,
    weather: dict | None,
    history: pd.DataFrame | None,
    soil: dict | None,
    risks: list[RiskResult],
    indicators: list[Indicator],
    ndvi_value: float | None,
) -> dict:
    forecast = weather["daily"] if weather else None
    current = weather["current"] if weather else None
    profile = CROP_PROFILES[crop]
    missing: list[str] = []

    current_facts = None
    if current:
        soil_moisture = current.get("soil_moisture_m3m3")
        current_facts = {
            "time": current.get("time"),
            "temperature_c": _round(current.get("temperature_c")),
            "humidity_pct": _round(current.get("humidity_pct"), 0),
            "rain_now_mm": _round(current.get("rain_mm")),
            "wind_kmh": _round(current.get("wind_kmh"), 0),
            "soil_moisture_model_pct": None if soil_moisture is None else _round(soil_moisture * 100, 0),
        }
        if soil_moisture is None:
            missing.append("Soil moisture from the weather model")
    else:
        missing.append("Current weather conditions")

    if forecast is None or forecast.empty:
        missing.append("7-day weather forecast")
    if history is None or history.empty:
        missing.append("Observed rainfall and temperature for the last 30 days")
    if soil is None:
        missing.append("Soil properties")
    elif "phh2o" not in soil:
        missing.append("Soil pH")
    if ndvi_value is None:
        missing.append("NDVI (vegetation health) value, not entered")

    return {
        "location": {
            "name": place["name"],
            "district": place.get("district") or None,
            "state": place.get("state") or None,
            "country": place.get("country") or None,
            "lat": round(place["lat"], 4),
            "lon": round(place["lon"], 4),
        },
        "crop": {
            "name": crop,
            "season": profile["season"],
            "reference_note": profile["note"],
            "reference_values_status": "preliminary general reference values, not locally validated",
        },
        "current_weather": current_facts,
        "forecast_7_days": _forecast_records(forecast) if forecast is not None and not forecast.empty else None,
        "observed_last_30_days": _history_summary(history) if history is not None and not history.empty else None,
        "soil_estimates_0_5cm": soil or None,
        "climate_risks": [
            {
                "name": risk.name,
                "level": risk.level,
                "evidence": risk.evidence,
                "unavailable": risk.unavailable,
            }
            for risk in risks
        ],
        "crop_indicators": [
            {"name": item.name, "status": item.status, "explanation": item.explanation}
            for item in indicators
        ],
        "vegetation_ndvi": None
        if ndvi_value is None
        else {"value": ndvi_value, "status": classify_ndvi(ndvi_value)[1], "source": "user-entered"},
        "missing_data": missing,
    }


ADVISORY_SCHEMA = {
    "farm_status": {"level": "LOW | MODERATE | HIGH | CRITICAL | INSUFFICIENT DATA", "summary": "string"},
    "top_priority": {"action": "string", "why": "string", "when": "string"},
    "weather_advice": {"expected": "string", "crop_effect": "string", "precautions": ["string"]},
    "crop_recommendations": [{"topic": "Irrigation | Soil moisture | Nutrients | Pest and disease | Harvest or sowing", "advice": "string", "basis": "string"}],
    "next_7_days": [{"day": "Today or Day N (date)", "action": "string"}],
    "preventive_measures": ["string"],
    "data_confidence": {
        "measured": ["string"],
        "forecast": ["string"],
        "model_estimates": ["string"],
        "missing": ["string"],
    },
}


def build_prompt(facts: dict) -> str:
    return (
        "You are an agronomy advisor writing for a smallholder farmer in India. "
        "Use ONLY the facts in the JSON below. Do not invent weather readings, soil measurements, "
        "mandi prices, crop-health scores, yields or any number not present in the data. "
        "If a value is null or listed in missing_data, say that it is unavailable instead of assuming it. "
        "Label forecasts as forecasts, observed values as observed, and soil or soil-moisture values as model estimates. "
        "Keep every sentence short, plain and respectful for a smallholder farmer. "
        "Prioritize actions the farmer can safely verify in the field. Distinguish an observation from a forecast. "
        "Do not tell the farmer to irrigate automatically: ask them to check field or root-zone moisture first. "
        "Do not recommend pesticide, fungicide, fertilizer dose, chemical product or disease treatment. "
        "Only suggest scouting for pests or disease when the supplied facts support a wet or stress condition. "
        "Do not assume crop growth stage, soil type, irrigation access, farm size or farmer equipment. "
        "Return a single JSON object that follows this structure exactly (same keys, types and order): "
        f"{json.dumps(ADVISORY_SCHEMA)}. "
        "The next_7_days list must contain one entry per forecast day in the data, and be an empty list if no forecast is given. "
        "Make each day's action specific to that day's supplied conditions; if no notable condition exists, give a different useful monitoring task without inventing facts. "
        "For every crop recommendation, include a short basis tied to a supplied fact. Use only the allowed topic names in the schema.\n\n"
        f"FACTS:\n{json.dumps(facts, ensure_ascii=False, default=str)}"
    )
