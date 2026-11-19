 

"""Rule-based advisory engine. Reads the same facts dictionary that is sent to Gemini and
produces the same structure, so the dashboard can display either source identically."""

from datetime import date

from agri.crops import crop_relevance
from agri.risk import CRITICAL, HIGH, INSUFFICIENT, LOW, MODERATE, SEVERITY_ORDER, overall_level

WARNING_LEVELS = (MODERATE, HIGH, CRITICAL)
ACTIONS = {
    "Drought risk": (
        "Irrigate the field where topsoil is dry, and check moisture by hand before each irrigation.",
        "Within the next 1 to 2 days, before the dry spell continues.",
    ),
    "Heat stress risk": (
        "Irrigate early in the morning and avoid spraying or fertilizing in the afternoon.",
        "Before 10 am on the hottest forecast days.",
    ),
    "Cold risk": (
        "Protect young or sensitive plants at night (cover, or light irrigation before the cold night).",
        "Before the coldest forecast night.",
    ),
    "Excessive rainfall risk": (
        "Clear drainage channels, and hold back fertilizer and spraying until the rain passes.",
        "Before the first heavy-rain day in the forecast.",
    ),
}


def _risks_by_name(facts: dict) -> dict[str, dict]:
    return {risk["name"]: risk for risk in facts["climate_risks"]}


def _indicator_status(facts: dict, name: str) -> str | None:
    for item in facts["crop_indicators"]:
        if item["name"] == name:
            return item["status"]
    return None


def _forecast(facts: dict) -> list[dict]:
    return facts["forecast_7_days"] or []


def _first_day(days: list[dict], predicate) -> dict | None:
    return next((day for day in days if predicate(day)), None)


def _day_label(index: int, iso_date: str) -> str:
    if index == 0:
        return f"Today ({date.fromisoformat(iso_date):%d %b})"
    return f"Day {index + 1} ({date.fromisoformat(iso_date):%d %b})"


def _farm_status(facts: dict, risks: dict[str, dict]) -> dict:
    level = overall_level([risk["level"] for risk in risks.values()])
    if level == INSUFFICIENT:
        return {"level": level, "summary": "There is not enough weather data to rate climate risk for this farm."}
    if level == LOW:
        return {"level": level, "summary": "No climate risk reached a warning level in the data available."}
    worst = max(
        (risk for risk in risks.values() if risk["level"] in WARNING_LEVELS),
        key=lambda risk: SEVERITY_ORDER.index(risk["level"]),
    )
    first_evidence = worst["evidence"][0] if worst["evidence"] else "See the climate risk tab for details."
    return {
        "level": level,
        "summary": f"Highest concern: {worst['name'].lower()} is {worst['level']}. {first_evidence}",
    }


def _top_priority(facts: dict, risks: dict[str, dict]) -> dict | None:
    warnings = [risk for risk in risks.values() if risk["level"] in WARNING_LEVELS]
    if not warnings:
        if overall_level([risk["level"] for risk in risks.values()]) == INSUFFICIENT:
            return None
        return {
            "action": "Continue routine monitoring of the field.",
            "why": "No climate risk reached a warning level in the data available.",
            "when": "Check the field and the forecast again this week.",
        }
    worst = max(warnings, key=lambda risk: SEVERITY_ORDER.index(risk["level"]))
    action, default_when = ACTIONS[worst["name"]]
    days = _forecast(facts)
    when = default_when
    if worst["name"] == "Excessive rainfall risk":
        heavy = _first_day(days, lambda day: (day["rain_mm"] or 0) >= 64.5)
        if heavy:
            when = f"Before {date.fromisoformat(heavy['date']):%d %b} ({heavy['rain_mm']} mm forecast)."
    if worst["name"] == "Cold risk":
        coldest = _first_day(days, lambda day: (day["tmin_c"] or 99) <= 5)
        if coldest:
            when = f"Before the night of {date.fromisoformat(coldest['date']):%d %b} ({coldest['tmin_c']} °C forecast minimum)."
    why = f"{worst['name']} is {worst['level']} for {facts['crop']['name']}. " + (
        worst["evidence"][0] if worst["evidence"] else ""
    )
    return {"action": action, "why": why.strip(), "when": when}


