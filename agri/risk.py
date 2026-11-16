"""Explainable climate risk engine.

Every risk is a transparent points system. Each point is listed in `evidence` so users can see
why a level was reached. Forecast evidence and observed evidence are kept separate.
All thresholds are PRELIMINARY and must be locally validated before operational use.
"""

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

PRELIMINARY_NOTE = "Thresholds are preliminary and have not been locally validated."

LOW = "LOW"
MODERATE = "MODERATE"
HIGH = "HIGH"
CRITICAL = "CRITICAL"
INSUFFICIENT = "INSUFFICIENT DATA"
SEVERITY_ORDER = [LOW, MODERATE, HIGH, CRITICAL]

# Observed (last 30 days) rainfall thresholds, mm
DROUGHT_OBS_SEVERE_MM = 30
DROUGHT_OBS_MODERATE_MM = 60
DROUGHT_FORECAST_DRY_MM = 5
DRY_SPELL_DAYS = 14

HEAT_FORECAST_EXTREME_C = 40
HEAT_FORECAST_HIGH_C = 38
HEAT_THRESHOLD_DAY_C = 35
HEAT_OBS_DAYS_MANY = 10
HEAT_OBS_DAYS_SOME = 5

COLD_FORECAST_SEVERE_C = 2
COLD_FORECAST_MILD_C = 5

RAIN_FORECAST_TOTAL_HIGH_MM = 100
RAIN_FORECAST_TOTAL_MODERATE_MM = 50
RAIN_HEAVY_DAY_MM = 64.5
RAIN_VERY_HEAVY_DAY_MM = 115.5
RAIN_OBS_30D_WET_MM = 300


@dataclass
class RiskResult:
    name: str
    level: str
    points: int = 0
    evidence: list[str] = field(default_factory=list)
    unavailable: list[str] = field(default_factory=list)
    source: str = "Forecast and observed"


def level_from_points(points: int) -> str:
    if points >= 5:
        return CRITICAL
    if points >= 3:
        return HIGH
    if points >= 1:
        return MODERATE
    return LOW


def overall_level(levels: list[str]) -> str:
    rated = [level for level in levels if level in SEVERITY_ORDER]
    if not rated:
        return INSUFFICIENT
    return max(rated, key=SEVERITY_ORDER.index)


def _finish(result: RiskResult, points: int) -> RiskResult:
    result.points = points
    result.level = level_from_points(points) if result.evidence else INSUFFICIENT
    return result


def _longest_dry_spell(rain: pd.Series) -> int:
    dry = np.concatenate(([0], (rain.fillna(0).to_numpy() < 1).astype(int), [0]))
    edges = np.flatnonzero(np.diff(dry))
    run_lengths = edges[1::2] - edges[::2]
    return int(run_lengths.max()) if run_lengths.size else 0


def _no_data(name: str) -> RiskResult:
    result = RiskResult(name=name, level=INSUFFICIENT)
    result.unavailable.append("Both forecast and observed weather are unavailable.")
    return result


def assess_drought(forecast: pd.DataFrame | None, history: pd.DataFrame | None) -> RiskResult:
    name = "Drought risk"
    if forecast is None and history is None:
        return _no_data(name)
    result = RiskResult(name=name, level=INSUFFICIENT, source="Observed and forecast")
    points = 0
    if history is not None and history["rain_mm"].notna().any():
        total = float(history["rain_mm"].sum())
        dry_spell = _longest_dry_spell(history["rain_mm"])
        result.evidence.append(f"Observed: {total:.0f} mm rain in the last 30 days (ends 5 days ago).")
        if total < DROUGHT_OBS_SEVERE_MM:
            points += 2
            result.evidence.append(f"Observed total is below {DROUGHT_OBS_SEVERE_MM} mm (+2 points).")
        elif total < DROUGHT_OBS_MODERATE_MM:
            points += 1
            result.evidence.append(f"Observed total is below {DROUGHT_OBS_MODERATE_MM} mm (+1 point).")
        result.evidence.append(f"Observed longest dry spell: {dry_spell} days.")
        if dry_spell >= DRY_SPELL_DAYS:
            points += 1
            result.evidence.append(f"Dry spell of {DRY_SPELL_DAYS}+ days (+1 point).")
    else:
        result.unavailable.append("Observed 30-day rainfall is unavailable.")

    if forecast is not None and forecast["rain_mm"].notna().any():
        next7 = float(forecast["rain_mm"].sum())
        result.evidence.append(f"Forecast: {next7:.0f} mm rain expected in the next 7 days.")
        if next7 < DROUGHT_FORECAST_DRY_MM:
            points += 1
            result.evidence.append(f"Forecast rain is under {DROUGHT_FORECAST_DRY_MM} mm (+1 point).")
    else:
        result.unavailable.append("7-day rainfall forecast is unavailable.")
    return _finish(result, points)


