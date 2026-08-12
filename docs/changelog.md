# Changelog

(Coder and reviewer agents append one line per significant change here. Do not rewrite this file; only append.)

- Updated OpenCode Go routing to reserve scarce models for architecture, planning, and orchestration while assigning high-volume models to implementation.
- Added the rerunnable BigQuery schema and seeded the four required source dimension values; warehouse loads remain next in the build order.
- Added the integration registry and setup checklist for credentials, APIs, BigQuery, BI tools, Excel, and cross-module contracts.
- Added the Adzuna extractor (country allowlist, 429 retry honoring Retry-After, typed parse/config/API failures) and the shared raw BigQuery writer with an empty-payload guard; 11 tests pass.
- Added staging normalization and deduplication SQL, warehouse dimension and fact loads (idempotent MERGE upserts, disappeared postings never deleted), and skill-mention derivation from a seed dictionary.
- Added `mart_skill_demand_trend` and `mart_application_tracker` views.
- Added the Excel export and `mark_application` with validation and locked-file retry; 17 tests pass. Dashboard connection guide added under `dashboard/`.
- Review pass: fixed the Adzuna search parameter to the API's `what` key, and added the specified Python interfaces `load_dim_company`, `load_fact_job_posting`, and `refresh_mart_views` over the SQL files; 21 tests pass.
- Added Greenhouse, Lever, and Rippling extractors plus a shared HTTP helper (429 retry honoring Retry-After, parse-error isolation); Rippling detail calls are concurrency-limited to 5 and single-detail failures do not abort the run; 40 tests pass.
- Added staging data-quality checks, the pipeline orchestrator (watermark with 30-day default, run logging that always executes, exclusive file lock), SCD2 company versioning, and raw-table retention cleanup; 51 tests pass.
- Added the final mart views `mart_hiring_velocity` and `mart_company_activity`; all four mart views are now code-complete.
- Documented BigQuery Sandbox limitations and isolated dotenv loading in the credentials test; final verification: 51 tests pass.
- Initialized a uv project (pyproject.toml + uv.lock, venv in .venv): dependencies now tracked via uv add; all 51 tests pass under uv run pytest.
- Backend switch to Databricks Free Edition: added the `dbio/` package (databricks-sql-connector wrapper with run_sql, run_sql_script, query_rows, insert_rows), ported all SQL to Spark SQL / Delta dialect (get_json_object, MD5 ids, SEQUENCE/EXPLODE calendar, RLIKE skill matching, null-safe MERGE), and rewrote bigquery_io, loaders, refresh, data_quality_checks, export_tracker, and run_pipeline to use dbio; added orchestration/apply_schema.py (splits schema.sql per statement); 51 tests pass.
- Live Databricks verification (2026-08-12): Unity Catalog only (hive_metastore disabled), so DATABRICKS_CATALOG=workspace; discovered and fixed dotenv loading from project root and disabled driver telemetry; schema applied (15 statements), pipeline ran end-to-end (Adzuna 50 rows → 49 deduped postings → dims/facts/4 marts), DQ rules PASS, run logged PARTIAL (greenhouse token missing), second run confirmed idempotency, and a 49-row Excel export was written to exports/application_tracker.xlsx.
- Added Greenhouse/Lever/Rippling normalization branches, correct Greenhouse ISO and Lever epoch-millisecond date parsing, company enrichment from `config/companies.yaml`, and verified public Greenhouse boards (`figma`, `stripe`, `coinbase`) plus Lever boards (`leverdemo`, `palantir`). A live run loaded 50 Adzuna, 892 Greenhouse, and 697 Lever payloads; staging produced 1,601 postings and all DQ rules passed. Rippling remains supported but has no verified public board slug.
- Hardened Databricks batch inserts with multi-row, size-aware parameter chunks (the connector has a 1 MB parameter limit), added stale-lock recovery and visible pipeline stage progress; 57 tests pass.
- Activated Rippling with the confirmed public Gather board: migrated to the `ats.rippling.com/api/v2/board/{slug}/jobs` list/detail API, added pagination and verified field normalization, loaded one live Rippling posting, and logged the run successfully. Converted and wired the Databricks SCD2 company SQL and verified the 30-day raw retention cleanup; 58 tests pass.
