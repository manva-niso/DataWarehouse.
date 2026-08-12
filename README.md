# Job Market Pulse

Job Market Pulse is a manually run Python and Databricks (Delta) data warehouse pipeline for job-posting ingestion, star-schema modeling, dashboard marts, and Excel tracking.

Implementation follows the build order and contracts documented in `AGENTS.md`.

## Backend

Databricks Free Edition (Unity Catalog) — a single catalog/schema (`workspace.default`) holds raw, staging, warehouse, and mart tables. All Python warehouse access goes through the `dbio/` package (`databricks-sql-connector`). Connection settings live in `.env` (see `.env.example`).

## Commands

- Apply schema (rerunnable): `uv run python -m orchestration.apply_schema`
- Run the pipeline (extractors → staging → warehouse → marts): `uv run python -m orchestration.run_pipeline`
- Export the application tracker to Excel: `export/export_tracker.py`
- Test: `uv run pytest` (58 tests)

Live verification (2026-08-13): schema applied, Adzuna (50), Greenhouse (892), Lever (697), and Rippling/Gather (1) payloads loaded; staging now contains 1,602 postings, facts/dims/marts populated, all data-quality rules PASS, SCD2 company loading and 30-day cleanup verified, and the Excel export was regenerated.
