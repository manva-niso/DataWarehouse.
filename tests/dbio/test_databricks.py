from unittest.mock import patch

from dbio import split_statements


def test_split_statements_drops_comments_and_splits_on_semicolons():
    script = """
-- header comment
CREATE TABLE a (x STRING);
CREATE TABLE b (y BIGINT);

-- trailing comment
"""
    statements = split_statements(script)
    assert len(statements) == 2
    assert "CREATE TABLE a" in statements[0]
    assert "CREATE TABLE b" in statements[1]


def test_split_statements_single_statement_without_semicolon():
    assert split_statements("SELECT 1") == ["SELECT 1"]


@patch("dbio.databricks.run_sql")
def test_run_sql_script_runs_each_statement(mock_run_sql):
    mock_run_sql.return_value = 0
    from dbio import run_sql_script

    total = run_sql_script("CREATE TABLE a (x STRING);\nCREATE TABLE b (y STRING);")
    assert mock_run_sql.call_count == 2
    assert total == 0
