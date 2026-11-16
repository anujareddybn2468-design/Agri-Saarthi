"""Crop reference profiles.

All numbers are PRELIMINARY general agronomy reference values, not locally validated.
They must be confirmed with local agricultural extension services before real decisions.
"""

CROP_PROFILES = {
    "Rice": {
        "season": "Kharif (monsoon)",
        "ideal_temp_c": (20, 35),
        "heat_stress_c": 38,
        "cold_stress_c": 12,
        "water_need_30d_mm": 150,
        "excess_rain_7d_mm": 150,
        "ph_range": (5.0, 7.5),
        "note": "Needs standing water during much of its growth; poor drainage is tolerated better than in most crops.",
    },
    "Wheat": {
        "season": "Rabi (winter)",
        "ideal_temp_c": (12, 25),
        "heat_stress_c": 32,
        "cold_stress_c": 3,
        "water_need_30d_mm": 50,
        "excess_rain_7d_mm": 60,
        "ph_range": (6.0, 7.5),
        "note": "Heat during grain filling reduces yield; cool, dry harvest weather is preferred.",
    },
    "Maize": {
        "season": "Kharif / spring",
        "ideal_temp_c": (18, 32),
        "heat_stress_c": 35,
        "cold_stress_c": 10,
        "water_need_30d_mm": 70,
        "excess_rain_7d_mm": 80,
        "ph_range": (5.8, 7.5),
        "note": "Sensitive to water stress at flowering and to waterlogging early on.",
    },
    "Ragi (Finger millet)": {
        "season": "Kharif (monsoon)",
        "ideal_temp_c": (20, 30),
        "heat_stress_c": 37,
        "cold_stress_c": 10,
        "water_need_30d_mm": 40,
        "excess_rain_7d_mm": 80,
        "ph_range": (5.5, 7.5),
        "note": "Comparatively drought tolerant; still needs moisture during establishment.",
    },
    "Cotton": {
        "season": "Kharif (monsoon)",
        "ideal_temp_c": (21, 32),
        "heat_stress_c": 38,
        "cold_stress_c": 12,
        "water_need_30d_mm": 60,
        "excess_rain_7d_mm": 80,
        "ph_range": (5.8, 8.0),
        "note": "Heavy rain during flowering and boll opening increases shedding and pest pressure.",
    },
    "Tomato": {
        "season": "Rabi / year-round with irrigation",
        "ideal_temp_c": (18, 27),
        "heat_stress_c": 35,
        "cold_stress_c": 10,
        "water_need_30d_mm": 50,
        "excess_rain_7d_mm": 60,
        "ph_range": (6.0, 7.0),
        "note": "Needs regular moisture; prolonged wet leaves encourage fungal disease.",
    },
}

CROP_NAMES = list(CROP_PROFILES)


def crop_relevance(risk_name: str, crop: str) -> str:
    """Explain, in one sentence, why a climate risk matters for the selected crop."""
    profile = CROP_PROFILES[crop]
    if risk_name == "Drought risk":
        return (
            f"{crop} needs about {profile['water_need_30d_mm']} mm of water over 30 days (preliminary). "
            "Shortfalls reduce growth unless irrigation makes up the gap."
        )
    if risk_name == "Heat stress risk":
        return (
            f"Temperatures above about {profile['heat_stress_c']} °C stress {crop} and can reduce yield "
            "during flowering and grain or fruit development."
        )
    if risk_name == "Cold risk":
        return (
            f"Minimum temperatures below about {profile['cold_stress_c']} °C can slow or damage {crop} "
            "(preliminary limit)."
        )
    if risk_name == "Excessive rainfall risk":
        return (
            f"Around {profile['excess_rain_7d_mm']} mm of rain in a week (preliminary) can waterlog {crop} "
            "fields and raise disease and pest pressure."
        )
    return ""
