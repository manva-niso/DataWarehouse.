"""Rippling extractor for Job Market Pulse.

Two-call source: a list call for the board, then one detail call per job,
concurrency-limited to 5 workers. A single detail failure is logged and does
not abort the remaining details.
"""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from .http_utils import get_json

logger = logging.getLogger(__name__)

RIPPLING_BOARD_URL = "https://ats.rippling.com/api/v2/board/{board_slug}/jobs"
MAX_DETAIL_WORKERS = 5


class RipplingError(Exception):
    """Base class for Rippling extractor failures."""


class RipplingConfigError(RipplingError):
    """Raised when the board slug is missing or empty."""


def _fetch_job_detail(board_slug: str, job_id: str) -> dict[str, Any] | None:
    url = f"{RIPPLING_BOARD_URL.format(board_slug=board_slug)}/{job_id}"
    body = get_json(url)
    if not isinstance(body, dict):
        logger.warning("Rippling detail for job %s returned a non-object payload", job_id)
        return None
    return body


def fetch_rippling_jobs(board_slug: str) -> list[dict[str, Any]]:
    """List jobs on the board, then fetch each detail with max 5 concurrent calls.

    An empty board is a valid outcome and is logged. Detail failures are
    logged and skipped; only the list-call failure aborts the extractor.
    """
    if not board_slug:
        raise RipplingConfigError("board_slug must not be empty")
    list_url = RIPPLING_BOARD_URL.format(board_slug=board_slug)
    details: list[dict[str, Any]] = []
    page = 0
    page_size = 100
    listed = 0
    while True:
        body = get_json(list_url, params={"page": page, "pageSize": page_size})
        if not isinstance(body, dict):
            logger.info("Rippling board %s returned a non-object list response", board_slug)
            break
        raw_jobs = body.get("items", [])
        job_ids = [
            job["id"] for job in raw_jobs
            if isinstance(job, dict) and job.get("id")
        ]
        listed += len(job_ids)
        with ThreadPoolExecutor(max_workers=MAX_DETAIL_WORKERS) as executor:
            futures = {
                executor.submit(_fetch_job_detail, board_slug, job_id): job_id
                for job_id in job_ids
            }
            for future in as_completed(futures):
                job_id = futures[future]
                try:
                    detail = future.result()
                except Exception as exc:  # noqa: BLE001 - isolation by design
                    logger.warning("Rippling detail for job %s failed: %s", job_id, exc)
                    continue
                if detail is not None:
                    details.append(detail)
        total_pages = int(body.get("totalPages", page + 1) or page + 1)
        if page + 1 >= total_pages or not job_ids:
            break
        page += 1
    logger.info(
        "Rippling board %s listed %d jobs and fetched %d details",
        board_slug,
        listed,
        len(details),
    )
    return details
