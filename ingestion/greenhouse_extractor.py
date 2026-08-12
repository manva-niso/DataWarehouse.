"""Greenhouse extractor for Job Market Pulse.

Fetches all jobs published on a public Greenhouse board. The board token is a
path parameter, not an API key; secret tokens belong in the local .env file.
"""

import logging
from typing import Any

from .http_utils import get_json

logger = logging.getLogger(__name__)

GREENHOUSE_BOARD_URL = "https://api.greenhouse.io/v1/boards/{board_token}/jobs"


class GreenhouseError(Exception):
    """Base class for Greenhouse extractor failures."""


class GreenhouseConfigError(GreenhouseError):
    """Raised when the board token is missing or empty."""


def fetch_greenhouse_jobs(board_token: str) -> list[dict[str, Any]]:
    """Return all jobs published on the Greenhouse board.

    An empty job list is a valid outcome and is logged, not treated as an
    error. Failures raise typed errors via the shared HTTP helper.
    """
    if not board_token:
        raise GreenhouseConfigError("board_token must not be empty")
    url = GREENHOUSE_BOARD_URL.format(board_token=board_token)
    body = get_json(url)
    jobs = body.get("jobs", []) if isinstance(body, dict) else []
    logger.info("Greenhouse board %s returned %d jobs", board_token, len(jobs))
    return jobs
