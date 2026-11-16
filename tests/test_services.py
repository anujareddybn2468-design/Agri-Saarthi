"""Tests for API response parsing using recorded-shape fixtures, with no network access."""

from datetime import date

import pytest

from agri import geocoding, soil, weather
from agri.http_client import ApiError


def test_geocoding_parses_results(monkeypatch):
    payload = {"results": [{"name": "Baramati", "latitude": 18.15, "longitude": 74.58, "admin2": "Pune", "admin1": "Maharashtra", "country": "India", "timezone": "Asia/Kolkata"}]}
    monkeypatch.setattr(geocoding, "get_json", lambda url, params: payload)
    places = geocoding.search_places("Baramati, Pune")
    assert places[0]["lat"] == 18.15
    assert geocoding.place_label(places[0]) == "Baramati, Pune, Maharashtra, India"


def test_geocoding_returns_empty_when_no_match(monkeypatch):
    monkeypatch.setattr(geocoding, "get_json", lambda url, params: {})
    assert geocoding.search_places("Nowhereville") == []


def test_geocoding_propagates_api_error(monkeypatch):
    def boom(url, params):
        raise ApiError("down")
    monkeypatch.setattr(geocoding, "get_json", boom)
    with pytest.raises(ApiError):
        geocoding.search_places("Pune")


def test_forecast_rejects_incomplete_payload(monkeypatch):
    monkeypatch.setattr(weather, "get_json", lambda url, params: {"current": {}})
    with pytest.raises(ApiError):
        weather.fetch_forecast(18.5, 73.8)


def test_forecast_parses_daily_frame(monkeypatch):
    payload = {
        "current": {"time": "2026-11-16T10:00", "temperature_2m": 30.1, "relative_humidity_2m": 55, "precipitation": 0, "wind_speed_10m": 12},
        "daily": {"time": ["2026-11-16", "2026-11-17"], "temperature_2m_max": [31, 32], "temperature_2m_min": [19, 20], "precipitation_sum": [0, 4.2], "precipitation_probability_max": [5, 40], "wind_speed_10m_max": [15, 18]},
        "timezone": "Asia/Kolkata",
    }
    monkeypatch.setattr(weather, "get_json", lambda url, params: payload)
    result = weather.fetch_forecast(18.5, 73.8)
    assert len(result["daily"]) == 2
    assert result["current"]["temperature_c"] == 30.1


def test_history_window_ends_five_days_before_today(monkeypatch):
    captured = {}

    def fake(url, params):
        captured.update(params)
        return {"daily": {"time": ["2026-10-12"], "temperature_2m_max": [30], "temperature_2m_min": [18], "precipitation_sum": [2]}}

    monkeypatch.setattr(weather, "get_json", fake)
    history = weather.fetch_history(18.5, 73.8, today=date(2026, 11, 16))
    assert captured["end_date"] == "2026-11-11"
    assert captured["start_date"] == "2026-10-13"
    assert len(history) == 1


def test_soil_scales_values_by_unit_factor(monkeypatch):
    payload = {"properties": {"layers": [
        {"name": "phh2o", "unit_measure": {"d_factor": 10, "target_units": "pH"}, "depths": [{"values": {"mean": 65}}]},
        {"name": "clay", "unit_measure": {"d_factor": 10, "target_units": "%"}, "depths": [{"values": {"mean": 250}}]},
        {"name": "sand", "unit_measure": {"d_factor": 10, "target_units": "%"}, "depths": [{"values": {"mean": None}}]},
        {"name": "unknown", "unit_measure": {"d_factor": 1}, "depths": [{"values": {"mean": 1}}]},
    ]}}
    monkeypatch.setattr(soil, "get_json", lambda url, params: payload)
    result = soil.fetch_soil(18.5, 73.8)
    assert result == {
        "phh2o": {"label": "Soil pH", "relevance": soil.SOIL_PROPERTIES["phh2o"][1], "value": 6.5, "unit": "pH"},
        "clay": {"label": "Clay content", "relevance": soil.SOIL_PROPERTIES["clay"][1], "value": 25.0, "unit": "%"},
    }
