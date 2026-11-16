"""Mandi (wholesale market) prices from the data.gov.in daily market price dataset.

Requires a free data.gov.in API key (DATA_GOV_IN_API_KEY). Prices are reported as published;
nothing is estimated or filled in when a market has no record.
"""

from datetime import datetime

import pandas as pd

from agri.http_client import ApiError, get_json

MANDI_URL = "https://api.data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070"
DATASET_NAME = "data.gov.in: Current daily prices of various commodities from various markets (Mandi)"

# App crop name -> commodity name used in the dataset
MANDI_COMMODITIES = {
    "Rice": "Rice",
    "Wheat": "Wheat",
    "Maize": "Maize",
    "Ragi (Finger millet)": "Ragi",
    "Cotton": "Cotton",
    "Tomato": "Tomato",
}


def _number(value) -> float | None:
    try:
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def fetch_mandi_prices(api_key: str, crop: str, state: str, limit: int = 200) -> dict:
    """Return normalised market rows for a crop in a state, newest first.

    Raises ApiError when the service fails. Returns an empty row list when no records match.
    """
    commodity = MANDI_COMMODITIES[crop]
    payload = get_json(
        MANDI_URL,
        {
            "api-key": api_key,
            "format": "json",
            "limit": limit,
            "filters[state]": state,
            "filters[commodity]": commodity,
        },
    )
    records = payload.get("records")
    if not isinstance(records, list):
        raise ApiError("The mandi price response was not in the expected format.")

    rows = []
    for record in records:
        modal = _number(record.get("modal_price"))
        arrival = pd.to_datetime(record.get("arrival_date"), dayfirst=True, errors="coerce")
        if modal is None or pd.isna(arrival):
            continue
        rows.append(
            {
                "market": record.get("market", ""),
                "district": record.get("district", ""),
                "variety": record.get("variety", ""),
                "arrival_date": arrival.normalize(),
                "min_price": _number(record.get("min_price")),
                "max_price": _number(record.get("max_price")),
                "modal_price": modal,
            }
        )
    frame = pd.DataFrame(rows)
    if frame.empty:
        return {"rows": frame, "fetched_at": datetime.now().strftime("%d %b %Y, %H:%M"), "commodity": commodity}
    frame = frame.sort_values(["arrival_date", "market"], ascending=[False, True]).reset_index(drop=True)
    return {"rows": frame, "fetched_at": datetime.now().strftime("%d %b %Y, %H:%M"), "commodity": commodity}


def market_trends(rows: pd.DataFrame) -> pd.DataFrame:
    """Compare each market's latest modal price with its previous reported date.

    The change is only computed when two different dates exist for the same market and variety.
    """
    if rows.empty:
        return rows.assign(previous_price=pd.Series(dtype=float), change_pct=pd.Series(dtype=float))
    ordered = rows.sort_values("arrival_date", ascending=False)
    latest = ordered.drop_duplicates(["market", "variety"], keep="first")
    previous = (
        ordered.groupby(["market", "variety"], sort=False)
        .nth(1)
        .drop_duplicates(["market", "variety"], keep="first")
        .set_index(["market", "variety"])["modal_price"]
    )
    merged = latest.set_index(["market", "variety"]).join(previous.rename("previous_price"))
    merged["change_pct"] = (merged["modal_price"] - merged["previous_price"]) / merged["previous_price"] * 100
    return merged.reset_index()
