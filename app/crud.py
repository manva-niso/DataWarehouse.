"""CRUD operations for Job Market Pulse Streamlit Application.

Provides verified, validated database operations for tracking, note taking,
hiding jobs, and updating user profiles. Reads and writes go through the dbio
package to Databricks SQL.
"""

import json
import logging
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from dbio import query_rows, run_sql
from export.export_tracker import (
    ALLOWED_STATUSES,
    FutureDateError,
    InvalidStatusError,
    PostingNotFoundError,
    mark_application,
)

logger = logging.getLogger(__name__)


def save_job(posting_id: str) -> None:
    """Save a job posting to applications with status 'SAVED'."""
    mark_application(posting_id, date.today(), status="SAVED")
    logger.info("Saved job posting %s", posting_id)


def unmark_application(posting_id: str) -> None:
    """Remove a posting from user application tracking."""
    run_sql(
        "DELETE FROM applications WHERE posting_id = :posting_id",
        {"posting_id": posting_id},
    )
    logger.info("Unmarked application for %s", posting_id)


def add_note(posting_id: str, note: str) -> str:
    """Add a note to a job posting and return the new note_id."""
    if not note or not note.strip():
        raise ValueError("Note content cannot be empty")
    note_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    run_sql(
        """
        INSERT INTO job_notes (note_id, posting_id, note, created_at, updated_at)
        VALUES (:note_id, :posting_id, :note, :created_at, :updated_at)
        """,
        {
            "note_id": note_id,
            "posting_id": posting_id,
            "note": note.strip(),
            "created_at": now,
            "updated_at": now,
        },
    )
    logger.info("Added note %s to posting %s", note_id, posting_id)
    return note_id


def update_note(note_id: str, note: str) -> None:
    """Update an existing note's content and updated_at timestamp."""
    if not note or not note.strip():
        raise ValueError("Note content cannot be empty")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    run_sql(
        """
        UPDATE job_notes
        SET note = :note, updated_at = :updated_at
        WHERE note_id = :note_id
        """,
        {
            "note_id": note_id,
            "note": note.strip(),
            "updated_at": now,
        },
    )
    logger.info("Updated note %s", note_id)


def delete_note(note_id: str) -> None:
    """Delete a note by its note_id."""
    run_sql(
        "DELETE FROM job_notes WHERE note_id = :note_id",
        {"note_id": note_id},
    )
    logger.info("Deleted note %s", note_id)


def get_notes(posting_id: str) -> list[dict[str, Any]]:
    """Retrieve all notes for a specific posting, sorted newest first."""
    return query_rows(
        """
        SELECT note_id, posting_id, note, created_at, updated_at
        FROM job_notes
        WHERE posting_id = :posting_id
        ORDER BY created_at DESC
        """,
        {"posting_id": posting_id},
    )


def hide_job(posting_id: str) -> None:
    """Permanently dismiss/hide a job posting from browse and matches."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    run_sql(
        """
        MERGE INTO hidden_jobs AS target
        USING (SELECT :posting_id AS posting_id, :hidden_at AS hidden_at) AS source
        ON target.posting_id = source.posting_id
        WHEN NOT MATCHED THEN
          INSERT (posting_id, hidden_at)
          VALUES (source.posting_id, source.hidden_at)
        """,
        {"posting_id": posting_id, "hidden_at": now},
    )
    logger.info("Hidden job %s", posting_id)


def unhide_job(posting_id: str) -> None:
    """Unhide a previously hidden job posting."""
    run_sql(
        "DELETE FROM hidden_jobs WHERE posting_id = :posting_id",
        {"posting_id": posting_id},
    )
    logger.info("Unhid job %s", posting_id)


def upsert_profile(
    target_roles: list[str],
    target_skills: list[str],
    preferred_locations: list[str],
    remote_preference: str = "ANY",
    min_salary: float = 0.0,
    currency: str = "INR",
    seniority_level: str = "ENTRY",
) -> None:
    """Save updated target profile settings to user_profile."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    run_sql(
        """
        MERGE INTO user_profile AS target
        USING (
          SELECT
            :profile_id AS profile_id,
            :target_roles AS target_roles,
            :target_skills AS target_skills,
            :preferred_locations AS preferred_locations,
            :remote_preference AS remote_preference,
            :min_salary AS min_salary,
            :currency AS currency,
            :seniority_level AS seniority_level,
            :updated_at AS updated_at
        ) AS source
        ON target.profile_id = source.profile_id
        WHEN MATCHED THEN
          UPDATE SET
            target_roles = source.target_roles,
            target_skills = source.target_skills,
            preferred_locations = source.preferred_locations,
            remote_preference = source.remote_preference,
            min_salary = source.min_salary,
            currency = source.currency,
            seniority_level = source.seniority_level,
            updated_at = source.updated_at
        WHEN NOT MATCHED THEN
          INSERT (
            profile_id, target_roles, target_skills, preferred_locations,
            remote_preference, min_salary, currency, seniority_level, updated_at
          )
          VALUES (
            source.profile_id, source.target_roles, source.target_skills,
            source.preferred_locations, source.remote_preference, source.min_salary,
            source.currency, source.seniority_level, source.updated_at
          )
        """,
        {
            "profile_id": "default",
            "target_roles": json.dumps(target_roles),
            "target_skills": json.dumps(target_skills),
            "preferred_locations": json.dumps(preferred_locations),
            "remote_preference": remote_preference,
            "min_salary": float(min_salary),
            "currency": currency,
            "seniority_level": seniority_level,
            "updated_at": now,
        },
    )
    logger.info("Upserted user profile")


