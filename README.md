# Job Market Pulse

Job Market Pulse is a manually run Python and Databricks (Delta) data warehouse pipeline for job-posting ingestion, star-schema modeling, dashboard marts, and Excel tracking.

Implementation follows the build order and contracts in `AGENTS.md`.

## Backend

Databricks Free Edition (Unity Catalog) — a single catalog/schema (`workspace.default`) holds raw, staging, warehouse, and mart tables. All Python warehouse access goes through the `dbio/` package (`databricks-sql-connector`). Connection settings live in `.env` (see `.env.example`).

## Commands

- Apply schema (rerunnable): `uv run python -m orchestration.apply_schema`
- Run the pipeline (extractors → staging → warehouse → marts): `uv run python -m orchestration.run_pipeline`
- Export the application tracker to Excel: `export/export_tracker.py`
- Test: `uv run pytest` (51 tests)

Live verification (2026-08-12): schema applied, Adzuna run ingested 50 postings, staging deduplicated to 49, facts/dims/marts populated, all data-quality rules PASS, Excel export written; second run confirmed idempotency (no duplicate facts).
