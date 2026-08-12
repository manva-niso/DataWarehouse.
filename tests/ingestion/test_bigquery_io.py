import pytest

from ingestion.bigquery_io import write_to_bigquery_raw


def test_write_to_bigquery_raw_empty_payload_returns_zero():
    assert write_to_bigquery_raw("adzuna", [], "run-empty") == 0


def test_write_to_bigquery_raw_unknown_source_raises_value_error():
    with pytest.raises(ValueError):
        write_to_bigquery_raw("unknown", [{"id": 1}], "run-1")
