"""Regression tests for safe AI and rule-based farmer advisories."""

from agri.advisory import is_valid_advisory
from agri.advisory_rules import rule_advisory


def minimal_facts():
    return {
        "crop": {"name": "Rice"},
        "climate_risks": [
            {"name": name, "level": "LOW", "evidence": [], "unavailable": []}
            for name in ("Drought risk", "Heat stress risk", "Cold risk", "Excessive rainfall risk")
        ],
        "crop_indicators": [
            {"name": "Recent rainfall vs crop need", "status": "Watch", "explanation": ""}
        ],
        "observed_last_30_days": None,
        "current_weather": None,
        "forecast_7_days": [],
        "soil_estimates_0_5cm": None,
        "vegetation_ndvi": None,
        "missing_data": ["Observed rainfall", "Soil properties"],
    }


def test_rule_advisory_handles_missing_history_when_water_indicator_is_watch():
    advisory = rule_advisory(minimal_facts())
    irrigation = next(item for item in advisory["crop_recommendations"] if item["topic"] == "Irrigation")
    assert "rainfall totals are unavailable" in irrigation["advice"]
    assert "topsoil moisture" in irrigation["advice"]


def test_ai_advisory_validation_rejects_malformed_nested_recommendation():
    valid_shape = {
        "farm_status": {"level": "LOW", "summary": "No warning."},
        "top_priority": None,
        "weather_advice": {"expected": "No forecast.", "crop_effect": "Unknown.", "precautions": []},
        "crop_recommendations": [{"topic": "Unexpected", "advice": "Do this", "basis": "Because"}],
        "next_7_days": [],
        "preventive_measures": [],
        "data_confidence": {"measured": [], "forecast": [], "model_estimates": [], "missing": []},
    }
    assert not is_valid_advisory(valid_shape)


def test_ai_advisory_validation_rejects_incomplete_day_plan():
    valid_shape = {
        "farm_status": {"level": "LOW", "summary": "No warning."},
        "top_priority": None,
        "weather_advice": {"expected": "No forecast.", "crop_effect": "Unknown.", "precautions": []},
        "crop_recommendations": [],
        "next_7_days": [{"day": "Today"}],
        "preventive_measures": [],
        "data_confidence": {"measured": [], "forecast": [], "model_estimates": [], "missing": []},
    }
    assert not is_valid_advisory(valid_shape)
