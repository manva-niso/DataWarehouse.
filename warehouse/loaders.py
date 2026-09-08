"""Warehouse loaders for Job Market Pulse.

The loading logic lives in the numbered SQL files (AGENTS.md build order
step 5); these functions provide the Python interface specified in the
function specs and stay idempotent by construction. SQL runs against the
Databricks warehouse through the dbio package.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import yaml
from dbio import run_sql, run_sql_script

logger = logging.getLogger(__name__)

WAREHOUSE_SQL_DIR = Path(__file__).parent


def _run_sql_file(filename: str) -> None:
    sql = (WAREHOUSE_SQL_DIR / filename).read_text(encoding="utf-8")
    run_sql_script(sql)
    logger.info("Executed %s", filename)


def load_dim_company(df=None) -> None:
    """Upsert dimensions with SCD2 versioning on tracked-attribute change only.

    The df argument is accepted for signature compatibility with the AGENTS.md
    function spec; the SQL reads directly from the staging tables.
    """
    _run_sql_file("load_dimensions.sql")
    _run_sql_file("scd2_company.sql")


def load_fact_job_posting(df=None) -> None:
    """Upsert facts on (posting_id, date_posted); never delete disappeared postings.

    The df argument is accepted for signature compatibility with the AGENTS.md
    function spec; the SQL reads directly from the staging tables.
    """
    _run_sql_file("load_facts.sql")


def load_user_profile(profile_path: Path | None = None) -> None:
    """Upsert the single-row user_profile table from config/profile.yaml."""
    if profile_path is None:
        profile_path = WAREHOUSE_SQL_DIR.parent / "config" / "profile.yaml"
    if not profile_path.exists():
        logger.warning("No profile config found at %s", profile_path)
        return
    with open(profile_path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    profile = data.get("profile", {})
    if not profile:
        logger.warning("Empty profile in %s", profile_path)
        return

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
            "target_roles": json.dumps(profile.get("target_roles", [])),
            "target_skills": json.dumps(profile.get("target_skills", [])),
            "preferred_locations": json.dumps(profile.get("preferred_locations", [])),
            "remote_preference": profile.get("remote_preference", "ANY"),
            "min_salary": float(profile.get("min_salary", 0.0)),
            "currency": profile.get("currency", "INR"),
            "seniority_level": profile.get("seniority_level", "ENTRY"),
            "updated_at": now,
        },
    )
    logger.info("Loaded user profile from %s", profile_path.name)
