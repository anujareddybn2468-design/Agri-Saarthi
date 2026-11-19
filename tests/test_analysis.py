"""Unit tests for the analysis layer. Inputs here are synthetic test fixtures, not app data."""

import pandas as pd
import pytest

from agri.crop_risk import AT_RISK, FAVOURABLE, UNKNOWN, WATCH, assess_crop
from agri.ndvi import classify_ndvi
from agri.recommendations import build_recommendations
from agri.risk import HIGH, LOW, INSUFFICIENT, assess_all_risks, assess_drought, assess_excess_rain, assess_heat


def make_forecast(rain, tmax, tmin=20.0):
    n = len(rain)
    return pd.DataFrame({
        "date": pd.date_range("2026-01-01", periods=n),
        "tmax": [tmax] * n if not isinstance(tmax, list) else tmax,
        "tmin": [tmin] * n,
        "rain_mm": rain,
    })


def make_history(rain, tmax=30.0):
    n = len(rain)
    return pd.DataFrame({
        "date": pd.date_range("2025-12-01", periods=n),
        "tmax": [tmax] * n if not isinstance(tmax, list) else tmax,
        "tmin": [18.0] * n,
        "rain_mm": rain,
    })


def test_drought_high_when_dry_observed_and_forecast():
    history = make_history([0.0] * 30)
    forecast = make_forecast([0.0] * 7, 30)
    risk = assess_drought(forecast, history)
    assert risk.level == HIGH
    assert risk.points >= 3


def test_drought_low_with_healthy_rainfall():
    history = make_history([10.0] * 30)
    forecast = make_forecast([8.0] * 7, 28)
    assert assess_drought(forecast, history).level == LOW


def test_drought_insufficient_when_no_data():
    risk = assess_drought(None, None)
    assert risk.level == INSUFFICIENT
    assert risk.unavailable


def test_heat_high_with_extreme_forecast_and_hot_history():
    forecast = make_forecast([0.0] * 7, 41)
    history = make_history([0.0] * 30, tmax=36.0)
    assert assess_heat(forecast, history).level == HIGH


def test_heat_low_when_mild():
    forecast = make_forecast([0.0] * 7, 26)
    history = make_history([0.0] * 30, tmax=27.0)
    assert assess_heat(forecast, history).level == LOW


def test_excess_rain_high_with_heavy_forecast():
    forecast = make_forecast([20, 70, 40, 10, 5, 0, 0], 28)
    history = make_history([10.0] * 30)
    risk = assess_excess_rain(forecast, history)
    assert risk.level == HIGH
    assert any("heaviest" in line.lower() or "64.5" in line or "mm total" in line for line in risk.evidence)


def test_all_risks_return_three_named_results():
    names = [risk.name for risk in assess_all_risks(make_forecast([0.0] * 7, 30), make_history([5.0] * 30))]
    assert names == ["Drought risk", "Heat stress risk", "Cold risk", "Excessive rainfall risk"]


def test_crop_indicators_flag_heat_for_wheat():
    forecast = make_forecast([0.0] * 7, 36, tmin=22)
    history = make_history([60.0] * 30)
    indicators = {i.name: i for i in assess_crop("Wheat", forecast, history, ph=6.8)}
    assert indicators["Heat stress exposure"].status == AT_RISK
    assert indicators["Soil pH suitability"].status == FAVOURABLE


def test_crop_indicators_unknown_without_data():
    indicators = {i.name: i for i in assess_crop("Tomato", None, None, ph=None)}
    assert indicators["Soil pH suitability"].status == UNKNOWN
    assert indicators["Recent rainfall vs crop need"].status == UNKNOWN


def test_crop_water_indicator_watch_when_partial_need():
    history = make_history([3.0] * 30)  # 90 mm vs Rice need of 150 mm
    indicators = {i.name: i for i in assess_crop("Rice", None, history, ph=6.0)}
    assert indicators["Recent rainfall vs crop need"].status == WATCH


@pytest.mark.parametrize(
    "value,expected",
    [(0.1, "At risk"), (0.3, "Watch"), (0.5, "Favourable"), (0.8, "Favourable")],
)
def test_ndvi_status_bands(value, expected):
    assert classify_ndvi(value)[1] == expected


def test_ndvi_rejects_out_of_range():
    with pytest.raises(ValueError):
        classify_ndvi(1.5)


def test_recommendations_fall_back_when_nothing_flagged():
    recs = build_recommendations([], [], {}, None)
    assert recs[0]["title"] == "No urgent weather or soil alerts"


def test_recommendations_flag_acidic_soil():
    recs = build_recommendations([], [], {"phh2o": {"value": 4.9}}, None)
    assert any(rec["title"] == "Soil is acidic" for rec in recs)


def test_longest_dry_spell_counts_longest_run():
    from agri.risk import _longest_dry_spell

    rain = pd.Series([0.0, 0.0, 0.0, 5.0, 0.0, 0.0, 0.0, 0.0, 0.0, 2.0])
    assert _longest_dry_spell(rain) == 5
    assert _longest_dry_spell(pd.Series([3.0, 4.0])) == 0


def test_missing_rainfall_breaks_dry_spell_instead_of_counting_as_dry():
    from agri.risk import _longest_dry_spell

    rain = pd.Series([0.0] * 8 + [None] + [0.0] * 8)
    assert _longest_dry_spell(rain) == 8


def test_drought_skips_observed_scoring_when_history_is_too_incomplete():
    history = make_history([0.0] * 10 + [None] * 20)
    forecast = make_forecast([8.0] * 7, 30)
    risk = assess_drought(forecast, history)
    assert risk.points == 0
    assert any("fewer than 24 valid readings" in item for item in risk.unavailable)


def test_crop_water_indicator_unknown_when_rainfall_history_is_incomplete():
    history = make_history([0.0] * 10 + [None] * 20)
    indicators = {i.name: i for i in assess_crop("Rice", None, history, ph=6.0)}
    assert indicators["Recent rainfall vs crop need"].status == UNKNOWN


def test_excess_rain_forecast_adjusts_for_missing_days():
    forecast = make_forecast([20.0, 20.0, 20.0, 20.0, 20.0, None, None], 28)
    risk = assess_excess_rain(forecast, None)
    assert any("adjusted from 5 valid daily readings" in line for line in risk.evidence)
    assert any("140 mm over 7 days" in line for line in risk.evidence)


def test_excess_rain_skips_forecast_when_too_few_days_are_valid():
    forecast = make_forecast([100.0, None, None, None, None, None, None], 28)
    risk = assess_excess_rain(forecast, None)
    assert risk.level == INSUFFICIENT
    assert any("fewer than 5 valid daily readings" in item for item in risk.unavailable)


def test_excess_rain_skips_observed_scoring_when_history_is_incomplete():
    history = make_history([20.0] * 10 + [None] * 20)
    risk = assess_excess_rain(None, history)
    assert risk.level == INSUFFICIENT
    assert any("fewer than 24 valid readings" in item for item in risk.unavailable)


def test_crop_excess_rain_is_unknown_with_incomplete_forecast():
    forecast = make_forecast([100.0, None, None, None, None, None, None], 28)
    indicators = {i.name: i for i in assess_crop("Rice", forecast, None, ph=6.0)}
    assert indicators["Excess rain exposure"].status == UNKNOWN
