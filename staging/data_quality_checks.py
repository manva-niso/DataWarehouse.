"""Data-quality checks for Job Market Pulse staging output.

Runs each rule against staging tables and records PASS/FAIL/WARN per rule in
data_quality_log. Zero postings is a valid outcome and is logged as WARN,
never as a failure. Runs against the Databricks warehouse via dbio.
"""

import logging
from datetime import datetime, timezone

from dbio import query_rows, run_sql

logger = logging.getLogger(__name__)

RULES = [
    {
        "rule_name": "duplicate_posting_ids",
        "sql": (
            "SELECT COUNT(*) AS n FROM ("
            "SELECT posting_id FROM staging_postings "
            "GROUP BY posting_id HAVING COUNT(*) > 1)"
        ),
        "expected": 0,
    },
    {
        "rule_name": "null_required_fields",
        "sql": (
            "SELECT COUNT(*) AS n FROM staging_postings "
            "WHERE posting_id IS NULL OR job_title IS NULL OR company_name IS NULL"
        ),
        "expected": 0,
    },
    {
        "rule_name": "future_date_posted",
        "sql": (
            "SELECT COUNT(*) AS n FROM staging_postings "
            "WHERE date_posted > CURRENT_DATE()"
        ),
        "expected": 0,
    },
    {
        "rule_name": "zero_postings",
        "sql": "SELECT COUNT(*) AS n FROM staging_postings",
        "expected": None,
    },
]


def run_data_quality_checks(run_id: str) -> int:
    """Run each rule, log PASS/FAIL/WARN, and return the number of failed rules."""
    checked_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    failed = 0
    for rule in RULES:
        result = query_rows(rule["sql"])
        rows_affected = result[0]["n"] if result else 0
        if rule["expected"] is None:
            status = "WARN" if rows_affected == 0 else "PASS"
        else:
            status = "PASS" if rows_affected == rule["expected"] else "FAIL"
        if status == "FAIL":
            failed += 1
        run_sql(
            """
            INSERT INTO data_quality_log
              (run_id, rule_name, status, rows_affected, checked_at)
            VALUES
              (:run_id, :rule_name, :status, :rows_affected, :checked_at)
            """,
            {
                "run_id": run_id,
                "rule_name": rule["rule_name"],
                "status": status,
                "rows_affected": rows_affected,
                "checked_at": checked_at,
            },
        )
        logger.info("DQ rule %s: %s (%d rows)", rule["rule_name"], status, rows_affected)
    return failed
