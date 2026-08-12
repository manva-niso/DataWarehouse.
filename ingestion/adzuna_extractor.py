"""Adzuna extractor for Job Market Pulse.

Fetches one page of the Adzuna job-search API. The country code is validated
against an allowlist before any request is made, credentials are read from
the local .env file, and 429 responses are retried once after honoring
Retry-After when present.
"""

import logging
import os
import time
from typing import Any

import requests
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

ADZUNA_SEARCH_URL = "https://api.adzuna.com/v1/api/jobs/{country}/search/{page}"

ALLOWED_COUNTRIES = frozenset(
    {
        "at", "au", "be", "br", "ca", "ch", "de", "es", "fr", "gb",
        "in", "it", "lu", "mx", "nl", "nz", "pl", "sg", "us", "za",
    }
)

RESULTS_PER_PAGE = 50
REQUEST_TIMEOUT_SECONDS = 30
RATE_LIMIT_BACKOFF_SECONDS = 30
RATE_LIMIT_RETRIES = 1


class AdzunaError(Exception):
    """Base class for Adzuna extractor failures."""


class AdzunaCountryError(AdzunaError):
    """Raised when a country is not on the Adzuna allowlist."""


class AdzunaConfigError(AdzunaError):
    """Raised when required Adzuna credentials are missing."""


class AdzunaApiError(AdzunaError):
    """Raised for non-200, non-429 Adzuna API responses."""


class AdzunaRateLimitError(AdzunaError):
    """Raised when Adzuna keeps returning 429 after the retry budget."""


class AdzunaParseError(AdzunaError):
    """Raised when a 200 response body is not valid JSON."""


def _adzuna_credentials() -> tuple[str, str]:
    load_dotenv()
    app_id = os.getenv("ADZUNA_APP_ID")
    app_key = os.getenv("ADZUNA_APP_KEY")
    if not app_id or not app_key:
        raise AdzunaConfigError(
            "ADZUNA_APP_ID and ADZUNA_APP_KEY must be set in the local .env file"
        )
    return app_id, app_key


def _retry_after_seconds(response: requests.Response) -> float | None:
    value = response.headers.get("Retry-After")
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        return None


def fetch_adzuna_jobs(query: str, country: str, page: int) -> list[dict[str, Any]]:
    """Return one page of Adzuna job-search results.

    Raises AdzunaCountryError for unsupported countries, AdzunaConfigError
    when credentials are missing, AdzunaApiError for non-200 responses,
    AdzunaParseError for malformed JSON, and AdzunaRateLimitError when 429
    persists after the retry budget.
    """
    if country not in ALLOWED_COUNTRIES:
        raise AdzunaCountryError(
            f"Unsupported Adzuna country {country!r}; allowed: {sorted(ALLOWED_COUNTRIES)}"
        )
    if page < 1:
        raise ValueError("page must be a positive integer")
    app_id, app_key = _adzuna_credentials()
    url = ADZUNA_SEARCH_URL.format(country=country, page=page)
    params = {
        "app_id": app_id,
        "app_key": app_key,
        "what": query,
        "results_per_page": RESULTS_PER_PAGE,
        "content-type": "application/json",
    }
    for attempt in range(RATE_LIMIT_RETRIES + 1):
        response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT_SECONDS)
        if response.status_code == requests.codes.ok:
            try:
                body = response.json()
            except ValueError as exc:
                logger.error("PARSE_ERROR: Adzuna returned a non-JSON body for %s", url)
                raise AdzunaParseError("Adzuna returned a malformed JSON body") from exc
            results = body.get("results", []) if isinstance(body, dict) else []
            logger.info(
                "Adzuna country=%s page=%d query=%r returned %d results",
                country, page, query, len(results),
            )
            return results
        if response.status_code == requests.codes.too_many_requests:
            delay = _retry_after_seconds(response) or RATE_LIMIT_BACKOFF_SECONDS * (attempt + 1)
            logger.warning("Adzuna rate-limited; waiting %.1f seconds before retry", delay)
            time.sleep(delay)
            continue
        raise AdzunaApiError(f"Adzuna API returned HTTP {response.status_code}")
    raise AdzunaRateLimitError(
        f"Adzuna kept returning 429 after {RATE_LIMIT_RETRIES} retries for {url}"
    )
