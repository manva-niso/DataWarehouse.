"""Cold storage archival encoder for Job Market Pulse.

Extracts outdated and stale postings (closing_date passed or unseen > retention_days),
encodes all metadata (dates, role category, experience, URLs, descriptions) into a
compressed, portable JSONL cold-storage archive file under exports/, and completely
purges the outdated records from the Databricks Delta database.
"""

import base64
import gzip
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dbio.databricks import query_rows, run_sql

logger = logging.getLogger(__name__)

EXPORTS_DIR = Path(__file__).parents[1] / "exports"
ENCODED_ARCHIVE_PATH = EXPORTS_DIR / "archived_postings_encoded.jsonl.gz"
ENCODED_ARCHIVE_JSONL = EXPORTS_DIR / "archived_postings_encoded.jsonl"


def _encode_posting(row: dict[str, Any], reason: str = "STALE_RETENTION") -> dict[str, Any]:
    """Serialize all attributes and generate a compact encoded verification token."""
    clean_row = {}
    for k, v in row.items():
        if hasattr(v, "isoformat"):
            clean_row[k] = v.isoformat()
        else:
            clean_row[k] = v

    now_iso = datetime.now(timezone.utc).isoformat()
    clean_row["archived_at"] = now_iso
    clean_row["archive_reason"] = reason

    # Lightweight Base64 signature for verification
    payload_sig = f"{clean_row.get('posting_id')}|{clean_row.get('role_family')}|{clean_row.get('last_seen_at')}"
    clean_row["_encoded_token"] = base64.b64encode(payload_sig.encode("utf-8")).decode("ascii")

    return clean_row


