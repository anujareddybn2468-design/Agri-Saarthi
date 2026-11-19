
"""Explainable climate risk engine.

Every risk is a transparent points system. Each point is listed in `evidence` so users can see
why a level was reached. Forecast evidence and historical archive evidence are kept separate.
Historical values are Open-Meteo archive/reanalysis estimates, not direct station observations.
All thresholds are PRELIMINARY and must be locally validated before operational use.
"""

from dataclasses import dataclass, field

import pandas as pd

PRELIMINARY_NOTE = "Thresholds are preliminary and have not been locally validated."

LOW = "LOW"
MODERATE = "MODERATE"
HIGH = "HIGH"
CRITICAL = "CRITICAL"
INSUFFICIENT = "INSUFFICIENT DATA"
SEVERITY_ORDER = [LOW, MODERATE, HIGH, CRITICAL]

# Historical archive (last 30 days) rainfall thresholds, mm
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
    source: str = "Forecast and historical archive"


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
    """Return the longest consecutive dry run in the historical archive; missing days break a run."""
    longest = current = 0
    for value in rain:
        if pd.isna(value):
            current = 0
        elif float(value) < 1:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return longest


def _no_data(name: str) -> RiskResult:
    result = RiskResult(name=name, level=INSUFFICIENT)
    result.unavailable.append("Both forecast and historical archive weather data are unavailable.")
    return result


def assess_drought(forecast: pd.DataFrame | None, history: pd.DataFrame | None) -> RiskResult:
    name = "Drought risk"
    if forecast is None and history is None:
        return _no_data(name)
    result = RiskResult(name=name, level=INSUFFICIENT, source="Historical archive and forecast")
    points = 0
    if history is not None and "rain_mm" in history:
        observed = history["rain_mm"].dropna()
        if len(observed) >= 24 and len(history) >= 24:
            total = float(observed.sum() * 30 / len(observed))
            dry_spell = _longest_dry_spell(history["rain_mm"])
            result.evidence.append(
                f"Historical archive estimate: about {total:.0f} mm rain over 30 days, adjusted from {len(observed)} valid daily readings."
            )
            if total < DROUGHT_OBS_SEVERE_MM:
                points += 2
                result.evidence.append(f"Estimated 30-day total is below {DROUGHT_OBS_SEVERE_MM} mm (+2 points).")
            elif total < DROUGHT_OBS_MODERATE_MM:
                points += 1
                result.evidence.append(f"Estimated 30-day total is below {DROUGHT_OBS_MODERATE_MM} mm (+1 point).")
            result.evidence.append(f"Longest consecutive dry spell in archive estimates: {dry_spell} days (missing days break a spell).")
            if dry_spell >= DRY_SPELL_DAYS:
                points += 1
                result.evidence.append(f"Dry spell of {DRY_SPELL_DAYS}+ days (+1 point).")
        else:
            result.unavailable.append("Historical archive rainfall has fewer than 24 valid readings; 30-day drought scoring was skipped.")
    else:
        result.unavailable.append("Historical 30-day archive rainfall is unavailable.")

    if forecast is not None and "rain_mm" in forecast and forecast["rain_mm"].notna().sum() >= 5:
        valid_forecast_days = int(forecast["rain_mm"].notna().sum())
        next7 = float(forecast["rain_mm"].sum() * 7 / valid_forecast_days)
        result.evidence.append(
            f"Forecast: about {next7:.0f} mm over 7 days, adjusted from {valid_forecast_days} valid daily readings."
        )
        if next7 < DROUGHT_FORECAST_DRY_MM:
            points += 1
            result.evidence.append(f"Forecast rain is under {DROUGHT_FORECAST_DRY_MM} mm (+1 point).")
    else:
        result.unavailable.append("7-day rainfall forecast has fewer than 5 valid daily readings or is unavailable.")
    return _finish(result, points)


def assess_heat(forecast: pd.DataFrame | None, history: pd.DataFrame | None) -> RiskResult:
    name = "Heat stress risk"
    if forecast is None and history is None:
        return _no_data(name)
    result = RiskResult(name=name, level=INSUFFICIENT, source="Historical archive and forecast")
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
            f"Historical archive estimate: {hot_observed} of the last 30 days reached {HEAT_THRESHOLD_DAY_C} °C or more."
        )
        if hot_observed >= HEAT_OBS_DAYS_MANY:
            points += 2
            result.evidence.append(f"{HEAT_OBS_DAYS_MANY}+ estimated hot days in the archive (+2 points).")
        elif hot_observed >= HEAT_OBS_DAYS_SOME:
            points += 1
            result.evidence.append(f"{HEAT_OBS_DAYS_SOME}+ estimated hot days in the archive (+1 point).")
    else:
        result.unavailable.append("Historical 30-day archive temperatures are unavailable.")
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
    result = RiskResult(name=name, level=INSUFFICIENT, source="Historical archive and forecast")
    points = 0
    if forecast is not None and "rain_mm" in forecast and forecast["rain_mm"].notna().sum() >= 5:
        valid_forecast = forecast["rain_mm"].dropna()
        valid_days = len(valid_forecast)
        next7 = float(valid_forecast.sum() * 7 / valid_days)
        heaviest = float(valid_forecast.max())
        result.evidence.append(
            f"Forecast: about {next7:.0f} mm over 7 days, adjusted from {valid_days} valid daily readings; "
            f"heaviest valid day {heaviest:.0f} mm."
        )
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
        result.unavailable.append("7-day rainfall forecast has fewer than 5 valid daily readings or is unavailable.")

    if history is not None and "rain_mm" in history and history["rain_mm"].notna().sum() >= 24 and len(history) >= 24:
        observed = history["rain_mm"].dropna()
        total = float(observed.sum() * 30 / len(observed))
        result.evidence.append(
            f"Historical archive estimate: about {total:.0f} mm rain over 30 days, adjusted from {len(observed)} valid daily readings."
        )
        if total >= RAIN_OBS_30D_WET_MM:
            points += 1
            result.evidence.append(f"Estimated 30-day archive total is {RAIN_OBS_30D_WET_MM} mm or more (+1 point).")
    else:
        if history is None or "rain_mm" not in history:
            result.unavailable.append("Historical 30-day archive rainfall is unavailable.")
        else:
            result.unavailable.append("Historical archive rainfall has fewer than 24 valid readings; 30-day excess-rain scoring was skipped.")
    return _finish(result, points)


def assess_all_risks(forecast: pd.DataFrame | None, history: pd.DataFrame | None) -> list[RiskResult]:
    return [
        assess_drought(forecast, history),
        assess_heat(forecast, history),
        assess_cold(forecast),
        assess_excess_rain(forecast, history),
    ]
