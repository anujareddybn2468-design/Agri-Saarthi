"""Weather data from Open-Meteo: live conditions, 7-day forecast and recent observed history."""

from datetime import date, timedelta

import pandas as pd

from agri.http_client import ApiError, get_json

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"

# Archive (reanalysis) data lags real time by several days.
ARCHIVE_LAG_DAYS = 5
HISTORY_DAYS = 30


def fetch_forecast(lat: float, lon: float) -> dict:
    """Return current conditions and a 7-day daily forecast. Raises ApiError on failure."""
    payload = get_json(
        FORECAST_URL,
        {
            "latitude": lat,
            "longitude": lon,
            "timezone": "auto",
            "current": "temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m",
            "daily": ",".join(
                [
                    "temperature_2m_max",
                    "temperature_2m_min",
                    "precipitation_sum",
                    "precipitation_probability_max",
                    "wind_speed_10m_max",
                ]
            ),
            "hourly": "soil_moisture_0_to_7cm",
            "forecast_days": 7,
            "wind_speed_unit": "kmh",
        },
    )
    current = payload.get("current")
    daily = payload.get("daily")
    if not isinstance(current, dict) or not isinstance(daily, dict) or "time" not in daily:
        raise ApiError("The weather forecast response was incomplete.")
    soil_moisture = _current_soil_moisture(payload, current.get("time"))

    daily_frame = pd.DataFrame(
        {
            "date": pd.to_datetime(daily["time"]),
            "tmax": daily.get("temperature_2m_max"),
            "tmin": daily.get("temperature_2m_min"),
            "rain_mm": daily.get("precipitation_sum"),
            "rain_prob_pct": daily.get("precipitation_probability_max"),
            "wind_max_kmh": daily.get("wind_speed_10m_max"),
        }
    )
    return {
        "current": {
            "time": current.get("time"),
            "temperature_c": current.get("temperature_2m"),
            "humidity_pct": current.get("relative_humidity_2m"),
            "rain_mm": current.get("precipitation"),
            "wind_kmh": current.get("wind_speed_10m"),
            "soil_moisture_m3m3": soil_moisture,
            "units": payload.get("current_units", {}),
        },
        "daily": daily_frame,
        "timezone": payload.get("timezone", ""),
    }


def _current_soil_moisture(payload: dict, current_time: str | None) -> float | None:
    """Model-estimated soil moisture (m3/m3) for the current hour, or None if not provided."""
    hourly = payload.get("hourly")
    if not isinstance(hourly, dict) or current_time is None:
        return None
    times = hourly.get("time") or []
    values = hourly.get("soil_moisture_0_to_7cm") or []
    if current_time not in times or len(values) != len(times):
        return None
    value = values[times.index(current_time)]
    return None if value is None else float(value)


def fetch_history(lat: float, lon: float, today: date | None = None) -> pd.DataFrame:
    """Return the last 30 days of observed daily rainfall and temperature.

    The window ends ARCHIVE_LAG_DAYS before today because the archive is not yet complete.
    """
    today = today or date.today()
    end = today - timedelta(days=ARCHIVE_LAG_DAYS)
    start = end - timedelta(days=HISTORY_DAYS - 1)
    payload = get_json(
        ARCHIVE_URL,
        {
            "latitude": lat,
            "longitude": lon,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
            "timezone": "auto",
        },
    )
    daily = payload.get("daily")
    if not isinstance(daily, dict) or "time" not in daily:
        raise ApiError("The historical weather response was incomplete.")

    return pd.DataFrame(
        {
            "date": pd.to_datetime(daily["time"]),
            "tmax": daily.get("temperature_2m_max"),
            "tmin": daily.get("temperature_2m_min"),
            "rain_mm": daily.get("precipitation_sum"),
        }
    )
