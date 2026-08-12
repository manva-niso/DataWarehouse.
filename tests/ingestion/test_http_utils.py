from unittest.mock import Mock, patch

import pytest

from ingestion.http_utils import (
    SourceHttpError,
    SourceParseError,
    SourceRateLimitError,
    get_json,
)


def _response(status_code, body=None, headers=None):
    response = Mock(status_code=status_code, headers=headers or {})
    if body is None:
        response.json.side_effect = ValueError("malformed body")
    else:
        response.json.return_value = body
    return response


@patch("ingestion.http_utils.requests.get", return_value=_response(200, {"jobs": []}))
def test_get_json_returns_parsed_body(mock_get):
    assert get_json("https://example.test/jobs") == {"jobs": []}


@patch("ingestion.http_utils.requests.get", return_value=_response(200))
def test_get_json_malformed_body_raises_parse_error(mock_get):
    with pytest.raises(SourceParseError):
        get_json("https://example.test/jobs")


@patch("ingestion.http_utils.requests.get", side_effect=[_response(429), _response(200, [])])
@patch("ingestion.http_utils.time.sleep")
def test_get_json_rate_limit_retries_once_then_succeeds(mock_sleep, mock_get):
    assert get_json("https://example.test/jobs") == []
    assert mock_get.call_count == 2


@patch("ingestion.http_utils.requests.get", side_effect=[_response(429, headers={"Retry-After": "4"}), _response(200, [])])
@patch("ingestion.http_utils.time.sleep")
def test_get_json_rate_limit_respects_retry_after(mock_sleep, mock_get):
    get_json("https://example.test/jobs")
    mock_sleep.assert_called_once_with(4.0)


@patch("ingestion.http_utils.requests.get", return_value=_response(429))
@patch("ingestion.http_utils.time.sleep")
def test_get_json_rate_limit_exhausted_raises_gracefully(mock_sleep, mock_get):
    with pytest.raises(SourceRateLimitError):
        get_json("https://example.test/jobs")


@patch("ingestion.http_utils.requests.get", return_value=_response(500))
def test_get_json_server_error_raises_http_error(mock_get):
    with pytest.raises(SourceHttpError):
        get_json("https://example.test/jobs")
