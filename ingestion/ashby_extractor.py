"""Ashby extractor for Job Market Pulse.

Fetches published postings for an Ashby company board. The board slug is
non-secret and belongs in config/companies.yaml.
"""

import logging
from typing import Any

from .http_utils import get_json

logger = logging.getLogger(__name__)

ASHBY_BOARD_URL = "https://api.ashbyhq.com/posting-api/job-board/{board_slug}"


class AshbyError(Exception):
    """Base class for Ashby extractor failures."""


class AshbyConfigError(AshbyError):
    """Raised when the board slug is missing or empty."""


def fetch_ashby_jobs(board_slug: str) -> list[dict[str, Any]]:
    """Return published postings for an Ashby company.

    An empty job list is a valid outcome and is logged, not treated as an
    error. Failures raise typed errors via the shared HTTP helper.
    """
    if not board_slug:
        raise AshbyConfigError("board_slug must not be empty")
    url = ASHBY_BOARD_URL.format(board_slug=board_slug)
    body = get_json(url)
    jobs = body.get("jobs", []) if isinstance(body, dict) else []
    logger.info("Ashby board %s returned %d jobs", board_slug, len(jobs))
    return jobs
