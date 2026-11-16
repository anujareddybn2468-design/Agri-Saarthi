"""Crop-specific risk indicators. Explains why a crop may be at risk; does not predict yield."""

from dataclasses import dataclass

import pandas as pd

from agri.crops import CROP_PROFILES

FAVOURABLE = "Favourable"
WATCH = "Watch"
AT_RISK = "At risk"
UNKNOWN = "Unknown"


@dataclass
class Indicator:
    name: str
    status: str
    explanation: str


def _temperature_indicator(profile: dict, forecast: pd.DataFrame | None) -> Indicator:
    low, high = profile["ideal_temp_c"]
    if forecast is None or forecast["tmax"].isna().all():
        return Indicator("Temperature suitability", UNKNOWN, "7-day temperature forecast is unavailable.")
    mean_max = float(forecast["tmax"].mean())
    mean_min = float(forecast["tmin"].mean())
    mean_temp = (mean_max + mean_min) / 2
    if low <= mean_temp <= high:
        status = FAVOURABLE
        text = f"Average forecast temperature is {mean_temp:.1f} °C, inside the preferred {low}-{high} °C range."
    elif low - 4 <= mean_temp <= high + 4:
        status = WATCH
        text = f"Average forecast temperature is {mean_temp:.1f} °C, slightly outside the preferred {low}-{high} °C range."
    else:
        status = AT_RISK
        text = f"Average forecast temperature is {mean_temp:.1f} °C, well outside the preferred {low}-{high} °C range."
    return Indicator("Temperature suitability", status, text)


def _heat_indicator(profile: dict, forecast: pd.DataFrame | None) -> Indicator:
    limit = profile["heat_stress_c"]
    if forecast is None or forecast["tmax"].isna().all():
        return Indicator("Heat stress exposure", UNKNOWN, "7-day temperature forecast is unavailable.")
    peak = float(forecast["tmax"].max())
    if peak >= limit + 2:
        status, text = AT_RISK, f"Forecast peak of {peak:.1f} °C exceeds the heat stress limit of {limit} °C for this crop."
    elif peak >= limit:
        status, text = WATCH, f"Forecast peak of {peak:.1f} °C reaches the heat stress limit of {limit} °C."
    else:
        status, text = FAVOURABLE, f"Forecast peak of {peak:.1f} °C stays below the heat stress limit of {limit} °C."
    return Indicator("Heat stress exposure", status, text)


def _water_indicator(profile: dict, history: pd.DataFrame | None) -> Indicator:
    need = profile["water_need_30d_mm"]
    if history is None or history["rain_mm"].isna().all():
        return Indicator("Recent rainfall vs crop need", UNKNOWN, "Observed 30-day rainfall is unavailable.")
    total = float(history["rain_mm"].sum())
    ratio = total / need
    if ratio < 0.5:
        status = AT_RISK
    elif ratio < 1.0:
        status = WATCH
    else:
        status = FAVOURABLE
    text = (
        f"Observed rain over 30 days was {total:.0f} mm against a preliminary crop need of about {need} mm "
        f"({ratio:.0%} of need). Rainfall is not the only water source; irrigation and soil moisture matter."
    )
    return Indicator("Recent rainfall vs crop need", status, text)


def _excess_rain_indicator(profile: dict, forecast: pd.DataFrame | None) -> Indicator:
    limit = profile["excess_rain_7d_mm"]
    if forecast is None or forecast["rain_mm"].isna().all():
        return Indicator("Excess rain exposure", UNKNOWN, "7-day rainfall forecast is unavailable.")
    total = float(forecast["rain_mm"].sum())
    if total >= limit:
        status = AT_RISK
        text = f"Forecast rain of {total:.0f} mm over 7 days is at or above the preliminary {limit} mm level for this crop."
    elif total >= limit * 0.6:
        status = WATCH
        text = f"Forecast rain of {total:.0f} mm over 7 days is approaching the preliminary {limit} mm level."
    else:
        status = FAVOURABLE
        text = f"Forecast rain of {total:.0f} mm over 7 days is below the preliminary {limit} mm level."
    return Indicator("Excess rain exposure", status, text)


def _ph_indicator(profile: dict, ph: float | None) -> Indicator:
    low, high = profile["ph_range"]
    if ph is None:
        return Indicator("Soil pH suitability", UNKNOWN, "Soil pH data is unavailable for this location.")
    if low <= ph <= high:
        return Indicator("Soil pH suitability", FAVOURABLE, f"Soil pH {ph:.1f} is within the preferred {low}-{high} range.")
    if low - 0.5 <= ph <= high + 0.5:
        return Indicator("Soil pH suitability", WATCH, f"Soil pH {ph:.1f} is close to the preferred {low}-{high} range.")
    return Indicator("Soil pH suitability", AT_RISK, f"Soil pH {ph:.1f} is outside the preferred {low}-{high} range.")


def assess_crop(
    crop: str,
    forecast: pd.DataFrame | None,
    history: pd.DataFrame | None,
    ph: float | None,
) -> list[Indicator]:
    profile = CROP_PROFILES[crop]
    return [
        _temperature_indicator(profile, forecast),
        _heat_indicator(profile, forecast),
        _water_indicator(profile, history),
        _excess_rain_indicator(profile, forecast),
        _ph_indicator(profile, ph),
    ]
