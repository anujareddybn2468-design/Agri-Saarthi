 
"""Soil properties from ISRIC SoilGrids (0-5 cm, mean estimate) with plain-language relevance."""

import math

from agri.http_client import ApiError, get_json

SOILGRIDS_URL = "https://rest.isric.org/soilgrids/v2.0/properties/query"
SOIL_DEPTH = "0-5cm"

# SoilGrids property code -> (display label, why it matters for crops)
SOIL_PROPERTIES = {
    "phh2o": (
        "Soil pH",
        "Controls how easily crops absorb nutrients. Most field crops prefer a near-neutral range.",
    ),
    "clay": (
        "Clay content",
        "High clay holds water and nutrients but can waterlog and drain slowly.",
    ),
    "sand": (
        "Sand content",
        "High sand drains quickly and needs more frequent, lighter irrigation.",
    ),
    "soc": (
        "Soil organic carbon",
        "Indicates organic matter, which improves moisture holding and fertility.",
    ),
    "nitrogen": (
        "Total nitrogen",
        "A rough indicator of natural nitrogen supply. Crops still need planned fertilization.",
    ),
    "cec": (
        "Cation exchange capacity",
        "Measures the soil's ability to hold nutrients such as potassium, calcium and magnesium.",
    ),
}


def fetch_soil(lat: float, lon: float) -> dict[str, dict]:
    """Return available soil properties keyed by SoilGrids code.

    Properties SoilGrids does not provide for this location are omitted, not guessed.
    Invalid individual property values are skipped.
    Raises ApiError when the service fails or its response is incomplete.
    """
    params = [("lon", lon), ("lat", lat), ("depth", SOIL_DEPTH), ("value", "mean")]
    params += [("property", code) for code in SOIL_PROPERTIES]
    payload = get_json(SOILGRIDS_URL, params)

    layers = (payload.get("properties") or {}).get("layers")
    if not isinstance(layers, list):
        raise ApiError("The soil data response was incomplete.")

    results: dict[str, dict] = {}
    for layer in layers:
        if not isinstance(layer, dict):
            continue

        code = layer.get("name")
        if code not in SOIL_PROPERTIES:
            continue

        unit = layer.get("unit_measure") or {}
        if not isinstance(unit, dict):
            unit = {}

        divisor = unit.get("d_factor") or 1

        try:
            divisor = float(divisor)
            raw = layer["depths"][0]["values"]["mean"]
            value = float(raw) / divisor
        except (KeyError, IndexError, TypeError, ValueError, ZeroDivisionError):
            continue

        if not math.isfinite(value) or divisor <= 0:
            continue

        results[code] = {
            "label": SOIL_PROPERTIES[code][0],
            "relevance": SOIL_PROPERTIES[code][1],
            "value": round(value, 2),
            "unit": unit.get("target_units") or "",
        }

    return results
