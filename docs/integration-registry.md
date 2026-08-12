# Integration Registry

This is the connection source of truth for future modules. It records what
must be configured, where data moves, and which external actions remain. It
never contains secret values.

## Credential Inventory

| System | Credential or setting | Storage | Required by | Status |
|---|---|---|---|---|
| Databricks | `DATABRICKS_HOST` | `.env` | Every warehouse operation via `dbio` | VERIFIED |
| Databricks | `DATABRICKS_HTTP_PATH` | `.env` | Every warehouse operation via `dbio` | VERIFIED |
| Databricks | `DATABRICKS_TOKEN` (SQL warehouse scope) | `.env` | Every warehouse operation via `dbio` | VERIFIED |
| Databricks | `DATABRICKS_CATALOG`, `DATABRICKS_SCHEMA` | `.env` | Default namespace; `workspace` / `default` | VERIFIED |
| Adzuna | `ADZUNA_APP_ID` | `.env` | `fetch_adzuna_jobs` | VERIFIED live |
| Adzuna | `ADZUNA_APP_KEY` | `.env` | `fetch_adzuna_jobs` | VERIFIED live |
| Greenhouse | Board token or board identifier | `.env` / `config/companies.yaml` per `AGENTS.md` | `fetch_greenhouse_jobs` | VERIFIED live (`figma`, `stripe`, `coinbase`) |
| Lever | Company slug | `config/companies.yaml` | `fetch_lever_jobs` | VERIFIED live (`leverdemo`, `palantir`) |
| Rippling | Board slug | `config/companies.yaml` | `fetch_rippling_jobs` | No public board verified; endpoint remains an assumption |
| OpenCode Go | Provider authentication | OpenCode auth storage, outside this repo | Agent execution only | External setup |
| Power BI or Tableau | Databricks connector credentials (HTTP path + PAT) | BI tool credential store, outside this repo | Dashboard refresh | TODO |

Do not commit `.env`, PATs, API keys, access tokens, BI credentials, or
generated exports. Public board slugs may be tracked in
`config/companies.yaml`; secret board tokens must remain in `.env`.

## Databricks Notes

- Free Edition workspace runs Unity Catalog only: legacy `hive_metastore` is
  disabled (`UC_HIVE_METASTORE_DISABLED_EXCEPTION`). Use the managed `workspace`
  catalog, schema `default`; `SHOW CATALOGS` confirms `samples`, `system`, `workspace`.
- The SQL warehouse auto-starts on first query; keep it running during pipeline runs.
- `databricks-sql-connector` executes one statement per call, so multi-statement
  SQL files are split by `dbio.split_statements` / `run_sql_script`.
- Telemetry is disabled in `dbio` (`enable_telemetry=False`) because the driver's
  telemetry endpoint is not resolvable in this environment.
- `dbio` loads `.env` from the project root (not cwd), so connections work from
  any working directory.

## Source Connections

| Source | API action | Raw table | Normalization contract | Downstream consumers | Status |
|---|---|---|---|---|---|
| Adzuna | Paginated search by query, country, and page; validate country before request | `raw_adzuna` | Parse source dates and fields into common posting shape | `staging_postings`, warehouse facts, marts | VERIFIED live (50 rows) |
| Greenhouse | `GET api.greenhouse.io/v1/boards/{board_token}/jobs` | `raw_greenhouse` | Map board jobs and ISO dates into common posting shape | `staging_postings`, warehouse facts, marts | VERIFIED live (892 rows) |
| Lever | `GET api.lever.co/v0/postings/{company}?mode=json` | `raw_lever` | Map fields and epoch-millisecond dates into common posting shape | `staging_postings`, warehouse facts, marts | VERIFIED live (697 rows) |
| Rippling | List call followed by detail calls, max 5 concurrent details | `raw_rippling` | Merge list/detail payloads and normalize source dates | `staging_postings`, warehouse facts, marts | No public board verified; zero-row source handled cleanly |

All source failures are logged and isolated. A zero-result response is valid;
malformed JSON is logged as `PARSE_ERROR`; one failed source does not stop the
others; the full run fails only when every source fails.

