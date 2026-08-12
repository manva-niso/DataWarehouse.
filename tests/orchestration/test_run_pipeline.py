from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from orchestration import run_pipeline as rp


def test_cleanup_raw_tables_rejects_non_positive_retention():
    with pytest.raises(ValueError):
        rp.cleanup_raw_tables(0)
    with pytest.raises(ValueError):
        rp.cleanup_raw_tables(-5)


@patch("orchestration.run_pipeline.run_sql", return_value=3)
def test_cleanup_raw_tables_returns_deleted_counts(mock_run_sql):
    deleted = rp.cleanup_raw_tables(30)
    assert deleted == {
        "raw_greenhouse": 3,
        "raw_lever": 3,
        "raw_rippling": 3,
        "raw_adzuna": 3,
    }
    sql = mock_run_sql.call_args.args[0]
    assert "INTERVAL 30 DAY" in sql


@patch("orchestration.run_pipeline.query_rows", return_value=[])
def test_get_last_watermark_defaults_to_30_days_ago(mock_query):
    watermark = rp.get_last_watermark("adzuna")
    assert datetime.now(timezone.utc) - watermark < timedelta(days=31)
    assert datetime.now(timezone.utc) - watermark > timedelta(days=29)


@patch("orchestration.run_pipeline.query_rows")
def test_get_last_watermark_returns_last_successful_run(mock_query):
    last_run = datetime(2026, 8, 1, 12, 0, 0, tzinfo=timezone.utc)
    mock_query.return_value = [{"last_run": last_run}]
    assert rp.get_last_watermark("adzuna") == last_run


@patch("orchestration.run_pipeline.insert_rows", return_value=1)
def test_log_pipeline_run_writes_one_row_per_entry(mock_insert):
    rp.log_pipeline_run("run-1", "SUCCESS", {"adzuna": 5})
    table, rows = mock_insert.call_args.args
    assert table == "pipeline_run_log"
    assert len(rows) == 1
    assert rows[0]["status"] == "SUCCESS"
    assert rows[0]["rows_written"] == 5


@patch("orchestration.run_pipeline.log_pipeline_run")
@patch("orchestration.run_pipeline.os.kill")
def test_main_second_run_logs_already_running_and_exits(mock_kill, mock_log, tmp_path, monkeypatch):
    monkeypatch.setattr(rp, "LOCK_FILE", tmp_path / "lock")
    (tmp_path / "lock").write_text("123", encoding="utf-8")
    mock_kill.return_value = None
    with patch("orchestration.run_pipeline.logger") as mock_logger:
        rp.main()
    assert "ALREADY_RUNNING" in str(mock_logger.warning.call_args)
    mock_log.assert_not_called()


@patch("orchestration.run_pipeline._fetch_source", return_value=[])
@patch("orchestration.run_pipeline.write_to_bigquery_raw", return_value=0)
@patch("orchestration.run_pipeline.log_pipeline_run")
@patch("orchestration.run_pipeline._run_staging")
@patch("orchestration.run_pipeline.run_data_quality_checks", return_value=0)
@patch("orchestration.run_pipeline.load_dim_company")
@patch("orchestration.run_pipeline.load_fact_job_posting")
@patch("orchestration.run_pipeline.refresh_mart_views")
def test_main_successful_run_logs_overall_success(
    mock_refresh,
    mock_facts,
    mock_dims,
    mock_dq,
    mock_staging,
    mock_log,
    mock_write,
    mock_fetch,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(rp, "LOCK_FILE", tmp_path / "lock")
    rp.main()
    overall_call = [
        call for call in mock_log.call_args_list
        if call.args[1] == "SUCCESS" and call.args[2] == {"OVERALL": 0}
    ]
    assert overall_call
    assert not (tmp_path / "lock").exists()


@patch("orchestration.run_pipeline._fetch_source", side_effect=RuntimeError("all down"))
@patch("orchestration.run_pipeline.log_pipeline_run")
@patch("orchestration.run_pipeline._run_staging")
def test_main_all_sources_failed_skips_downstream(
    mock_staging, mock_log, mock_fetch, tmp_path, monkeypatch
):
    monkeypatch.setattr(rp, "LOCK_FILE", tmp_path / "lock")
    rp.main()
    assert any(call.args[1] == "FAILED" for call in mock_log.call_args_list)
    mock_staging.assert_not_called()
