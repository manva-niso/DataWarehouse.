from datetime import date
from unittest.mock import patch

import pytest

from app.crud import (
    add_note,
    delete_note,
    get_notes,
    get_profile,
    hide_job,
    save_job,
    unhide_job,
    unmark_application,
    update_note,
    upsert_profile,
)


@patch("app.crud.mark_application")
def test_save_job_calls_mark_application(mock_mark):
    save_job("adzuna-123")
    mock_mark.assert_called_once_with("adzuna-123", date.today(), status="SAVED")


@patch("app.crud.run_sql")
def test_unmark_application_deletes_row(mock_run_sql):
    unmark_application("adzuna-123")
    mock_run_sql.assert_called_once()
    sql, params = mock_run_sql.call_args.args
    assert "DELETE FROM applications" in sql
    assert params["posting_id"] == "adzuna-123"


@patch("app.crud.run_sql")
def test_add_note_validates_and_inserts(mock_run_sql):
    with pytest.raises(ValueError):
        add_note("adzuna-123", "")
    with pytest.raises(ValueError):
        add_note("adzuna-123", "   ")

    note_id = add_note("adzuna-123", "Had interview round 1")
    assert note_id
    mock_run_sql.assert_called_once()
    sql, params = mock_run_sql.call_args.args
    assert "INSERT INTO job_notes" in sql
    assert params["posting_id"] == "adzuna-123"
    assert params["note"] == "Had interview round 1"


@patch("app.crud.run_sql")
def test_update_note_validates_and_updates(mock_run_sql):
    with pytest.raises(ValueError):
        update_note("nid-1", "")

    update_note("nid-1", "Updated note")
    mock_run_sql.assert_called_once()
    sql, params = mock_run_sql.call_args.args
    assert "UPDATE job_notes" in sql
    assert params["note_id"] == "nid-1"
    assert params["note"] == "Updated note"


@patch("app.crud.run_sql")
def test_delete_note_deletes_row(mock_run_sql):
    delete_note("nid-1")
    mock_run_sql.assert_called_once()
    sql, params = mock_run_sql.call_args.args
    assert "DELETE FROM job_notes" in sql
    assert params["note_id"] == "nid-1"


@patch("app.crud.query_rows", return_value=[{"note_id": "nid-1", "note": "Great fit"}])
def test_get_notes_queries_by_posting(mock_query):
    notes = get_notes("adzuna-123")
    assert len(notes) == 1
    assert notes[0]["note"] == "Great fit"
    mock_query.assert_called_once()


@patch("app.crud.run_sql")
def test_hide_and_unhide_job(mock_run_sql):
    hide_job("adzuna-123")
    assert "MERGE INTO hidden_jobs" in mock_run_sql.call_args.args[0]
    unhide_job("adzuna-123")
    assert "DELETE FROM hidden_jobs" in mock_run_sql.call_args.args[0]


@patch("app.crud.run_sql")
def test_upsert_profile_serializes_json(mock_run_sql):
    upsert_profile(
        target_roles=["DE"],
        target_skills=["SQL", "Python"],
        preferred_locations=["Remote"],
        remote_preference="REMOTE_ONLY",
        min_salary=100000.0,
        currency="USD",
        seniority_level="MID",
    )
    mock_run_sql.assert_called_once()
    sql, params = mock_run_sql.call_args.args
    assert "MERGE INTO user_profile" in sql
    assert '"DE"' in params["target_roles"]
    assert '"SQL"' in params["target_skills"]
    assert params["seniority_level"] == "MID"


@patch("app.crud.query_rows", return_value=[])
def test_get_profile_fallback_defaults(mock_query):
    prof = get_profile()
    assert "DE" in prof["target_roles"]
    assert "SQL" in prof["target_skills"]


@patch(
    "app.crud.query_rows",
    return_value=[
        {
            "profile_id": "default",
            "target_roles": '["SWE", "DE"]',
            "target_skills": '["Python", "Kafka"]',
            "preferred_locations": '["Bengaluru"]',
            "remote_preference": "HYBRID",
            "min_salary": 120000.0,
            "currency": "INR",
            "seniority_level": "MID",
        }
    ],
)
def test_get_profile_loaded(mock_query):
    prof = get_profile()
    assert prof["target_roles"] == ["SWE", "DE"]
    assert prof["target_skills"] == ["Python", "Kafka"]
    assert prof["seniority_level"] == "MID"


@patch("app.crud.query_rows", return_value=[{"skill_name": "SQL"}, {"skill_name": "Python"}])
def test_get_cataloged_skills(mock_query):
    from app.crud import get_cataloged_skills

    skills = get_cataloged_skills()
    assert skills == ["SQL", "Python"]


@patch("app.crud.query_rows", return_value=[{"company_name": "Figma"}, {"company_name": "Stripe"}])
def test_get_cataloged_companies(mock_query):
    from app.crud import get_cataloged_companies

    companies = get_cataloged_companies()
    assert companies == ["Figma", "Stripe"]


@patch("orchestration.run_pipeline.archive_stale_postings", return_value={"archived": 3, "deleted": 3})
@patch("marts.refresh.refresh_mart_views")
def test_trigger_archive(mock_refresh, mock_archive):
    from app.crud import trigger_archive

    counts = trigger_archive(retention_days=7)
    mock_archive.assert_called_once_with(retention_days=7)
    mock_refresh.assert_called_once()
    assert counts == {"archived": 3, "deleted": 3}


@patch("orchestration.run_pipeline._fetch_source", return_value=[{"id": 1}])
@patch("ingestion.bigquery_io.write_to_bigquery_raw", return_value=1)
@patch("orchestration.run_pipeline.log_pipeline_run")
@patch("orchestration.run_pipeline._run_staging")
@patch("staging.data_quality_checks.run_data_quality_checks")
@patch("warehouse.loaders.load_dim_company")
@patch("warehouse.loaders.load_fact_job_posting")
@patch("warehouse.loaders.load_user_profile")
@patch("marts.refresh.refresh_mart_views")
@patch("orchestration.run_pipeline.archive_stale_postings", return_value={"archived": 0, "deleted": 0})
def test_trigger_reload_pipeline(
    mock_archive,
    mock_refresh,
    mock_profile,
    mock_facts,
    mock_dim,
    mock_dq,
    mock_staging,
    mock_log,
    mock_write,
    mock_fetch,
):
    from app.crud import trigger_reload_pipeline

    result = trigger_reload_pipeline()
    assert "run_id" in result
    assert result["total_rows"] >= 1
    mock_staging.assert_called_once()
    mock_dq.assert_called_once()
    mock_facts.assert_called_once()
    mock_refresh.assert_called_once()