## Databricks Actions

| Order | Action | Objects | Owning module | Status |
|---:|---|---|---|---|
| 1 | Verify catalog/schema access and warehouse HTTP path | Catalog, schema, SQL warehouse | Configuration / setup | DONE |
| 2 | Create the rerunnable warehouse schema and seed source values | `warehouse/schema.sql`, all schema tables | Warehouse | DONE (15 statements applied, rerunnable) |
| 3 | Append one JSON row per source payload and record `run_id`, `ingested_at` | `raw_*` | Ingestion | DONE (Adzuna 50, Greenhouse 892, Lever 697) |
| 4 | Normalize source-specific fields and types with replaceable output | `staging_postings` | Staging | DONE (1,601 deduplicated postings) |
| 5 | Deduplicate by normalized company, title, and location; preserve earliest `first_seen_at` | `staging_postings` | Staging | DONE |
| 6 | Upsert dimensions, including SCD2 company versions only on tracked changes | `dim_*` | Warehouse | DONE via `load_dim_company`; SCD2 upgrade in `scd2_company.sql` still TODO |
| 7 | Upsert facts on `(posting_id, date_posted)`; never delete disappeared postings | `fact_*` | Warehouse | DONE (idempotent rerun verified) |
| 8 | Write run and data-quality outcomes, including partial failures | `pipeline_run_log`, `data_quality_log` | Orchestration / Staging | DONE (PARTIAL run logged correctly) |
| 9 | Create or replace each mart view atomically | `marts/*` views | Marts | DONE (4 of 4 views return rows) |
| 10 | Query marts only for dashboard and Excel presentation | `mart_*` views | Dashboard / Export | DONE (Excel export live) |
| 11 | Delete raw rows older than the configured positive retention window | `raw_*` | Orchestration | CODE READY via `cleanup_raw_tables`; live run TODO |

## Export And Dashboard Actions

| System | Required action | Source allowed | Output or acceptance check | Status |
|---|---|---|---|---|
| Excel / openpyxl | Query `mart_application_tracker` in write-only mode | Marts only | Zero rows still produce headers; missing closing date displays `Not specified`; locked file retries with timestamp suffix | DONE (1,601-row live export in `exports/`) |
| Power BI Desktop | Connect to Databricks marts only and configure refresh credentials | Marts only | Build 3-4 visuals and save dashboard artifact under `dashboard/` if selected | TODO / choose tool |
| Tableau Free Edition | Alternative to Power BI; connect to Databricks marts only | Marts only | Build 3-4 visuals and save workbook artifact under `dashboard/` if selected | TODO / choose tool |
| Dashboard documentation | Export visual screenshots | Dashboard | Store PNGs under `docs/screenshots/` | TODO |

## Cross-Module Contracts

| Producer | Consumer | Contract to preserve |
|---|---|---|
| Ingestion raw writer | Staging | `raw_{source}` contains `payload` JSON text, `run_id`, and `ingested_at`; writes append and return row count |
| Staging | Warehouse | Normalized postings expose stable posting identity, source, company, location, dates, skills, `first_seen_at`, `last_seen_at`, and `is_incomplete` |
| Warehouse | Marts | Fact and dimension names/keys match `warehouse/schema.sql`; disappeared postings remain available for downstream closure logic |
| Marts | Dashboard | Dashboard reads mart views only, never raw or staging tables |
| Marts | Export | Export reads `mart_application_tracker` only and preserves the specified null rendering |
| Orchestration | Logs | Every source and overall run records status, row counts, and timestamps, including partial failure and `ALREADY_RUNNING` |
| `dbio` | All Python modules | `run_sql` (single statement), `run_sql_script` (multi-statement), `query_rows` (dict rows), `insert_rows` (batch) |

## Change Procedure

1. Add or update the credential name here before adding external-call code.
2. Record the raw table, normalized fields, downstream consumers, and failure behavior.
3. Update `docs/modules.md` and `docs/architecture.md` when a module boundary or interface changes.
4. Update this registry's status only after focused tests or a documented manual verification.
5. Never replace a placeholder with a secret value.
