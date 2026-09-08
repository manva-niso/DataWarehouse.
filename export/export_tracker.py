"""Excel export and application tracking for Job Market Pulse.

export_tracker_to_excel reads mart_application_tracker and writes a .xlsx in
write-only mode. Zero rows still produce a valid workbook with headers.
mark_application maintains the manual applications table with validation.
Reads and writes go through dbio to the Databricks warehouse.
"""

import logging
from datetime import date, datetime, timezone
from pathlib import Path

from dbio import query_rows, run_sql
from openpyxl import Workbook

logger = logging.getLogger(__name__)

ALLOWED_STATUSES = ("SAVED", "APPLIED", "INTERVIEW", "OFFER", "REJECTED")

COLUMNS = [
    ("posting_id", "Posting ID"),
    ("company_name", "Company"),
    ("job_title", "Job Title"),
    ("location", "Location"),
    ("date_posted", "Date Posted"),
    ("closing_date", "Closing Date"),
    ("date_applied", "Date Applied"),
    ("is_likely_closed", "Likely Closed"),
    ("last_seen_at", "Last Seen"),
]


class PostingNotFoundError(Exception):
    """Raised when mark_application receives an unknown posting_id."""


class FutureDateError(ValueError):
    """Raised when mark_application receives a date in the future."""


class InvalidStatusError(ValueError):
    """Raised when mark_application receives an unknown status."""


def _format_row(row) -> list:
    closing = row["closing_date"]
    applied = row["date_applied"]
    return [
        row["posting_id"],
        row["company_name"],
        row["job_title"],
        row["location"],
        str(row["date_posted"]) if row["date_posted"] else "",
        "Not specified" if closing is None else str(closing),
        "" if applied is None else str(applied),
        "Yes" if row["is_likely_closed"] else "No",
        str(row["last_seen_at"]) if row["last_seen_at"] else "",
    ]


def _export_tracker_to_excel(output_path: str) -> str:
    rows = query_rows("SELECT * FROM mart_application_tracker")
    workbook = Workbook(write_only=True)
    sheet = workbook.create_sheet(title="Application Tracker")
    sheet.append([header for _, header in COLUMNS])
    for row in rows:
        sheet.append(_format_row(row))
    workbook.save(output_path)
    logger.info("Wrote application tracker to %s", output_path)
    return output_path


def export_tracker_to_excel(output_path: str) -> str:
    """Query mart_application_tracker, write .xlsx, and return the final path.

    If the target file is locked, retries once with a timestamp-suffixed name.
    """
    try:
        return _export_tracker_to_excel(output_path)
    except PermissionError:
        logger.warning("Target file is locked; retrying with a timestamp suffix")
        path = Path(output_path)
        stamped = path.with_name(f"{path.stem}-{datetime.now():%Y%m%d%H%M%S}{path.suffix}")
        return _export_tracker_to_excel(str(stamped))


def mark_application(posting_id: str, date_applied: date, status: str = "APPLIED") -> None:
    """Upsert an application with status and date after validating the posting, status, and date."""
    if date_applied > date.today():
        raise FutureDateError(f"date_applied {date_applied} is in the future")
    if status not in ALLOWED_STATUSES:
        raise InvalidStatusError(f"status {status!r} is invalid; must be one of {ALLOWED_STATUSES}")
    exists = query_rows(
        "SELECT 1 FROM fact_job_posting WHERE posting_id = :posting_id LIMIT 1",
        {"posting_id": posting_id},
    )
    if not exists:
        raise PostingNotFoundError(f"No posting found with posting_id {posting_id!r}")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    run_sql(
        """
        MERGE INTO applications AS target
        USING (
          SELECT
            :posting_id AS posting_id,
            :date_applied AS date_applied,
            :status AS status,
            :updated_at AS updated_at
        ) AS source
        ON target.posting_id = source.posting_id
        WHEN MATCHED THEN
          UPDATE SET
            date_applied = source.date_applied,
            status = source.status,
            updated_at = source.updated_at
        WHEN NOT MATCHED THEN
          INSERT (posting_id, date_applied, status, updated_at)
          VALUES (source.posting_id, source.date_applied, source.status, source.updated_at)
        """,
        {
            "posting_id": posting_id,
            "date_applied": date_applied.isoformat(),
            "status": status,
            "updated_at": now,
        },
    )
    logger.info("Marked posting %s as %s on %s", posting_id, status, date_applied)
