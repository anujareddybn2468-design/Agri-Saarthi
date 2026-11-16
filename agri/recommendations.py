"""Rule-based farming recommendations. Each item states the evidence it is based on."""

from agri.crop_risk import AT_RISK, WATCH, Indicator
from agri.risk import RiskResult

GENERAL_NOTE = (
    "These are general, rule-based suggestions from preliminary thresholds. "
    "Confirm with your local agricultural extension officer or Krishi Vigyan Kendra before acting."
)


def build_recommendations(
    risks: list[RiskResult],
    indicators: list[Indicator],
    soil: dict[str, dict],
    ndvi_status: str | None,
) -> list[dict]:
    recs: list[dict] = []
    levels = {risk.name: risk.level for risk in risks}
    statuses = {indicator.name: indicator.status for indicator in indicators}

    if levels.get("Heat stress risk") in ("High", "Moderate") or statuses.get("Heat stress exposure") in (AT_RISK, WATCH):
        recs.append({
            "title": "Protect crops from heat",
            "advice": "Irrigate in the early morning or evening, and consider mulching to keep soil cooler. Avoid fertilizer and spraying during the hottest hours.",
            "basis": "Heat stress risk or forecast peak temperature is at or above the crop's heat limit.",
        })

    if levels.get("Drought risk") in ("High", "Moderate") or statuses.get("Recent rainfall vs crop need") in (AT_RISK, WATCH):
        recs.append({
            "title": "Plan irrigation and conserve moisture",
            "advice": "Schedule irrigation by checking soil moisture before watering. Mulch and weeding reduce water loss from the field.",
            "basis": "Observed rainfall is low relative to the crop's preliminary water need, or the forecast is dry.",
        })

    if levels.get("Excessive rainfall risk") in ("High", "Moderate") or statuses.get("Excess rain exposure") in (AT_RISK, WATCH):
        recs.append({
            "title": "Prepare for heavy rain",
            "advice": "Clear drainage channels before the rain, delay top-dressed fertilizer, and scout for fungal disease after the rain stops.",
            "basis": "Forecast rainfall is high or approaching the crop's preliminary excess level.",
        })

    ph = soil.get("phh2o", {}).get("value")
    if ph is not None:
        if ph < 5.5:
            recs.append({
                "title": "Soil is acidic",
                "advice": "Consider agricultural lime after a soil test confirms the need. Acidic soil can lock up nutrients.",
                "basis": f"Estimated soil pH is {ph:.1f}.",
            })
        elif ph > 8.0:
            recs.append({
                "title": "Soil is alkaline",
                "advice": "Add organic matter such as compost, and confirm with a soil test before using any amendment.",
                "basis": f"Estimated soil pH is {ph:.1f}.",
            })

    soc = soil.get("soc", {}).get("value")
    if soc is not None and soc < 10:
        recs.append({
            "title": "Build up organic matter",
            "advice": "Add farmyard manure or compost before sowing. Organic matter improves water holding and fertility over time.",
            "basis": f"Estimated soil organic carbon is {soc:.1f} g/kg, which is on the low side.",
        })

    sand = soil.get("sand", {}).get("value")
    if sand is not None and sand >= 65:
        recs.append({
            "title": "Irrigate lightly and more often",
            "advice": "Sandy soil drains quickly, so smaller, more frequent irrigations hold water in the root zone better.",
            "basis": f"Estimated sand content is {sand:.0f}%.",
        })

    clay = soil.get("clay", {}).get("value")
    if clay is not None and clay >= 40:
        recs.append({
            "title": "Watch for waterlogging",
            "advice": "Heavy clay drains slowly. Avoid irrigating when the field is already wet and keep drainage channels open.",
            "basis": f"Estimated clay content is {clay:.0f}%.",
        })

    if ndvi_status == AT_RISK:
        recs.append({
            "title": "Scout the field for stress",
            "advice": "Your entered vegetation index suggests sparse or stressed cover. Walk the field to check for pests, nutrient deficiency or water stress.",
            "basis": "User-entered NDVI value falls in the stressed range.",
        })

    if not recs:
        recs.append({
            "title": "No urgent weather or soil alerts",
            "advice": "Continue routine monitoring and follow your usual crop calendar.",
            "basis": "No risk level or indicator reached a warning threshold with the data available.",
        })
    return recs
