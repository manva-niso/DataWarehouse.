# AGENTS.md

## HARD RULE — user confirmation required (never violates)
Any delete, update, or edit to ANY external user data — Google Mail, Google Sheets, Google Docs, Google Drive, or any other mail/sheet/doc/cloud file — requires the user to explicitly write the word `confirm` in chat before the change is executed. This includes:
- deleting, renaming, moving, or overwriting any file, email, sheet cell, doc text, or row
- editing or formatting existing content (appending new, additive content is also confirmed unless it is a brand-new file the user just asked to create)
- sending or deleting emails
- creating/appending data in bulk to an existing spreadsheet or document

Safe WITHOUT confirmation: reading/listening/viewing content, creating a brand-new file the user explicitly asked for, and writing entirely new files (e.g. creating a new Google Doc/Sheet as requested). When in doubt, ask first — never act.

## Project
Job Market Pulse — a data warehouse pipeline that ingests job postings from multiple sources, models them into a star schema on Databricks (Delta), and serves a dashboard + Excel export. Portfolio project for a Data Engineer Intern role — prioritize correctness of pipeline/warehouse patterns over UI polish.

## Stack
- Python 3.11+ (ingestion, staging orchestration, export)
- SQL — Databricks SQL / Spark SQL on Delta Lake (no dbt; plain numbered `.sql` files)
- Databricks Free Edition — single workspace catalog/schema (`workspace.default`) for raw + staging + warehouse + marts (no separate object store); access via `databricks-sql-connector` through the `dbio/` package
- `openpyxl` — Excel export
- Power BI Desktop or Tableau Free Edition — dashboard (connects to marts only, not raw/staging)
- No scheduler required — pipeline runs manually via `uv run python -m orchestration.run_pipeline`; apply DDL via `uv run python -m orchestration.apply_schema`

## Build order (follow this sequence)
1. Repo skeleton (folders below) + empty `.gitkeep` files
2. `warehouse/schema.sql` — full DDL first, before any ingestion code
3. One ingestion source only: **Adzuna** (`ingestion/adzuna_extractor.py`) → `raw_adzuna` table
4. `staging/01_normalize_postings.sql` + `staging/02_deduplicate.sql` → `staging_postings`
5. `warehouse/load_dimensions.sql` + `warehouse/load_facts.sql` → gold tables
6. `marts/mart_skill_demand_trend.sql` — first mart, prove the layer works end to end
7. `export/export_tracker.py` → sample `.xlsx`
8. Dashboard connected to marts, 3-4 visuals
9. Remaining ingestion sources: Greenhouse, Lever, then Rippling (in that order — Rippling is two-call, do it last)
10. `staging/data_quality_checks.py` + `data_quality_log`
11. `orchestration/pipeline_run_log`
12. SCD Type 2 on `dim_company`
13. `orchestration/cleanup_raw_tables.sql` (30-day retention)

Do not skip ahead to step 9+ before steps 1-8 work end to end on one source. One working vertical slice before scaling sources.

## Phase 2 roadmap (approved, see docs/ROADMAP.md)
Beyond the build order below, the approved Phase 2 plan adds: `job_posting_detail` (descriptions/URLs/salaries), `role_family` classification, applications status lifecycle + `job_notes` + `hidden_jobs` + `user_profile`, archive-then-delete retention for live facts, a rule-based job-matching engine (`mart_job_match`), a Streamlit CRUD app, six business-analytics marts (role market, seasonality, salary, source quality, funnel, longevity), Power BI + Tableau report builds, and a later RAG assistant. Follow `docs/ROADMAP.md` phases in order; re-verify with its per-phase commands.

