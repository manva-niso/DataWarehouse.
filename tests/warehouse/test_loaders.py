from unittest.mock import patch

from marts.refresh import refresh_mart_views
from warehouse.loaders import load_dim_company, load_fact_job_posting, load_user_profile


@patch("warehouse.loaders.run_sql_script")
def test_load_dim_company_runs_dimensions_sql(mock_run_sql):
    load_dim_company()
    sql_files = [call.args[0] for call in mock_run_sql.call_args_list]
    assert any("dim_company" in sql and "CREATE OR REPLACE TABLE dim_date" in sql for sql in sql_files)
    assert any("dbt" in sql and "Databricks" in sql for sql in sql_files)
    assert any("UPDATE dim_company" in sql and "is_current = FALSE" in sql for sql in sql_files)


@patch("warehouse.loaders.run_sql_script")
def test_load_fact_job_posting_runs_facts_sql(mock_run_sql):
    load_fact_job_posting()
    sql = mock_run_sql.call_args.args[0]
    assert "MERGE INTO fact_job_posting" in sql
    assert "role_family" in sql
    assert "MERGE INTO job_posting_detail" in sql
    assert "fact_posting_skill_mention" in sql


@patch("warehouse.loaders.run_sql")
def test_load_user_profile_upserts_profile(mock_run_sql):
    load_user_profile()
    sql, params = mock_run_sql.call_args.args
    assert "MERGE INTO user_profile" in sql
    assert params["profile_id"] == "default"
    assert "DE" in params["target_roles"]
    assert "SQL" in params["target_skills"]


@patch("marts.refresh.run_sql_script")
def test_refresh_mart_views_runs_every_mart_sql_file(mock_run_sql):
    refresh_mart_views()
    sql_files = [call.args[0] for call in mock_run_sql.call_args_list]
    assert any("mart_skill_demand_trend" in sql for sql in sql_files)
    assert any("mart_application_tracker" in sql for sql in sql_files)
    assert any("mart_hiring_velocity" in sql for sql in sql_files)
    assert any("mart_company_activity" in sql for sql in sql_files)
    assert any("mart_job_match" in sql for sql in sql_files)
    assert any("mart_role_market" in sql for sql in sql_files)
    assert any("mart_posting_seasonality" in sql for sql in sql_files)
    assert any("mart_salary_summary" in sql for sql in sql_files)
    assert any("mart_source_quality" in sql for sql in sql_files)
    assert any("mart_application_funnel" in sql for sql in sql_files)
    assert any("mart_posting_longevity" in sql for sql in sql_files)