def _weather_advice(facts: dict, risks: dict[str, dict]) -> dict:
    days = _forecast(facts)
    crop = facts["crop"]["name"]
    if not days:
        return {
            "expected": "The 7-day forecast is unavailable, so the coming week's weather cannot be described.",
            "crop_effect": "Crop effects cannot be assessed without a forecast.",
            "precautions": ["Check the national weather service or a local forecast before field work."],
        }
    rain_total = sum(day["rain_mm"] or 0 for day in days)
    highs = [day["tmax_c"] for day in days if day["tmax_c"] is not None]
    lows = [day["tmin_c"] for day in days if day["tmin_c"] is not None]
    expected = (
        f"Forecast for the next 7 days: {rain_total:.0f} mm rain in total"
        + (f", highs up to {max(highs):.1f} °C" if highs else "")
        + (f", lows down to {min(lows):.1f} °C" if lows else "")
        + "."
    )
    stressed = [risk for risk in risks.values() if risk["level"] in WARNING_LEVELS]
    if stressed:
        worst = max(stressed, key=lambda risk: SEVERITY_ORDER.index(risk["level"]))
        crop_effect = crop_relevance(worst["name"], crop)
    else:
        crop_effect = f"No major weather stress is forecast for {crop} at the preliminary limits."
    precautions = [ACTIONS[risk["name"]][0] for risk in stressed]
    if not precautions:
        precautions = ["Keep a daily check of the forecast while the crop is in the field."]
    return {"expected": expected, "crop_effect": crop_effect, "precautions": precautions}


def _crop_recommendations(facts: dict, risks: dict[str, dict]) -> list[dict]:
    recs = []
    crop = facts["crop"]["name"]
    history = facts["observed_last_30_days"]
    water = _indicator_status(facts, "Recent rainfall vs crop need")
    if risks["Drought risk"]["level"] in WARNING_LEVELS or water in ("At risk", "Watch"):
        if history and history.get("rain_total_mm") is not None:
            advice = (
                f"Check field moisture and irrigate {crop} only where needed to address the rainfall gap. "
                f"Historical archive rainfall estimate was {history['rain_total_mm']:.0f} mm over the last 30 days."
            )
            basis = "Historical archive rainfall estimate compared with a preliminary crop water need."
        else:
            advice = (
                f"Check topsoil moisture by hand. If the root zone is dry and water is available, "
                f"plan irrigation for {crop}; recent rainfall totals are unavailable."
            )
            basis = "Rainfall totals are unavailable; recommendation is conditional on a field moisture check."
        recs.append({"topic": "Irrigation", "advice": advice, "basis": basis})
    elif history:
        recs.append({
            "topic": "Irrigation",
            "advice": "Recent rain has been close to the crop's preliminary need. Irrigate only where topsoil is dry.",
            "basis": "Historical archive rainfall estimate and a preliminary crop water need.",
        })
    else:
        recs.append({
            "topic": "Irrigation",
            "advice": "Historical rainfall archive data is unavailable, so irrigation timing cannot be based on it. Check topsoil moisture by hand.",
            "basis": "Historical archive rainfall unavailable.",
        })

    moisture = facts["current_weather"]["soil_moisture_model_pct"] if facts["current_weather"] else None
    if moisture is None:
        recs.append({
            "topic": "Soil moisture",
            "advice": "No soil moisture estimate is available. Use a hand check (squeeze a handful of soil) before irrigating.",
            "basis": "Soil moisture model value unavailable.",
        })
    else:
        if moisture < 15:
            advice = f"The model estimates topsoil moisture is low at {moisture:.0f}%. Irrigate after a hand check."
        elif moisture > 35:
            advice = f"The model estimates topsoil moisture is high at {moisture:.0f}%. Hold irrigation until the field drains."
        else:
            advice = f"The model estimates topsoil moisture is moderate at {moisture:.0f}%. Recheck after the next rain."
        recs.append({
            "topic": "Soil moisture",
            "advice": advice,
            "basis": "Model estimate from the weather service, not a field measurement. Thresholds are preliminary.",
        })

    recs.append(_nutrient_advice(facts))

    rain_flag = risks["Excessive rainfall risk"]["level"] in WARNING_LEVELS
    humidity = facts["current_weather"]["humidity_pct"] if facts["current_weather"] else None
    wet_days = sum(1 for day in _forecast(facts) if (day["rain_mm"] or 0) >= 1)
    if rain_flag or (humidity is not None and humidity >= 85) or wet_days >= 3:
        evidence = []
        if rain_flag:
            evidence.append("excessive rainfall risk is " + risks["Excessive rainfall risk"]["level"].lower())
        if humidity is not None and humidity >= 85:
            evidence.append(f"current humidity is {humidity:.0f}%")
        if wet_days >= 3:
            evidence.append(f"{wet_days} forecast days have at least 1 mm of rain")
        recs.append({
            "topic": "Pest and disease",
            "advice": f"Scout {crop} after wet spells for fungal leaf disease and pest build-up, and act early if you see it.",
            "basis": "Supported by: " + "; ".join(evidence) + ".",
        })

    if rain_flag or risks["Cold risk"]["level"] in WARNING_LEVELS or risks["Heat stress risk"]["level"] in WARNING_LEVELS:
        stressed = [name for name in ("Excessive rainfall risk", "Cold risk", "Heat stress risk") if risks[name]["level"] in WARNING_LEVELS]
        recs.append({
            "topic": "Harvest or sowing",
            "advice": "Plan field work around the forecast: delay harvesting, drying or sowing on the worst days, and avoid sowing into waterlogged soil.",
            "basis": "Supported by: " + ", ".join(name.lower() for name in stressed) + " in the forecast.",
        })
    return recs


