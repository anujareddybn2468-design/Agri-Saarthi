"""Chooses the advisory source: Gemini when configured and valid, otherwise the rule-based engine."""

import json
import re
from collections.abc import Callable

from agri.advisory_facts import build_prompt
from agri.advisory_rules import rule_advisory
from agri.gemini_client import generate_json
from agri.http_client import ApiError

SOURCE_GEMINI = "Gemini AI"
SOURCE_RULES = "Rule-based engine"

_REQUIRED_STRINGS = {
    "farm_status": ("level", "summary"),
    "weather_advice": ("expected", "crop_effect"),
}
_REQUIRED_LISTS = ("crop_recommendations", "next_7_days", "preventive_measures")
_CONFIDENCE_KEYS = ("measured", "forecast", "model_estimates", "missing")
_QUANTITY = re.compile(r"(-?\d+(?:\.\d+)?)\s*(?:°C|mm|%|km/h)")


def _numbers_in(value: object) -> list[float]:
    if isinstance(value, bool):
        return []
    if isinstance(value, (int, float)):
        return [float(value)]
    if isinstance(value, dict):
        return [number for item in value.values() for number in _numbers_in(item)]
    if isinstance(value, list):
        return [number for item in value for number in _numbers_in(item)]
    return []


def cites_only_known_quantities(advisory: dict, facts: dict) -> bool:
    """True when every temperature, rain, humidity or wind figure in the text exists in the facts."""
    known = _numbers_in(facts)
    text = json.dumps(advisory, ensure_ascii=False)
    for match in _QUANTITY.finditer(text):
        value = float(match.group(1))
        if not any(abs(value - number) < 0.06 for number in known):
            return False
    return True


def is_valid_advisory(data: object) -> bool:
    if not isinstance(data, dict):
        return False
    for section, keys in _REQUIRED_STRINGS.items():
        block = data.get(section)
        if not isinstance(block, dict) or not all(isinstance(block.get(key), str) for key in keys):
            return False
    priority = data.get("top_priority")
    if priority is not None and not (
        isinstance(priority, dict) and all(isinstance(priority.get(key), str) for key in ("action", "why", "when"))
    ):
        return False
    if not isinstance(data["weather_advice"].get("precautions"), list):
        return False
    for key in _REQUIRED_LISTS:
        if not isinstance(data.get(key), list):
            return False

    # Validate every nested item before the UI renders it. A malformed AI response
    # must fall back to the deterministic rules rather than breaking the app.
    for item in data["crop_recommendations"]:
        if not isinstance(item, dict) or not all(
            isinstance(item.get(field), str)
            for field in ("topic", "advice", "basis")
        ):
            return False
        if item["topic"] not in {
            "Irrigation", "Soil moisture", "Nutrients",
            "Pest and disease", "Harvest or sowing",
        }:
            return False
    for item in data["next_7_days"]:
        if not isinstance(item, dict) or not all(
            isinstance(item.get(field), str) for field in ("day", "action")
        ):
            return False
    if not all(isinstance(item, str) for item in data["preventive_measures"]):
        return False

    confidence = data.get("data_confidence")
    if not isinstance(confidence, dict) or not all(isinstance(confidence.get(key), list) for key in _CONFIDENCE_KEYS):
        return False
    return True


def generate_advisory(
    facts: dict,
    api_key: str | None,
    model: str,
    call_gemini: Callable[[str, str, str], dict] = generate_json,
) -> dict:
    """Return {"source", "note", "advisory"}. Never raises for AI failures."""
    rules = rule_advisory(facts)
    if not api_key:
        return {
            "source": SOURCE_RULES,
            "note": "Gemini AI is not configured, so this advisory comes from the rule-based engine.",
            "advisory": rules,
        }
    try:
        candidate = call_gemini(api_key, model, build_prompt(facts))
    except ApiError as exc:
        return {
            "source": SOURCE_RULES,
            "note": f"Gemini AI could not be used ({exc}) so the rule-based engine is shown.",
            "advisory": rules,
        }
    if not is_valid_advisory(candidate):
        return {
            "source": SOURCE_RULES,
            "note": "Gemini AI returned an incomplete answer, so the rule-based engine is shown.",
            "advisory": rules,
        }
    if not cites_only_known_quantities(candidate, facts):
        return {
            "source": SOURCE_RULES,
            "note": "Gemini AI quoted a figure that is not in the collected data, so the rule-based engine is shown.",
            "advisory": rules,
        }
    return {
        "source": SOURCE_GEMINI,
        "note": "Written by Gemini AI from the data listed in the data confidence section.",
        "advisory": candidate,
    }
