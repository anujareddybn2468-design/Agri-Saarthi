"""Optional NDVI (vegetation health) interpretation.

No satellite NDVI service is connected. Values are only interpreted when the farmer or an
advisor enters them, and they are always labelled as user-provided.
NDVI ranges from -1 to 1; the bands below are general guidance and not locally validated.
"""

NDVI_BANDS = [
    (0.2, "Sparse or stressed vegetation", "At risk"),
    (0.4, "Moderate vegetation cover", "Watch"),
    (0.6, "Healthy, dense vegetation", "Favourable"),
    (1.01, "Very dense vegetation", "Favourable"),
]


def classify_ndvi(value: float) -> tuple[str, str]:
    """Return (description, status) for an NDVI value between -1 and 1."""
    if not -1 <= value <= 1:
        raise ValueError("NDVI must be between -1 and 1.")
    for upper, description, status in NDVI_BANDS:
        if value < upper:
            return description, status
    return NDVI_BANDS[-1][1], NDVI_BANDS[-1][2]
