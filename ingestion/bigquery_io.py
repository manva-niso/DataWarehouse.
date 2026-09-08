"""Shared raw-table writer for Job Market Pulse.

Appends source payload rows to the matching raw_{source} bronze table in the
Databricks warehouse and returns the row count. Empty payloads are a valid
outcome and are logged without touching the warehouse. Each payload dict is
stored as a JSON text string in the STRING payload column.

The function name is kept from the AGENTS.md spec (write_to_bigquery_raw)
although the backend is now Databricks SQL; the spec is the public contract.
"""

import json
import logging
from datetime import datetime, timezone

from dbio import insert_rows

logger = logging.getLogger(__name__)

ALLOWED_RAW_SOURCES = frozenset({"greenhouse", "lever", "rippling", "adzuna", "ashby"})


def write_to_bigquery_raw(source: str, payload: list[dict], run_id: str) -> int:
    """Append raw payload rows to raw_{source} and return the row count."""
    if source not in ALLOWED_RAW_SOURCES:
        raise ValueError(
            f"Unsupported raw source {source!r}; allowed: {sorted(ALLOWED_RAW_SOURCES)}"
        )
    if not payload:
        logger.info("No rows to write for raw_%s in run %s", source, run_id)
        return 0
    rows = [
        {
            "payload": json.dumps(row),
            "run_id": run_id,
            "ingested_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        }
        for row in payload
    ]
    inserted = insert_rows(f"raw_{source}", rows)
    logger.info("Wrote %d rows to raw_%s", inserted, source)
    return inserted
