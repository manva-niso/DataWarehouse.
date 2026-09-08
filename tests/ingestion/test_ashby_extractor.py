from unittest.mock import patch

import pytest

from ingestion.ashby_extractor import (
    AshbyConfigError,
    fetch_ashby_jobs,
)


@patch("ingestion.ashby_extractor.get_json", return_value={"jobs": []})
def test_fetch_ashby_jobs_empty_board_returns_empty_list(mock_get_json):
    assert fetch_ashby_jobs("example-board") == []


@patch("ingestion.ashby_extractor.get_json", return_value={"jobs": [{"id": "abc-123", "title": "Data Engineer"}]})
def test_fetch_ashby_jobs_returns_jobs(mock_get_json):
    jobs = fetch_ashby_jobs("example-board")
    assert len(jobs) == 1
    assert jobs[0]["title"] == "Data Engineer"


@patch("ingestion.ashby_extractor.get_json", return_value={"jobs": [{"id": "abc-123"}]})
def test_fetch_ashby_jobs_uses_board_url(mock_get_json):
    fetch_ashby_jobs("test-slug")
    assert "posting-api/job-board/test-slug" in mock_get_json.call_args.args[0]


def test_fetch_ashby_jobs_missing_slug_raises_config_error():
    with pytest.raises(AshbyConfigError):
        fetch_ashby_jobs("")
