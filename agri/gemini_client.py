"""Gemini client for AI advisory text. Sends only the facts the app collected and expects JSON back."""

import json

import requests

from agri.http_client import ApiError, USER_AGENT

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
DEFAULT_MODEL = "gemini-2.5-flash"
GEMINI_TIMEOUT = (10, 45)


def generate_json(api_key: str, model: str, prompt: str) -> dict:
    """Call Gemini and return the parsed JSON object it produced. Raises ApiError on any failure."""
    try:
        response = requests.post(
            GEMINI_URL.format(model=model),
            headers={
                "x-goog-api-key": api_key,
                "Content-Type": "application/json",
                "User-Agent": USER_AGENT,
            },
            json={
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.2,
                    "responseMimeType": "application/json",
                },
            },
            timeout=GEMINI_TIMEOUT,
        )
    except requests.Timeout as exc:
        raise ApiError("The AI service did not respond in time.") from exc
    except requests.RequestException as exc:
        raise ApiError("Could not reach the AI service.") from exc

    if response.status_code != 200:
        raise ApiError(f"The AI service returned an error (HTTP {response.status_code}).")

    try:
        body = response.json()
        text = body["candidates"][0]["content"]["parts"][0]["text"]
        parsed = json.loads(text)
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise ApiError("The AI service returned a response that could not be read.") from exc

    if not isinstance(parsed, dict):
        raise ApiError("The AI service returned an unexpected response format.")
    return parsed
