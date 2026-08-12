from pathlib import Path

STAGING_SQL_DIR = Path(__file__).parents[2] / "staging"


def _normalize_sql() -> str:
    return (STAGING_SQL_DIR / "01_normalize_postings.sql").read_text(encoding="utf-8")


def test_normalize_sql_covers_all_four_sources():
    sql = _normalize_sql()
    for source in ("raw_adzuna", "raw_greenhouse", "raw_lever", "raw_rippling"):
        assert f"FROM {source}" in sql


def test_normalize_sql_has_dedup_key_and_common_shape():
    sql = _normalize_sql()
    assert "dedup_key" in sql
    assert "CONCAT(LOWER(company_name)" in sql
    for column in (
        "posting_id",
        "source_id",
        "company_name",
        "location_normalized",
        "job_title",
        "date_posted",
        "closing_date",
        "is_incomplete",
    ):
        assert column in sql


def test_normalize_sql_keeps_source_specific_parsing():
    sql = _normalize_sql()
    assert "greenhouse-" in sql
    assert "$.first_published" in sql and "$.application_deadline" in sql
    assert "lever-" in sql
    assert "$.createdAt" in sql and "$.closedAt" in sql and "FROM_UNIXTIME" in sql
    assert "rippling-" in sql
