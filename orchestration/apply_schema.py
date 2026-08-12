"""Apply warehouse/schema.sql to the Databricks warehouse.

The databricks-sql-connector executes one statement per call, so the DDL file
is split on statement boundaries and each non-empty statement runs through
dbio.run_sql. Rerunnable: all DDL uses CREATE TABLE IF NOT EXISTS and the
dim_source seed is a MERGE.
"""

import sys
from pathlib import Path

from dbio import run_sql, split_statements

SCHEMA_FILE = Path(__file__).parents[1] / "warehouse" / "schema.sql"


def main() -> None:
    sql = SCHEMA_FILE.read_text(encoding="utf-8")
    statements = split_statements(sql)
    if not statements:
        print(f"No statements found in {SCHEMA_FILE}")
        sys.exit(1)
    for statement in statements:
        run_sql(statement)
        first_line = statement.splitlines()[0][:90]
        print(f"OK: {first_line}")
    print(f"Schema applied from {SCHEMA_FILE.name} ({len(statements)} statements)")


if __name__ == "__main__":
    main()
