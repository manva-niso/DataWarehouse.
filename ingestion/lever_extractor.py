"""Lever extractor for Job Market Pulse.

Fetches published postings for a Lever company. mode=json is hard-coded
internally per the project contract. The company slug is non-secret and
belongs in config/companies.yaml.
"""

import logging
from typing import Any

from .http_utils import get_json

logger = logging.getLogger(__name__)

LEVER_POSTINGS_URL = "https://api.lever.co/v0/postings/{company_slug}"


class LeverError(Exception):
    """Base class for Lever extractor failures."""


class LeverConfigError(LeverError):
    """Raised when the company slug is missing or empty."""


def fetch_lever_jobs(company_slug: str) -> list[dict[str, Any]]:
    """Return published postings for a Lever company (mode=json hard-coded).

    An empty posting list is a valid outcome and is logged, not treated as an
    error. Failures raise typed errors via the shared HTTP helper.
    """
    if not company_slug:
        raise LeverConfigError("company_slug must not be empty")
    url = LEVER_POSTINGS_URL.format(company_slug=company_slug)
    body = get_json(url, params={"mode": "json"})
    postings = body if isinstance(body, list) else []
    logger.info("Lever company %s returned %d postings", company_slug, len(postings))
    return postings