def _nutrient_advice(facts: dict) -> dict:
    soil = facts["soil_estimates_0_5cm"]
    if not soil:
        return {
            "topic": "Nutrients",
            "advice": "Soil data is unavailable, so nutrient advice cannot be based on it. Get a soil test before fertilizing.",
            "basis": "Soil properties unavailable.",
        }
    points = []
    ph = soil.get("phh2o", {}).get("value")
    if ph is not None and ph < 5.5:
        points.append(f"Estimated soil pH is {ph:.1f}, which is acidic. Lime may help after a soil test confirms it.")
    if ph is not None and ph > 8.0:
        points.append(f"Estimated soil pH is {ph:.1f}, which is alkaline. Add organic matter and confirm with a soil test.")
    soc = soil.get("soc", {}).get("value")
    if soc is not None and soc < 10:
        points.append(f"Estimated organic carbon is {soc:g} g/kg, which is low. Add compost or farmyard manure before sowing.")
    if not points:
        points.append("Soil estimates do not flag a clear nutrient problem. Confirm with a soil test before applying fertilizer.")
    return {
        "topic": "Nutrients",
        "advice": " ".join(points),
        "basis": "SoilGrids model estimates for the 0-5 cm layer, not laboratory tests.",
    }


def _next_7_days(facts: dict) -> list[dict]:
    plan = []
    for index, day in enumerate(_forecast(facts)):
        rain = day["rain_mm"] or 0
        tmax = day["tmax_c"]
        tmin = day["tmin_c"]
        if rain >= 64.5:
            action = f"Heavy rain expected ({rain:g} mm). Clear drains and delay fertilizer or spraying."
        elif tmin is not None and tmin <= 5:
            action = f"Cold night expected (minimum {tmin:g} °C). Protect young or sensitive plants."
        elif tmax is not None and tmax >= 38:
            action = f"Very hot day ({tmax:g} °C). Irrigate early morning and avoid midday field work."
        elif rain < 1 and tmax is not None and tmax >= 35:
            action = f"Hot and dry ({tmax:g} °C, no rain). Check topsoil moisture and irrigate if it is dry."
        elif rain >= 10:
            action = f"Rain expected ({rain:g} mm). Delay fertilizer and check drains."
        else:
            action = "Routine day. Walk the field and check for water stress and pests."
        plan.append({"day": _day_label(index, day["date"]), "action": action})
    return plan


def _preventive(risks: dict[str, dict]) -> list[str]:
    items = [ACTIONS[risk["name"]][0] for risk in risks.values() if risk["level"] in WARNING_LEVELS]
    items.append("Confirm timing with your local agriculture office or Krishi Vigyan Kendra before acting.")
    return items


def _data_confidence(facts: dict, risks: dict[str, dict]) -> dict:
    historical = []
    if facts["observed_last_30_days"]:
        historical.append(
            f"Historical rainfall and temperature estimates for "
            f"{facts['observed_last_30_days']['period']} (Open-Meteo archive/reanalysis)."
        )
    forecast = []
    if facts["current_weather"]:
        forecast.append("Current conditions (Open-Meteo weather model, not a station reading).")
    if facts["forecast_7_days"]:
        forecast.append("7-day forecast (Open-Meteo weather model).")
    estimates = []
    if facts["soil_estimates_0_5cm"]:
        estimates.append("Soil properties (ISRIC SoilGrids, 0-5 cm, 250 m grid estimate).")
    if facts["current_weather"] and facts["current_weather"]["soil_moisture_model_pct"] is not None:
        estimates.append("Topsoil moisture (weather model estimate).")
    missing = list(facts["missing_data"])
    for risk in risks.values():
        missing.extend(risk["unavailable"])
    return {
        # Keep the existing key so the dashboard continues to work.
        "measured": historical or ["No historical archive weather data was available."],
        "forecast": forecast or ["No forecast was available."],
        "model_estimates": estimates or ["No model-based estimates were available."],
        "missing": list(dict.fromkeys(missing)) or ["Nothing material is missing."],
    }


def rule_advisory(facts: dict) -> dict:
    risks = _risks_by_name(facts)
    return {
        "farm_status": _farm_status(facts, risks),
        "top_priority": _top_priority(facts, risks),
        "weather_advice": _weather_advice(facts, risks),
        "crop_recommendations": _crop_recommendations(facts, risks),
        "next_7_days": _next_7_days(facts),
        "preventive_measures": _preventive(risks),
        "data_confidence": _data_confidence(facts, risks),
    }
