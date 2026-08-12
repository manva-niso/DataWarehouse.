from unittest.mock import patch

import pytest

from ingestion.greenhouse_extractor import (
    GreenhouseConfigError,
    fetch_greenhouse_jobs,
)


@patch("ingestion.greenhouse_extractor.get_json", return_value={"jobs": []})
def test_fetch_greenhouse_jobs_empty_board_returns_empty_list(mock_get_json):
    assert fetch_greenhouse_jobs("example-board") == []


@patch("ingestion.greenhouse_extractor.get_json", return_value={"jobs": [{"id": 1}]})
def test_fetch_greenhouse_jobs_returns_jobs(mock_get_json):
    assert fetch_greenhouse_jobs("example-board") == [{"id": 1}]


@patch("ingestion.greenhouse_extractor.get_json", return_value={"jobs": [{"id": 1}]})
def test_fetch_greenhouse_jobs_uses_board_url(mock_get_json):
    fetch_greenhouse_jobs("example-board")
    assert "boards/example-board/jobs" in mock_get_json.call_args.args[0]


def test_fetch_greenhouse_jobs_missing_token_raises_config_error():
    with pytest.raises(GreenhouseConfigError):
        fetch_greenhouse_jobs("")