def get_existing_archived_ids() -> set[str]:
    """Read existing archived posting IDs from the local compressed archive."""
    if not ENCODED_ARCHIVE_PATH.exists():
        return set()
    archived_ids = set()
    try:
        with gzip.open(ENCODED_ARCHIVE_PATH, "rt", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    item = json.loads(line)
                    pid = item.get("posting_id")
                    if pid:
                        archived_ids.add(pid)
    except Exception as exc:
        logger.warning("Failed reading existing encoded archive: %s", exc)
    return archived_ids


def encode_and_purge_outdated_postings(retention_days: int = 7) -> dict[str, Any]:
    """Extract stale postings, encode into cold storage, and purge from database.

    1. Identifies stale rows in fact_job_posting and fact_job_posting_archive.
    2. Encodes all job info (role category, dates, URLs, descriptions, criteria).
    3. Appends to exports/archived_postings_encoded.jsonl.gz and exports/archived_postings_encoded.jsonl.
    4. Deletes purged records from fact_job_posting, job_posting_detail,
       fact_posting_skill_mention, and truncates fact_job_posting_archive.
    """
    if retention_days <= 0:
        raise ValueError(f"retention_days must be positive; got {retention_days}")

    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    existing_pids = get_existing_archived_ids()

    # Query all stale rows from fact_job_posting
    fetch_sql = f"""
    SELECT
      f.posting_id,
      f.job_title,
      f.role_family,
      c.company_name,
      l.location_normalized AS location,
      f.source_id,
      f.date_posted,
      f.closing_date,
      f.first_seen_at,
      f.last_seen_at,
      f.is_incomplete,
      d.salary_min,
      d.salary_max,
      d.currency,
      d.employment_type,
      d.posting_url,
      d.apply_url,
      d.description
    FROM fact_job_posting f
    LEFT JOIN dim_company c ON c.company_id = f.company_id AND c.is_current = TRUE
    LEFT JOIN dim_location l ON l.location_id = f.location_id
    LEFT JOIN job_posting_detail d ON d.posting_id = f.posting_id
    WHERE (f.closing_date < CURRENT_DATE()
           OR f.last_seen_at < CURRENT_TIMESTAMP() - INTERVAL {retention_days} DAY)
    """
    stale_facts = query_rows(fetch_sql)

    # Also check any records in fact_job_posting_archive
    try:
        fetch_arc_sql = """
        SELECT
          arc.posting_id,
          arc.job_title,
          arc.role_family,
          c.company_name,
          l.location_normalized AS location,
          arc.source_id,
          arc.date_posted,
          arc.closing_date,
          arc.first_seen_at,
          arc.last_seen_at,
          arc.is_incomplete,
          d.salary_min,
          d.salary_max,
          d.currency,
          d.employment_type,
          d.posting_url,
          d.apply_url,
          d.description
        FROM fact_job_posting_archive arc
        LEFT JOIN dim_company c ON c.company_id = arc.company_id AND c.is_current = TRUE
        LEFT JOIN dim_location l ON l.location_id = arc.location_id
        LEFT JOIN job_posting_detail d ON d.posting_id = arc.posting_id
        """
        existing_arc_rows = query_rows(fetch_arc_sql)
    except Exception:
        existing_arc_rows = []

    all_to_archive = {}
    for r in existing_arc_rows:
        pid = r.get("posting_id")
        if pid:
            all_to_archive[pid] = r
    for r in stale_facts:
        pid = r.get("posting_id")
        if pid:
            all_to_archive[pid] = r

    encoded_records = []
    pids_to_purge = list(all_to_archive.keys())

    for pid, row in all_to_archive.items():
        if pid not in existing_pids:
            encoded = _encode_posting(row, reason="NO_LONGER_SEEN" if not row.get("closing_date") else "DATE_PASSED")
            encoded_records.append(encoded)

    # Append to compressed gzip archive and plain jsonl
    if encoded_records:
        with gzip.open(ENCODED_ARCHIVE_PATH, "at", encoding="utf-8") as gz_f:
            for item in encoded_records:
                gz_f.write(json.dumps(item) + "\n")

        with open(ENCODED_ARCHIVE_JSONL, "a", encoding="utf-8") as jsonl_f:
            for item in encoded_records:
                jsonl_f.write(json.dumps(item) + "\n")

        logger.info("Encoded %d outdated postings to %s", len(encoded_records), ENCODED_ARCHIVE_PATH)

    # Purge from Databricks database
    purged_count = len(pids_to_purge)
    if pids_to_purge:
        run_sql(f"""
        DELETE FROM fact_job_posting
        WHERE closing_date < CURRENT_DATE()
           OR last_seen_at < CURRENT_TIMESTAMP() - INTERVAL {retention_days} DAY
        """)
        run_sql("""
        DELETE FROM job_posting_detail
        WHERE posting_id NOT IN (SELECT posting_id FROM fact_job_posting)
        """)
        run_sql("""
        DELETE FROM fact_posting_skill_mention
        WHERE posting_id NOT IN (SELECT posting_id FROM fact_job_posting)
        """)

    # Truncate / clear fact_job_posting_archive so zero outdated rows linger in DB
    try:
        run_sql("TRUNCATE TABLE fact_job_posting_archive")
    except Exception as exc:
        logger.debug("Could not truncate archive table: %s", exc)

    logger.info("Successfully encoded and purged %d outdated postings from database", purged_count)
    return {
        "encoded_count": len(encoded_records),
        "purged_count": purged_count,
        "archive_file": str(ENCODED_ARCHIVE_PATH),
        "total_archived_offline": len(existing_pids) + len(encoded_records),
    }


def load_encoded_archived_postings(limit: int = 100) -> list[dict[str, Any]]:
    """Read encoded postings from cold storage archive file for offline browsing."""
    if not ENCODED_ARCHIVE_PATH.exists():
        return []
    postings = []
    try:
        with gzip.open(ENCODED_ARCHIVE_PATH, "rt", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    postings.append(json.loads(line))
                    if len(postings) >= limit:
                        break
    except Exception as exc:
        logger.error("Error loading encoded archived postings: %s", exc)
    return postings
