from unittest.mock import patch

import pytest

from ingestion.lever_extractor import (
    LeverConfigError,
    fetch_lever_jobs,
)


@patch("ingestion.lever_extractor.get_json", return_value=[])
def test_fetch_lever_jobs_empty_returns_empty_list(mock_get_json):
    assert fetch_lever_jobs("acme") == []


@patch("ingestion.lever_extractor.get_json", return_value=[{"id": "abc"}])
def test_fetch_lever_jobs_returns_postings(mock_get_json):
    assert fetch_lever_jobs("acme") == [{"id": "abc"}]


@patch("ingestion.lever_extractor.get_json", return_value=[{"id": "abc"}])
def test_fetch_lever_jobs_hardcodes_mode_json(mock_get_json):
    fetch_lever_jobs("acme")
    assert mock_get_json.call_args.kwargs["params"] == {"mode": "json"}
    assert "postings/acme" in mock_get_json.call_args.args[0]


def test_fetch_lever_jobs_missing_slug_raises_config_error():
    with pytest.raises(LeverConfigError):
        fetch_lever_jobs("")
