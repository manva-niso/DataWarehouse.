from unittest.mock import patch

from marts.refresh import refresh_mart_views
from warehouse.loaders import load_dim_company, load_fact_job_posting


@patch("warehouse.loaders.run_sql_script")
def test_load_dim_company_runs_dimensions_sql(mock_run_sql):
    load_dim_company()
    sql = mock_run_sql.call_args.args[0]
    assert "dim_company" in sql
    assert "CREATE OR REPLACE TABLE dim_date" in sql


@patch("warehouse.loaders.run_sql_script")
def test_load_fact_job_posting_runs_facts_sql(mock_run_sql):
    load_fact_job_posting()
    sql = mock_run_sql.call_args.args[0]
    assert "MERGE INTO fact_job_posting" in sql
    assert "fact_posting_skill_mention" in sql


@patch("marts.refresh.run_sql_script")
def test_refresh_mart_views_runs_every_mart_sql_file(mock_run_sql):
    refresh_mart_views()
    sql_files = [call.args[0] for call in mock_run_sql.call_args_list]
    assert any("mart_skill_demand_trend" in sql for sql in sql_files)
    assert any("mart_application_tracker" in sql for sql in sql_files)
    assert any("mart_hiring_velocity" in sql for sql in sql_files)
    assert any("mart_company_activity" in sql for sql in sql_files)