def assess_heat(forecast: pd.DataFrame | None, history: pd.DataFrame | None) -> RiskResult:
    name = "Heat stress risk"
    if forecast is None and history is None:
        return _no_data(name)
    result = RiskResult(name=name, level=INSUFFICIENT, source="Observed and forecast")
    points = 0
    if forecast is not None and forecast["tmax"].notna().any():
        peak = float(forecast["tmax"].max())
        hot_days = int((forecast["tmax"] >= HEAT_THRESHOLD_DAY_C).sum())
        result.evidence.append(f"Forecast: peak daytime temperature {peak:.1f} °C over the next 7 days.")
        if peak >= HEAT_FORECAST_EXTREME_C:
            points += 2
            result.evidence.append(f"Forecast peak is {HEAT_FORECAST_EXTREME_C} °C or higher (+2 points).")
        elif peak >= HEAT_FORECAST_HIGH_C:
            points += 1
            result.evidence.append(f"Forecast peak is {HEAT_FORECAST_HIGH_C} °C or higher (+1 point).")
        result.evidence.append(f"Forecast days at or above {HEAT_THRESHOLD_DAY_C} °C: {hot_days}.")
    else:
        result.unavailable.append("7-day temperature forecast is unavailable.")

    if history is not None and history["tmax"].notna().any():
        hot_observed = int((history["tmax"] >= HEAT_THRESHOLD_DAY_C).sum())
        result.evidence.append(
            f"Observed: {hot_observed} of the last 30 days reached {HEAT_THRESHOLD_DAY_C} °C or more."
        )
        if hot_observed >= HEAT_OBS_DAYS_MANY:
            points += 2
            result.evidence.append(f"{HEAT_OBS_DAYS_MANY}+ hot days recently (+2 points).")
        elif hot_observed >= HEAT_OBS_DAYS_SOME:
            points += 1
            result.evidence.append(f"{HEAT_OBS_DAYS_SOME}+ hot days recently (+1 point).")
    else:
        result.unavailable.append("Observed 30-day temperatures are unavailable.")
    return _finish(result, points)


def assess_cold(forecast: pd.DataFrame | None) -> RiskResult:
    name = "Cold risk"
    if forecast is None:
        result = RiskResult(name=name, level=INSUFFICIENT, source="Forecast")
        result.unavailable.append("7-day temperature forecast is unavailable.")
        return result
    result = RiskResult(name=name, level=INSUFFICIENT, source="Forecast")
    if forecast["tmin"].isna().all():
        result.unavailable.append("7-day minimum temperature forecast is unavailable.")
        return result
    points = 0
    coldest = float(forecast["tmin"].min())
    result.evidence.append(f"Forecast: lowest minimum temperature {coldest:.1f} °C over the next 7 days.")
    if coldest <= COLD_FORECAST_SEVERE_C:
        points += 2
        result.evidence.append(f"Forecast minimum is {COLD_FORECAST_SEVERE_C} °C or lower (+2 points).")
    elif coldest <= COLD_FORECAST_MILD_C:
        points += 1
        result.evidence.append(f"Forecast minimum is {COLD_FORECAST_MILD_C} °C or lower (+1 point).")
    return _finish(result, points)


def assess_excess_rain(forecast: pd.DataFrame | None, history: pd.DataFrame | None) -> RiskResult:
    name = "Excessive rainfall risk"
    if forecast is None and history is None:
        return _no_data(name)
    result = RiskResult(name=name, level=INSUFFICIENT, source="Observed and forecast")
    points = 0
    if forecast is not None and forecast["rain_mm"].notna().any():
        next7 = float(forecast["rain_mm"].sum())
        heaviest = float(forecast["rain_mm"].max())
        result.evidence.append(f"Forecast: {next7:.0f} mm total over 7 days, heaviest day {heaviest:.0f} mm.")
        if next7 >= RAIN_FORECAST_TOTAL_HIGH_MM:
            points += 2
            result.evidence.append(f"7-day total is {RAIN_FORECAST_TOTAL_HIGH_MM} mm or more (+2 points).")
        elif next7 >= RAIN_FORECAST_TOTAL_MODERATE_MM:
            points += 1
            result.evidence.append(f"7-day total is {RAIN_FORECAST_TOTAL_MODERATE_MM} mm or more (+1 point).")
        if heaviest >= RAIN_VERY_HEAVY_DAY_MM:
            points += 2
            result.evidence.append(f"A forecast day reaches {RAIN_VERY_HEAVY_DAY_MM} mm (+2 points).")
        elif heaviest >= RAIN_HEAVY_DAY_MM:
            points += 1
            result.evidence.append(f"A forecast day reaches {RAIN_HEAVY_DAY_MM} mm (+1 point).")
    else:
        result.unavailable.append("7-day rainfall forecast is unavailable.")

    if history is not None and history["rain_mm"].notna().any():
        total = float(history["rain_mm"].sum())
        result.evidence.append(f"Observed: {total:.0f} mm rain in the last 30 days.")
        if total >= RAIN_OBS_30D_WET_MM:
            points += 1
            result.evidence.append(f"Observed 30-day total is {RAIN_OBS_30D_WET_MM} mm or more (+1 point).")
    else:
        result.unavailable.append("Observed 30-day rainfall is unavailable.")
    return _finish(result, points)


def assess_all_risks(forecast: pd.DataFrame | None, history: pd.DataFrame | None) -> list[RiskResult]:
    return [
        assess_drought(forecast, history),
        assess_heat(forecast, history),
        assess_cold(forecast),
        assess_excess_rain(forecast, history),
    ]
