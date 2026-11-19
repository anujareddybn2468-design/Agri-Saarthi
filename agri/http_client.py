
"""Shared HTTP helper with retry and rate-limit handling."""

import time

import requests

REQUEST_TIMEOUT = (10, 30)
USER_AGENT = "AgriSaarthi/1.0 (student hackathon prototype)"
MAX_ATTEMPTS = 3
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


class ApiError(Exception):
    """Raised when an external data service cannot provide a usable response."""


def get_json(url: str, params: dict | list | None = None) -> dict:
    for attempt in range(MAX_ATTEMPTS):
        try:
            response = requests.get(
                url,
                params=params,
                timeout=REQUEST_TIMEOUT,
                headers={"User-Agent": USER_AGENT},
            )

        except requests.Timeout as exc:
            if attempt == MAX_ATTEMPTS - 1:
                raise ApiError(
                    "The service did not respond after multiple attempts. "
                    "Try again shortly."
                ) from exc

            time.sleep(attempt + 1)
            continue

        except requests.RequestException as exc:
            if attempt == MAX_ATTEMPTS - 1:
                raise ApiError(
                    "Could not reach the service. Check your internet connection."
                ) from exc

            time.sleep(attempt + 1)
            continue

        if response.status_code == 200:
            try:
                payload = response.json()
            except ValueError as exc:
                raise ApiError(
                    "The service returned a response that could not be read."
                ) from exc

            if not isinstance(payload, dict):
                raise ApiError(
                    "The service returned an unexpected response format."
                )

            return payload

        if response.status_code in RETRYABLE_STATUS_CODES:
            if attempt < MAX_ATTEMPTS - 1:
                retry_after = response.headers.get("Retry-After")
                try:
                    delay = min(float(retry_after), 5) if retry_after else attempt + 1
                except ValueError:
                    delay = attempt + 1

                time.sleep(delay)
                continue

            if response.status_code == 429:
                raise ApiError(
                    "The service is temporarily receiving too many requests. "
                    "Please try again later."
                )

            raise ApiError(
                f"The service is temporarily unavailable "
                f"(HTTP {response.status_code}). Please try again later."
            )

        raise ApiError(
            f"The service returned an error (HTTP {response.status_code})."
        )

    raise ApiError("The service is temporarily unavailable. Try again later.")
