"""Databricks SQL execution layer for Job Market Pulse.

Thin wrapper over databricks-sql-connector: one connect() per call, named
parameters (:name style), rows returned as dicts. All consumers import this
package instead of touching the driver directly.
"""

from dbio.databricks import (
    insert_rows,
    query_rows,
    run_sql,
    run_sql_script,
    split_statements,
)

__all__ = ["insert_rows", "query_rows", "run_sql", "run_sql_script", "split_statements"]