"""Warehouse loaders for Job Market Pulse.

The loading logic lives in the numbered SQL files (AGENTS.md build order
step 5); these functions provide the Python interface specified in the
function specs and stay idempotent by construction. SQL runs against the
Databricks warehouse through the dbio package.
"""

import logging
from pathlib import Path

from dbio import run_sql_script

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
