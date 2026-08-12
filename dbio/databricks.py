"""Databricks (Delta) execution helpers for Job Market Pulse.

Connects to the Databricks Free Edition SQL warehouse with a personal access
token and runs SQL statements. Every call opens and closes its own connection
so no session state leaks between pipeline stages.

Environment variables (from .env):
    DATABRICKS_HOST        workspace URL host, e.g. dbc-xxx.cloud.databricks.com
    DATABRICKS_HTTP_PATH   SQL warehouse HTTP path, e.g. /sql/1.0/warehouses/<id>
    DATABRICKS_TOKEN       personal access token (SQL warehouse scope, Other API)
    DATABRICKS_CATALOG     optional, default workspace (Unity Catalog managed catalog)
    DATABRICKS_SCHEMA      optional, default default
"""

import logging
import os
from pathlib import Path

from databricks import sql
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _load_env() -> None:
    load_dotenv(PROJECT_ROOT / ".env")


def _connection():
    _load_env()
    host = os.getenv("DATABRICKS_HOST")
    http_path = os.getenv("DATABRICKS_HTTP_PATH")
    token = os.getenv("DATABRICKS_TOKEN")
    if not host or not http_path or not token:
        raise RuntimeError(
            "DATABRICKS_HOST, DATABRICKS_HTTP_PATH and DATABRICKS_TOKEN "
            "must be set in the local .env file"
        )
    return sql.connect(
        server_hostname=host,
        http_path=http_path,
        access_token=token,
        catalog=os.getenv("DATABRICKS_CATALOG", "workspace"),
        schema=os.getenv("DATABRICKS_SCHEMA", "default"),
        enable_telemetry=False,
    )


def split_statements(script: str) -> list[str]:
    """Split SQL text into individual statements, dropping comment lines."""
    statements: list[str] = []
    current: list[str] = []
    for line in script.splitlines():
        if line.strip().startswith("--"):
            continue
        current.append(line)
        if line.strip().endswith(";"):
            statements.append("\n".join(current).strip())
            current = []
    tail = "\n".join(current).strip()
    if tail:
        statements.append(tail)
    return [statement for statement in statements if statement]


def run_sql_script(script: str, parameters: dict | None = None) -> int:
    """Run a script of one or more statements; returns total affected rows.

    The Databricks SQL connector executes exactly one statement per call, so
    multi-statement SQL files (e.g. load_dimensions.sql) must be split first.
    """
    total = 0
    for statement in split_statements(script):
        total += run_sql(statement, parameters)
    return total


def run_sql(statement: str, parameters: dict | None = None) -> int:
    """Execute one statement and return the number of affected rows."""
    conn = _connection()
    try:
        cursor = conn.cursor()
        cursor.execute(statement, parameters)
        rowcount = cursor.rowcount if cursor.rowcount and cursor.rowcount > 0 else 0
        cursor.close()
        logger.debug("Executed statement (rows affected: %d)", rowcount)
        return rowcount
    finally:
        conn.close()


def query_rows(statement: str, parameters: dict | None = None) -> list[dict]:
    """Execute a statement and return all rows as dicts keyed by column name."""
    conn = _connection()
    try:
        cursor = conn.cursor()
        cursor.execute(statement, parameters)
        rows = [row.asDict() for row in cursor.fetchall()]
        cursor.close()
        logger.debug("Fetched %d rows", len(rows))
        return rows
    finally:
        conn.close()


def insert_rows(table: str, rows: list[dict]) -> int:
    """Batch-insert rows into a table; keys of the first row define columns."""
    if not rows:
        logger.info("No rows to insert into %s", table)
        return 0
    columns = ", ".join(rows[0].keys())
    placeholders = ", ".join(f":{name}" for name in rows[0].keys())
    statement = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"
    conn = _connection()
    try:
        cursor = conn.cursor()
        cursor.executemany(statement, rows)
        rowcount = cursor.rowcount if cursor.rowcount and cursor.rowcount > 0 else len(rows)
        cursor.close()
        logger.info("Inserted %d rows into %s", rowcount, table)
        return rowcount
    finally:
        conn.close()