def get_profile() -> dict[str, Any]:
    """Retrieve the current user profile from user_profile or fallback defaults."""
    rows = query_rows("SELECT * FROM user_profile WHERE profile_id = 'default' LIMIT 1")
    if rows:
        row = rows[0]
        return {
            "profile_id": row["profile_id"],
            "target_roles": json.loads(row["target_roles"]) if isinstance(row["target_roles"], str) else row["target_roles"],
            "target_skills": json.loads(row["target_skills"]) if isinstance(row["target_skills"], str) else row["target_skills"],
            "preferred_locations": json.loads(row["preferred_locations"]) if isinstance(row["preferred_locations"], str) else row["preferred_locations"],
            "remote_preference": row["remote_preference"],
            "min_salary": float(row["min_salary"] or 0.0),
            "currency": row["currency"],
            "seniority_level": row["seniority_level"],
        }
    return {
        "profile_id": "default",
        "target_roles": ["DE", "DA", "BI"],
        "target_skills": ["SQL", "Python", "Databricks", "Spark", "dbt"],
        "preferred_locations": ["Remote", "India", "Bengaluru"],
        "remote_preference": "ANY",
        "min_salary": 0.0,
        "currency": "INR",
        "seniority_level": "ENTRY",
    }


def get_cataloged_skills() -> list[str]:
    """Return sorted list of cataloged skills from dim_skill."""
    try:
        rows = query_rows("SELECT skill_name FROM dim_skill ORDER BY skill_name ASC")
        skills = [r["skill_name"] for r in rows if r.get("skill_name")]
        if skills:
            return skills
    except Exception as exc:
        logger.warning("Failed to fetch cataloged skills: %s", exc)

    return [
        "Airflow", "AWS", "Azure", "BigQuery", "Databricks", "dbt", "Docker",
        "ETL", "GCP", "Git", "Kafka", "Linux", "Pandas", "PostgreSQL",
        "Power BI", "Python", "Snowflake", "Spark", "SQL", "Tableau",
    ]


def get_cataloged_companies() -> list[str]:
    """Return sorted list of active companies from dim_company."""
    try:
        rows = query_rows(
            "SELECT DISTINCT company_name FROM dim_company WHERE is_current = TRUE ORDER BY company_name ASC"
        )
        return [r["company_name"] for r in rows if r.get("company_name")]
    except Exception as exc:
        logger.warning("Failed to fetch cataloged companies: %s", exc)
        return []


def trigger_archive(retention_days: int = 7) -> dict[str, int]:
    """Archive stale postings and refresh downstream marts."""
    from marts.refresh import refresh_mart_views
    from orchestration.run_pipeline import archive_stale_postings

    counts = archive_stale_postings(retention_days=retention_days)
    refresh_mart_views()
    return counts


def trigger_reload_pipeline() -> dict[str, Any]:
    """Trigger full ingestion pipeline run and refresh warehouse + marts."""
    from ingestion.bigquery_io import write_to_bigquery_raw
    from marts.refresh import refresh_mart_views
    from orchestration.run_pipeline import (
        SOURCES,
        _fetch_source,
        _run_staging,
        archive_stale_postings,
        log_pipeline_run,
    )
    from staging.data_quality_checks import run_data_quality_checks
    from warehouse.loaders import (
        load_dim_company,
        load_fact_job_posting,
        load_user_profile,
    )

    run_id = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    row_counts: dict[str, int] = {}
    source_statuses: dict[str, str] = {}

    for source in SOURCES:
        try:
            payload = _fetch_source(source)
            count = write_to_bigquery_raw(source, payload, run_id)
            row_counts[source] = count
            source_statuses[source] = "SUCCESS"
        except Exception as exc:
            logger.error("Source %s fetch failed: %s", source, exc)
            row_counts[source] = 0
            source_statuses[source] = "FAILED"

    for source in SOURCES:
        try:
            log_pipeline_run(run_id, source_statuses[source], {source: row_counts[source]})
        except Exception as exc:
            logger.error("Failed to log source %s: %s", source, exc)

    succeeded = [s for s in SOURCES if source_statuses[s] == "SUCCESS"]
    if succeeded:
        _run_staging()
        run_data_quality_checks(run_id)
        load_dim_company()
        load_fact_job_posting()
        load_user_profile()
        refresh_mart_views()
        archive_stale_postings(retention_days=7)

    return {
        "run_id": run_id,
        "row_counts": row_counts,
        "source_statuses": source_statuses,
        "total_rows": sum(row_counts.values()),
    }

