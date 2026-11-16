"""Shared HTTP helper that turns network and API failures into one error type."""

import requests

REQUEST_TIMEOUT = (10, 30)
USER_AGENT = "AgriSaarthi/1.0 (student hackathon prototype)"


class ApiError(Exception):
    """Raised when an external data service cannot provide a usable response."""


def get_json(url: str, params: dict | list | None = None) -> dict:
    try:
        response = requests.get(
            url,
            params=params,
            timeout=REQUEST_TIMEOUT,
            headers={"User-Agent": USER_AGENT},
        )
    except requests.Timeout as exc:
        raise ApiError("The service did not respond in time. Try again shortly.") from exc
    except requests.RequestException as exc:
        raise ApiError("Could not reach the service. Check your internet connection.") from exc

    if response.status_code != 200:
        raise ApiError(f"The service returned an error (HTTP {response.status_code}).")

    try:
        payload = response.json()
    except ValueError as exc:
        raise ApiError("The service returned a response that could not be read.") from exc

    if not isinstance(payload, dict):
        raise ApiError("The service returned an unexpected response format.")
    return payload
