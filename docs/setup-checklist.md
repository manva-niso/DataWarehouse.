# Setup Checklist

## Backend Choice

- BigQuery Sandbox cannot run this pipeline unchanged (no DML, no streaming, 60-day table expiry); billing-enabled BigQuery was not available.
- Chosen backend: **Databricks Free Edition** — no payment method required, permanent, Unity Catalog with a managed `workspace` catalog. Verified live: schema, MERGE, CTAS, views, DML, retention-style DELETE all work.

## Credentials

- [x] Create the Databricks workspace and a SQL warehouse (Free Edition).
- [x] Create a personal access token with scope "SQL warehouse" (and "Other API" if needed).
- [x] Add `DATABRICKS_HOST`, `DATABRICKS_HTTP_PATH`, `DATABRICKS_TOKEN`, `DATABRICKS_CATALOG=workspace`, `DATABRICKS_SCHEMA=default` to local `.env`.
- [x] Create Adzuna credentials and add `ADZUNA_APP_ID` and `ADZUNA_APP_KEY` to local `.env`.
- [ ] Add non-secret company board slugs to `config/companies.yaml`.
- [ ] Add any secret board tokens to local `.env`, never to tracked files.
- [ ] Authenticate OpenCode Go outside this repository if the configured agents are used.

## Databricks

- [x] Verify catalog/schema access (`SHOW CATALOGS` lists `samples`, `system`, `workspace`; default session is `workspace.default`).
- [x] Run `uv run python -m orchestration.apply_schema` — 15 statements applied, rerunnable.
- [x] Run the Adzuna raw ingestion and verify `raw_adzuna` row counts (50 per run, append-only).
- [x] Run normalization and deduplication; verify `staging_postings` (100 raw rows → 49 postings).
- [x] Run dimension and fact loads twice; verify idempotency (fact_job_posting still 49 rows after rerun).
- [x] Refresh the mart views and verify each view definition (all 4 marts return rows).
- [x] Verify `pipeline_run_log` and `data_quality_log` on success, zero rows, and partial failure (greenhouse FAILED, others SUCCESS → overall PARTIAL).
- [ ] Verify raw retention cleanup with a positive test window (`cleanup_raw_tables`).

## Presentation

- [ ] Choose Power BI Desktop or Tableau Free Edition.
- [ ] Connect the chosen BI tool to Databricks marts only (HTTP path + PAT; see `dashboard/README.md`).
- [ ] Build 3-4 dashboard visuals.
- [ ] Export dashboard screenshots to `docs/screenshots/`.
- [x] Generate the sample Excel workbook from `mart_application_tracker` (49 rows; `exports/application_tracker.xlsx`).
- [ ] Verify zero-row export, missing closing date, and locked-file retry behavior.