## Repo structure
```
job-market-pulse/
├── ingestion/          # greenhouse_extractor.py, lever_extractor.py, rippling_extractor.py, adzuna_extractor.py, ingestion_orchestrator.py
├── staging/             # 01_normalize_postings.sql, 02_deduplicate.sql, data_quality_checks.py
├── warehouse/            # schema.sql, load_dimensions.sql, load_facts.sql, scd2_company.sql
├── marts/                # mart_skill_demand_trend.sql, mart_hiring_velocity.sql, mart_company_activity.sql, mart_application_tracker.sql
├── export/                # export_tracker.py
├── exports/               # generated .xlsx output (gitignore actual runs, keep one sample committed)
├── dashboard/             # .pbix or .twbx
├── docs/screenshots/      # PNG exports of dashboard visuals
├── orchestration/         # run_pipeline.py, cleanup_raw_tables.sql
├── config/                # companies.yaml (board tokens/slugs per company)
├── tests/                 # mirrors module structure, see Testing section
├── .env.example
├── requirements.txt
└── README.md
```

## Schema (target — build exactly this, star schema)
**Facts:**
- `fact_job_posting(posting_id, company_id, location_id, source_id, job_title, date_posted, closing_date, first_seen_at, last_seen_at, is_incomplete)`
- `fact_posting_skill_mention(posting_id, skill_id)`

**Dimensions:**
- `dim_company(company_id, company_name, display_name, valid_from, valid_to, is_current)` — SCD Type 2
- `dim_location(location_id, location_raw, location_normalized)`
- `dim_skill(skill_id, skill_name)`
- `dim_date(date_id, date, day_of_week, month, year)`
- `dim_source(source_id, source_name)` — values: Greenhouse, Lever, Rippling, Adzuna

**Raw (bronze, one table per source, append-only):**
- `raw_greenhouse`, `raw_lever`, `raw_rippling`, `raw_adzuna` — columns: `payload` (JSON type), `run_id`, `ingested_at`

**Tracking (manually maintained):**
- `applications(posting_id, date_applied)`

**Logging:**
- `pipeline_run_log(run_id, source, status, rows_written, started_at, ended_at)`
- `data_quality_log(run_id, rule_name, status, rows_affected, checked_at)`

## Function specs (signature + purpose — implement exactly these)

| Function | Signature | Purpose |
|---|---|---|
| Greenhouse fetch | `fetch_greenhouse_jobs(board_token: str) -> list[dict]` | GET `api.greenhouse.io/v1/boards/{board_token}/jobs` |
| Lever fetch | `fetch_lever_jobs(company_slug: str) -> list[dict]` | GET `api.lever.co/v0/postings/{company}?mode=json` (hard-code mode=json internally) |
| Rippling fetch | `fetch_rippling_jobs(board_slug: str) -> list[dict]` | List call, then per-job detail call, concurrency-limited (max 5) |
| Adzuna fetch | `fetch_adzuna_jobs(query: str, country: str, page: int) -> list[dict]` | Paginated search; validate `country` against allowlist before calling |
| Raw write | `write_to_bigquery_raw(source: str, payload: list[dict], run_id: str) -> int` | Append to `raw_{source}`, return row count |
| Retention cleanup | `cleanup_raw_tables(retention_days: int = 30) -> dict[str, int]` | Delete `raw_*` rows older than window; reject retention_days <= 0 |
| Dim company load | `load_dim_company(df) -> None` | Upsert with SCD2 versioning on tracked-attribute change only |
| Fact posting load | `load_fact_job_posting(df) -> None` | Upsert on (posting_id, date_posted); never delete on disappearance, just stop advancing last_seen_at |
| Watermark | `get_last_watermark(source: str) -> datetime` | Last successful run's timestamp per source; default to 30 days ago if none |
| Run logger | `log_pipeline_run(run_id, status, row_counts) -> None` | Write to `pipeline_run_log`, always runs even on partial failure |
| Mart refresh | `refresh_mart_views() -> None` | `CREATE OR REPLACE VIEW` for each mart — must be atomic per view |
| Excel export | `export_tracker_to_excel(output_path: str) -> str` | Query `mart_application_tracker`, write `.xlsx`, streamed/write-only mode for openpyxl |
| Mark applied | `mark_application(posting_id: str, date_applied: date) -> None` | Upsert into `applications`; validate posting_id exists and date not in future |
| Pipeline entrypoint | `run_pipeline.main()` | Runs all extractors → staging → warehouse → marts in sequence; file-lock to prevent concurrent runs |

