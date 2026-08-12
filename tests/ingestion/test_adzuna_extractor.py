from unittest.mock import Mock, patch

import pytest

from ingestion.adzuna_extractor import (
    AdzunaApiError,
    AdzunaConfigError,
    AdzunaCountryError,
    AdzunaParseError,
    AdzunaRateLimitError,
    fetch_adzuna_jobs,
)


def _response(status_code, body=None, headers=None):
    response = Mock(status_code=status_code, headers=headers or {})
    if body is None:
        response.json.side_effect = ValueError("malformed body")
    else:
        response.json.return_value = body
    return response


@patch("ingestion.adzuna_extractor._adzuna_credentials", return_value=("app-id", "app-key"))
def test_fetch_adzuna_jobs_unsupported_country_raises_country_error(mock_credentials):
    with pytest.raises(AdzunaCountryError):
        fetch_adzuna_jobs("python", "xx", 1)
    mock_credentials.assert_not_called()


@patch("ingestion.adzuna_extractor.requests.get", return_value=_response(200, {"results": []}))
@patch("ingestion.adzuna_extractor._adzuna_credentials", return_value=("app-id", "app-key"))
def test_fetch_adzuna_jobs_empty_results_returns_empty_list(mock_credentials, mock_get):
    assert fetch_adzuna_jobs("python", "gb", 1) == []


@patch("ingestion.adzuna_extractor.requests.get", return_value=_response(200, {"results": [{"id": 1}]}))
@patch("ingestion.adzuna_extractor._adzuna_credentials", return_value=("app-id", "app-key"))
def test_fetch_adzuna_jobs_results_returned_when_present(mock_credentials, mock_get):
    assert fetch_adzuna_jobs("python", "gb", 1) == [{"id": 1}]


@patch("ingestion.adzuna_extractor.requests.get", return_value=_response(200, {"results": []}))
@patch("ingestion.adzuna_extractor._adzuna_credentials", return_value=("app-id", "app-key"))
def test_fetch_adzuna_jobs_sends_what_parameter(mock_credentials, mock_get):
    fetch_adzuna_jobs("python", "gb", 1)
    params = mock_get.call_args.kwargs["params"]
    assert params["what"] == "python"
    assert "results_per_page" in params


@patch("ingestion.adzuna_extractor.requests.get", side_effect=[_response(429), _response(200, {"results": []})])
@patch("ingestion.adzuna_extractor.time.sleep")
@patch("ingestion.adzuna_extractor._adzuna_credentials", return_value=("app-id", "app-key"))
def test_fetch_adzuna_jobs_rate_limit_retries_once_then_succeeds(mock_credentials, mock_sleep, mock_get):
    assert fetch_adzuna_jobs("python", "gb", 1) == []
    assert mock_get.call_count == 2


@patch("ingestion.adzuna_extractor.requests.get", return_value=_response(429))
@patch("ingestion.adzuna_extractor.time.sleep")
@patch("ingestion.adzuna_extractor._adzuna_credentials", return_value=("app-id", "app-key"))
def test_fetch_adzuna_jobs_rate_limit_exhausted_raises_gracefully(mock_credentials, mock_sleep, mock_get):
    with pytest.raises(AdzunaRateLimitError):
        fetch_adzuna_jobs("python", "gb", 1)


@patch("ingestion.adzuna_extractor.requests.get", side_effect=[_response(429, headers={"Retry-After": "5"}), _response(200, {"results": []})])
@patch("ingestion.adzuna_extractor.time.sleep")
@patch("ingestion.adzuna_extractor._adzuna_credentials", return_value=("app-id", "app-key"))
def test_fetch_adzuna_jobs_rate_limit_respects_retry_after(mock_credentials, mock_sleep, mock_get):
    fetch_adzuna_jobs("python", "gb", 1)
    mock_sleep.assert_called_once_with(5.0)


@patch("ingestion.adzuna_extractor.requests.get", return_value=_response(200))
@patch("ingestion.adzuna_extractor._adzuna_credentials", return_value=("app-id", "app-key"))
def test_fetch_adzuna_jobs_malformed_json_raises_parse_error(mock_credentials, mock_get):
    with pytest.raises(AdzunaParseError):
        fetch_adzuna_jobs("python", "gb", 1)


@patch("ingestion.adzuna_extractor.requests.get", return_value=_response(500))
@patch("ingestion.adzuna_extractor._adzuna_credentials", return_value=("app-id", "app-key"))
def test_fetch_adzuna_jobs_server_error_raises_api_error(mock_credentials, mock_get):
    with pytest.raises(AdzunaApiError):
        fetch_adzuna_jobs("python", "gb", 1)


def test_fetch_adzuna_jobs_missing_credentials_raises_config_error(monkeypatch):
    monkeypatch.delenv("ADZUNA_APP_ID", raising=False)
    monkeypatch.delenv("ADZUNA_APP_KEY", raising=False)
    with patch("ingestion.adzuna_extractor.load_dotenv"):
        with pytest.raises(AdzunaConfigError):
            fetch_adzuna_jobs("python", "gb", 1)
