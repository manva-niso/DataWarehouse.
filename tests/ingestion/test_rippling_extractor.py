from unittest.mock import patch

import pytest

from ingestion.http_utils import SourceHttpError
from ingestion.rippling_extractor import (
    RipplingConfigError,
    fetch_rippling_jobs,
)


class _Future:
    def __init__(self, value):
        self.value = value

    def result(self):
        return self.value


def _fake_get_json(url, **kwargs):
    if url.endswith("/jobs"):
        return {
            "items": [{"id": "a"}, {"id": "b"}],
            "page": 0,
            "totalPages": 1,
        }
    return {"job": "detail-" + url.rsplit("/", 1)[-1]}


@patch("ingestion.rippling_extractor.get_json", return_value={"items": []})
def test_fetch_rippling_jobs_empty_board_returns_empty_list(mock_get_json):
    assert fetch_rippling_jobs("example-board") == []


@patch("ingestion.rippling_extractor.get_json", side_effect=_fake_get_json)
@patch("ingestion.rippling_extractor.as_completed", side_effect=lambda futures: futures)
def test_fetch_rippling_jobs_lists_then_fetches_details(mock_as_completed, mock_get_json):
    results = fetch_rippling_jobs("example-board")
    assert sorted(r["job"] for r in results) == ["detail-a", "detail-b"]
    assert mock_get_json.call_count == 3


@patch("ingestion.rippling_extractor.get_json", side_effect=_fake_get_json)
@patch("ingestion.rippling_extractor.as_completed", side_effect=lambda futures: futures)
@patch("ingestion.rippling_extractor.ThreadPoolExecutor")
def test_fetch_rippling_jobs_limits_concurrency_to_five(mock_executor, mock_as_completed, mock_get_json):
    executor_instance = mock_executor.return_value.__enter__.return_value
    executor_instance.submit.side_effect = lambda fn, board, job_id: _Future(
        _fake_get_json(f"{board}/jobs/{job_id}")
    )
    fetch_rippling_jobs("example-board")
    assert mock_executor.call_args.kwargs == {"max_workers": 5}


@patch("ingestion.rippling_extractor.get_json")
@patch("ingestion.rippling_extractor.as_completed", side_effect=lambda futures: futures)
def test_fetch_rippling_jobs_paginates_list_results(mock_as_completed, mock_get_json):
    def paged(url, **kwargs):
        if url.endswith("/jobs"):
            page = kwargs["params"]["page"]
            if page == 0:
                return {"items": [{"id": "a"}], "page": 0, "totalPages": 2}
            return {"items": [{"id": "b"}], "page": 1, "totalPages": 2}
        return {"id": url.rsplit("/", 1)[-1]}

    mock_get_json.side_effect = paged
    results = fetch_rippling_jobs("example-board")
    assert sorted(result["id"] for result in results) == ["a", "b"]
    assert mock_get_json.call_count == 4


@patch("ingestion.rippling_extractor.get_json")
@patch("ingestion.rippling_extractor.as_completed", side_effect=lambda futures: futures)
def test_fetch_rippling_jobs_single_detail_failure_does_not_abort(mock_as_completed, mock_get_json):
    def flaky(url, **kwargs):
        if url.endswith("/jobs"):
            return {
                "items": [{"id": "a"}, {"id": "b"}],
                "page": 0,
                "totalPages": 1,
            }
        if url.endswith("/a"):
            raise SourceHttpError("detail a failed")
        return {"job": "detail-b"}

    mock_get_json.side_effect = flaky
    results = fetch_rippling_jobs("example-board")
    assert results == [{"job": "detail-b"}]


def test_fetch_rippling_jobs_missing_slug_raises_config_error():
    with pytest.raises(RipplingConfigError):
        fetch_rippling_jobs("")
