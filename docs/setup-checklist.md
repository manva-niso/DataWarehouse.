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

## Databricks

- [x] Verify catalog/schema access (`SHOW CATALOGS` lists `samples`, `system`, `workspace`; default session is `workspace.default`).
- [x] Run `uv run python -m orchestration.apply_schema` — 15 statements applied, rerunnable.
- [x] Run Adzuna, Greenhouse, Lever, and Rippling/Gather raw ingestion and verify source row counts (50, 892, 697, and 1 in the verified run).
- [x] Run normalization and deduplication; verify `staging_postings` (1,602 postings in the verified run).
- [x] Run dimension and fact loads twice; verify idempotency and SCD2 current-version uniqueness.
- [x] Refresh the mart views and verify each view definition (all 4 marts return rows).
- [x] Verify `pipeline_run_log` and `data_quality_log`; all four configured sources logged SUCCESS.
- [x] Verify raw retention cleanup with a positive 30-day window (`cleanup_raw_tables`).

## Presentation

- [ ] Choose Power BI Desktop or Tableau Free Edition.
- [ ] Connect the chosen BI tool to Databricks marts only (HTTP path + PAT; see `dashboard/README.md`).
- [ ] Build 3-4 dashboard visuals.
- [x] Generate verified mart-based preview screenshots in `docs/screenshots/`.
- [ ] Export final native dashboard screenshots from Power BI/Tableau.
- [x] Generate the sample Excel workbook from `mart_application_tracker` (49 rows; `exports/application_tracker.xlsx`).
- [ ] Verify zero-row export, missing closing date, and locked-file retry behavior.