## Critical edge cases (must be handled, not optional)
- Empty API response / zero results → valid outcome, not an error, log and continue
- One source failing → log and continue with remaining sources; only fail the whole run if ALL sources fail
- Malformed JSON from source → catch, log `PARSE_ERROR`, skip that source for this run
- Rate limit / 429 → respect `Retry-After` if present, else backoff and retry once, then fail gracefully
- Cross-source duplicate posting → dedup key = normalized(company_name) + title + normalized(location); keep earliest `first_seen_at`; document this as a known false-positive risk for exact-title-collision edge cases, don't try to solve perfectly
- Missing `closing_date` from a source that doesn't provide one → store as NULL in warehouse, render as `"Not specified"` in the Excel export (not blank — blank should only mean "not yet applied")
- Posting re-seen on a later day → update `last_seen_at`, do not create a duplicate fact row
- Posting no longer appears in any pull → do not keep it in the live facts forever: `is_likely_closed` is computed downstream in a mart as `last_seen_at < today - 3 days`, and postings that are past `closing_date` or absent for the configured retention window are ARCHIVED to `fact_job_posting_archive` (with `archive_reason`) and then removed from the live `fact_job_posting` — history is preserved in the archive for analytics; tracked applications/notes survive via a live ∪ archive union in the tracker mart (Phase 2, see `docs/ROADMAP.md`)
- `dim_company` unchanged attributes → do NOT create a new SCD2 version; only version on actual change
- Excel export with zero rows → still write valid file with headers, never crash
- Excel export file locked/open → catch PermissionError, retry once with timestamp-suffixed filename
- `mark_application` with unknown posting_id → raise a specific, clear error (not generic exception)
- Pipeline interrupted mid-run → must be safe to re-run (idempotent); raw tables are append-only, staging/gold steps use CREATE OR REPLACE / upserts
- Concurrent pipeline runs → file-based lock, second invocation logs `ALREADY_RUNNING` and exits cleanly

## Testing
Prioritize in this order (don't aim for 100% coverage):
1. Idempotency — safe to re-run any stage without corrupting data
2. Empty/zero-result behavior for every read/write function
3. Date/type parsing across all 4 sources' differing formats
4. Clear error messages on user-facing functions (`mark_application`, `export_tracker_to_excel`)
5. Retry/rate-limit logic — lower priority, document as "known limitation" if time-constrained rather than skipping silently

Put tests under `/tests`, mirroring the module structure (`tests/ingestion/`, `tests/staging/`, etc.). Name tests descriptively: `test_<condition>_<expected_behavior>()`.

## Conventions
- No dbt — plain, numbered SQL files, run directly against Databricks SQL (Spark SQL / Delta)
- No separate object store — Databricks `raw_*` Delta tables serve as the bronze layer; access via `dbio` (`dbio/` package wraps `databricks-sql-connector`)
- Dashboard and Excel export both read ONLY from `/marts` views, never from raw or staging directly — keeps business logic in one place
- Log everything to `pipeline_run_log` / `data_quality_log`; never fail silently
- Prefer partial success + logged failure over aborting the whole pipeline run
- API keys / board tokens in `.env`, never hardcoded; `config/companies.yaml` holds per-company board slugs/tokens (not secrets)
- Before adding or changing an external connection, update `docs/integration-registry.md` and `docs/setup-checklist.md`; never store secret values in tracked files.

## Out of scope (do not build unless explicitly asked)
- Always-on scheduler / continuous execution
- Separate object storage service (R2/S3) — Databricks handles raw + warehouse
- Frontend web app — dashboard tool + Excel export are the only presentation layers
- ML/forecasting features
