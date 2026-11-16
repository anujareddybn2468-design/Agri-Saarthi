"""Location search using the Open-Meteo geocoding API."""

from agri.http_client import get_json

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"


def search_places(query: str, max_results: int = 8) -> list[dict]:
    """Return candidate places for a village, town or district name.

    Returns an empty list when nothing matches. Raises ApiError on service failure.
    """
    name = query.split(",")[0].strip()
    if not name:
        return []

    payload = get_json(
        GEOCODING_URL,
        {"name": name, "count": max_results, "language": "en", "format": "json"},
    )
    places = []
    for item in payload.get("results") or []:
        latitude = item.get("latitude")
        longitude = item.get("longitude")
        if latitude is None or longitude is None:
            continue
        places.append(
            {
                "name": item.get("name", name),
                "district": item.get("admin2", ""),
                "state": item.get("admin1", ""),
                "country": item.get("country", ""),
                "lat": float(latitude),
                "lon": float(longitude),
                "timezone": item.get("timezone", "auto"),
            }
        )
    return places


def place_label(place: dict) -> str:
    parts = [place["name"], place["district"], place["state"], place["country"]]
    return ", ".join(part for part in parts if part)
