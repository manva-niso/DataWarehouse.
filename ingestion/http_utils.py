"""Shared HTTP helpers for source extractors.

Centralizes the 429 retry policy (respect Retry-After when present, else
backoff, retry once, then fail gracefully) and malformed-JSON handling so
every source behaves consistently.
"""

import logging
import time
from typing import Any

import requests

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SECONDS = 30
BACKOFF_SECONDS = 30
RATE_LIMIT_RETRIES = 1


class SourceHttpError(Exception):
    """Raised for non-200, non-429 responses."""


class SourceRateLimitError(Exception):
    """Raised when 429 persists after the retry budget."""


class SourceParseError(Exception):
    """Raised when a 200 response body is not valid JSON."""


def _retry_after_seconds(response: requests.Response) -> float | None:
    value = response.headers.get("Retry-After")
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        return None


def get_json(
    url: str,
    *,
    params: dict | None = None,
    headers: dict | None = None,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> Any:
    """GET url and return parsed JSON with one 429 retry honoring Retry-After."""
    for attempt in range(RATE_LIMIT_RETRIES + 1):
        response = requests.get(url, params=params, headers=headers, timeout=timeout)
        if response.status_code == requests.codes.ok:
            try:
                return response.json()
            except ValueError as exc:
                logger.error("PARSE_ERROR: non-JSON body from %s", url)
                raise SourceParseError(f"Malformed JSON body from {url}") from exc
        if response.status_code == requests.codes.too_many_requests:
            delay = _retry_after_seconds(response) or BACKOFF_SECONDS * (attempt + 1)
            logger.warning("Rate-limited on %s; waiting %.1f seconds", url, delay)
            time.sleep(delay)
            continue
        raise SourceHttpError(f"HTTP {response.status_code} from {url}")
    raise SourceRateLimitError(
        f"HTTP 429 persisted after {RATE_LIMIT_RETRIES} retries for {url}"
    )
