from unittest.mock import patch

from staging.data_quality_checks import run_data_quality_checks


@patch("staging.data_quality_checks.query_rows", side_effect=[[{"n": 0}], [{"n": 0}], [{"n": 0}], [{"n": 5}]])
@patch("staging.data_quality_checks.run_sql")
def test_run_data_quality_checks_all_rules_pass(mock_run_sql, mock_query):
    assert run_data_quality_checks("run-1") == 0
    assert mock_query.call_count == 4  # one per rule
    assert mock_run_sql.call_count == 4  # one log insert per rule


@patch("staging.data_quality_checks.query_rows", side_effect=[[{"n": 1}], [{"n": 0}], [{"n": 0}], [{"n": 5}]])
@patch("staging.data_quality_checks.run_sql")
def test_run_data_quality_checks_failed_rule_counted(mock_run_sql, mock_query):
    assert run_data_quality_checks("run-1") == 1


@patch("staging.data_quality_checks.query_rows", side_effect=[[{"n": 0}], [{"n": 0}], [{"n": 0}], [{"n": 0}]])
@patch("staging.data_quality_checks.run_sql")
def test_run_data_quality_checks_zero_postings_is_warn_not_fail(mock_run_sql, mock_query):
    assert run_data_quality_checks("run-1") == 0
