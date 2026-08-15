# Job Market Pulse — Complete Reference Guide (To Read, End to End)

> This document is the single source for understanding the entire project.
> It is written for someone who has never seen this codebase before — a new
> contributor, a reviewer, or an interviewer. Read it top to bottom and you
> will understand what the project is, how it works, why each decision was
> made, what went wrong during development, and how every piece fits together.

---

## Table of Contents

1. [What Is This Project?](#1-what-is-this-project)
2. [Technology Stack and Why](#2-technology-stack-and-why)
3. [Architecture at a Glance](#3-architecture-at-a-glance)
4. [Repository Structure](#4-repository-structure)
5. [Reading and Study Order](#5-reading-and-study-order)
6. [The Pipeline Step by Step](#6-the-pipeline-step-by-step)
7. [Source APIs Deep Dive](#7-source-apis-deep-dive)
8. [The Data Model](#8-the-data-model)
9. [Key Design Decisions and Why](#9-key-design-decisions-and-why)
10. [Every Edge Case and How It Is Handled](#10-every-edge-case-and-how-it-is-handled)
11. [Errors Encountered and How They Were Solved](#11-errors-encountered-and-how-they-were-solved)
12. [Testing Strategy and Coverage](#12-testing-strategy-and-coverage)
13. [How to Set Up and Run](#13-how-to-set-up-and-run)
14. [How to See and Use the Jobs](#14-how-to-see-and-use-the-jobs)
15. [How to Extend the Project](#15-how-to-extend-the-project)
16. [Interview Talking Points](#16-interview-talking-points)

---

## 1. What Is This Project?

Job Market Pulse is a data engineering pipeline that:

1. Pulls job postings from four public job-board APIs (Adzuna, Greenhouse, Lever, Rippling).
2. Stores the raw JSON responses in Databricks Delta Lake tables.
3. Normalizes the differing field names and date formats into one common shape.
4. Deduplicates postings that appear across multiple sources or multiple pulls.
5. Loads a star schema (dimensions + facts) in the warehouse.
6. Publishes four analytics views (marts) for dashboards and exports.
7. Exports an Excel application tracker.
8. Logs every run and every data-quality check.

The project was built as a portfolio piece for a Data Engineer Intern role. The
priority is correctness of pipeline and warehouse patterns — idempotency, source
isolation, data quality, and clean separation between raw, staging, gold, and
presentation layers — not UI polish.

### Verified Live State (2026-08-13)

| Source | Rows Ingested | Status |
|---|---|---|
| Adzuna | 50 | Live |
| Greenhouse (Figma, Stripe, Coinbase) | 892 | Live |
| Lever (leverdemo, palantir) | 697 | Live |
| Rippling (Gather) | 1 | Live |
| **Total raw payloads** | **1,640** | |
| **Deduplicated warehouse postings** | **1,602** | |

---

## 2. Technology Stack and Why

| Technology | What It Does Here | Why It Was Chosen |
|---|---|---|
| Python 3.12+ | Ingestion, orchestration, export | Standard DE language; rich REST and data libraries |
| uv | Dependency and environment management | Faster than pip; lockfile reproduction; simple CLI |
| Databricks Free Edition | Compute and storage (Delta Lake) | No credit card; permanent; Unity Catalog; real Spark SQL |
| Delta Lake | Table format | ACID; MERGE support; time travel; default in Databricks |
| databricks-sql-connector | Python-to-Databricks bridge | Official driver; supports parameterized queries |
| Requests | REST API calls | Standard; simple; supports timeouts and retries |
| openpyxl | Excel export | Write-only mode for large workbooks; styling support |
| PyYAML | config/companies.yaml | Human-readable non-secret configuration |
| pytest | Testing | Standard; descriptive test names; mock support |
| matplotlib (dev only) | Dashboard preview PNGs | Reproducible visual evidence without a BI tool |

### What Was Considered and Rejected

| Option | Why Rejected |
|---|---|
| BigQuery Sandbox | No DML without billing; 60-day table expiry |
| BigQuery with billing | No payment method available for free tier |
| Azure for Students | Student ID rejected |
| Neon Postgres | Considered as fallback; Databricks had better Spark SQL fit |
| dbt | Overkill for plain numbered SQL files; adds complexity |
| Separate S3/R2 object store | Databricks handles raw + warehouse in one catalog |
| Always-on scheduler | Out of scope; manual runs are sufficient for a portfolio |

---

## 3. Architecture at a Glance

```
┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│   Adzuna    │  │  Greenhouse  │  │    Lever    │  │   Rippling  │
│  REST API   │  │  REST API   │  │  REST API   │  │  REST API   │
└──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘
       │                │                │                │
       ▼                ▼                ▼                ▼
┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐
│raw_adzuna  │ │raw_greenhouse│ │raw_lever  │ │raw_rippling│
│  Delta     │ │  Delta      │ │  Delta    │ │  Delta     │
└──────┬─────┘ └──────┬─────┘ └──────┬─────┘ └──────┬─────┘
       │              │              │              │
       └──────────────┴──────────────┴──────────────┘
                      │
                      ▼
           ┌────────────────────────┐
           │staging_postings_normalized│
           │  UNION ALL of 4 sources  │
           │  Source-specific JSON    │
           │  parsing + date formats  │
           └───────────┬────────────┘
                       │
                       ▼
           ┌────────────────────────┐
           │  staging_postings       │
           │  Cross-source dedup    │
           │  Dedup key:             │
           │  company|title|location │
           └───────────┬────────────┘
                       │
                       ▼
     ┌─────────────────────────────────┐
     │       WAREHOUSE (Gold)          │
     │                                 │
     │  dim_company (SCD Type 2)      │
     │  dim_location                   │
     │  dim_skill (25 seed skills)    │
     │  dim_date (calendar)            │
     │  dim_source (4 sources)        │
     │  fact_job_posting (upsert)     │
     │  fact_posting_skill_mention    │
     │  applications (manual)         │
     └───────────┬─────────────────────┘
                 │
                 ▼
     ┌─────────────────────────────────┐
     │          MARTS (Views)          │
     │                                 │
     │  mart_application_tracker      │
     │  mart_skill_demand_trend       │
     │  mart_hiring_velocity          │
     │  mart_company_activity         │
     └───────────┬─────────────────────┘
                 │
        ┌────────┼────────┐
        ▼        ▼        ▼
   ┌────────┐┌───────┐┌──────────┐
   │ Excel  ││Power BI││ Tableau  │
   │ export ││/Tableau││          │
   └────────┘└───────┘└──────────┘
                 │
                 ▼
         External Python/SQL
         consumers (read marts only)
```

### Data Flow Rules

- Raw tables are append-only. No updates or deletes during normal ingestion.
- Staging tables are CREATE OR REPLACE — rebuilt on every run.
- Warehouse facts use MERGE (upsert) — never delete disappeared postings.
- Marts are CREATE OR REPLACE VIEW — atomic per view.
- External consumers read marts only, never raw or staging.

---

## 4. Repository Structure

```
codes/
├── ingestion/                    # REST API extractors
│   ├── adzuna_extractor.py        #   Paginated search; country allowlist; 429 retry
│   ├── greenhouse_extractor.py    #   Board token → jobs list
│   ├── lever_extractor.py         #   Company slug → postings (mode=json)
│   ├── rippling_extractor.py      #   List + detail calls; max 5 concurrent
│   ├── bigquery_io.py             #   Raw table writer (writes to Databricks via dbio)
│   └── http_utils.py               #   Shared HTTP helper with retry and parse-error handling
├── dbio/                          # Databricks connection layer (the ONLY DB access point)
│   ├── __init__.py                 #   Re-exports: run_sql, run_sql_script, query_rows, insert_rows
│   └── databricks.py               #   Connection, statement splitting, size-aware batch inserts
├── staging/                        # Bronze → Silver transformations
│   ├── 01_normalize_postings.sql   #   4 UNION ALL branches; source-specific JSON parsing
│   ├── 02_deduplicate.sql          #   Cross-source dedup; keep earliest first_seen_at
│   └── data_quality_checks.py      #   4 DQ rules; PASS/FAIL/WARN; writes to data_quality_log
├── warehouse/                      # Silver → Gold
│   ├── schema.sql                  #   All 14 Delta table DDL + dim_source seed MERGE
│   ├── load_dimensions.sql         #   dim_date, dim_location, dim_skill (CTAS) + dim_company (MERGE)
│   ├── load_facts.sql              #   fact_job_posting (MERGE upsert) + skill mentions (CTAS)
│   ├── scd2_company.sql            #   SCD Type 2: close old versions, open new on change
│   └── loaders.py                  #   Python interface: load_dim_company(), load_fact_job_posting()
├── marts/                          # Gold → Presentation
│   ├── mart_skill_demand_trend.sql #   Skills × year-month → postings count
│   ├── mart_hiring_velocity.sql    #   Company × year-month → postings count
│   ├── mart_company_activity.sql   #   Company → total/active/likely_closed counts
│   ├── mart_application_tracker.sql#   One row per posting + application date + likely_closed flag
│   └── refresh.py                  #   refresh_mart_views() — runs all .sql files atomically
├── orchestration/                  # Pipeline coordination
│   ├── apply_schema.py             #   Splits schema.sql per statement; runs each via dbio
│   ├── run_pipeline.py             #   Full pipeline: extract → raw → stage → DQ → load → marts
│   └── cleanup_raw_tables.sql      #   DELETE template for retention window
├── export/                         # Presentation
│   └── export_tracker.py           #   Excel export + mark_application()
├── exports/                        # Generated output
│   └── application_tracker.xlsx    #   Sample committed; runtime files gitignored
├── dashboard/                      # Presentation
│   ├── README.md                   #   BI tool connection instructions
│   ├── dashboard-spec.md           #   Visual spec: 4 visuals, fields, filters
│   └── generate_screenshots.py     #   Reproducible PNG previews from marts
├── docs/                           # Documentation
│   ├── architecture.md             #   Decisions and boundaries
│   ├── setup-checklist.md          #   Step-by-step setup with checkboxes
│   ├── integration-registry.md     #   Every credential, endpoint, and status
│   ├── outputs-guide.md            #   How to consume tables, SQL examples, Python consumer
│   ├── changelog.md                #   Append-only history of significant changes
│   ├── modules.md                  #   Module dependency graph
│   └── screenshots/                #   PNG previews
│       ├── skill-demand-trend.png
│       ├── hiring-velocity.png
│       ├── company-activity.png
│       └── application-tracker.png
├── tests/                          # 58 tests
│   ├── ingestion/                   #   Extractors, HTTP retry, empty results, config errors
│   ├── dbio/                       #   Statement splitting, multi-row insert batching
│   ├── staging/                    #   DQ checks, normalization SQL content
│   ├── warehouse/                  #   Loader SQL execution, SCD2 SQL
│   ├── export/                     #   Excel export, error handling, mark_application
│   └── orchestration/              #   Lock, watermark, logging, cleanup, main partial failure
├── config/
│   └── companies.yaml              #   Public board identifiers (non-secret)
├── .env.example                    #   Template for secrets
├── .gitignore                      #   Excludes .env, .venv, caches, .opencode
├── AGENTS.md                       #   Engineering specification (schema, contracts, edge cases)
├── PROJECT.md                      #   Technical project guide
├── README.md                       #   Full project overview
├── pyproject.toml                  #   Dependencies and project metadata
├── requirements.txt                #   Flat dependency list
└── uv.lock                         #   Reproducible lockfile
```

---

## 5. Reading and Study Order

Read these files in this exact order to build understanding incrementally:

### Phase 1: Understand the What and Why

| Step | File | What You Learn |
|---|---|---|
| 1 | `README.md` | Project purpose, commands, verified metrics |
| 2 | `AGENTS.md` | Complete spec: schema, function contracts, edge cases, build order |
| 3 | `PROJECT.md` | Technical guide: system boundary, technology, table catalogue, operations |
| 4 | `docs/architecture.md` | Key architectural decisions |
| 5 | `docs/outputs-guide.md` | How to consume outputs; SQL/Python examples |

### Phase 2: Understand the Configuration

| Step | File | What You Learn |
|---|---|---|
| 6 | `.env.example` | Required environment variables (Databricks + Adzuna) |
| 7 | `config/companies.yaml` | Public board identifiers for Greenhouse, Lever, Rippling |

### Phase 3: Understand the Connection Layer

| Step | File | What You Learn |
|---|---|---|
| 8 | `dbio/databricks.py` | How Python talks to Databricks; statement splitting; size-aware inserts |
| 9 | `dbio/__init__.py` | Public API: run_sql, run_sql_script, query_rows, insert_rows |

### Phase 4: Understand the Schema

| Step | File | What You Learn |
|---|---|---|
| 10 | `warehouse/schema.sql` | All 14 tables, their columns, and the dim_source seed |

### Phase 5: Understand Ingestion

| Step | File | What You Learn |
|---|---|---|
| 11 | `ingestion/http_utils.py` | Shared HTTP helper; retry; parse-error handling |
| 12 | `ingestion/adzuna_extractor.py` | Country allowlist; 429 retry; paginated search |
| 13 | `ingestion/greenhouse_extractor.py` | Board token → job list |
| 14 | `ingestion/lever_extractor.py` | Company slug → postings with mode=json |
| 15 | `ingestion/rippling_extractor.py` | List + detail; pagination; 5-worker concurrency |
| 16 | `ingestion/bigquery_io.py` | Raw table writer (named for legacy; writes via dbio) |

### Phase 6: Understand Staging

| Step | File | What You Learn |
|---|---|---|
| 17 | `staging/01_normalize_postings.sql` | 4 UNION ALL branches; per-source JSON parsing |
| 18 | `staging/02_deduplicate.sql` | Cross-source dedup; earliest first_seen_at |
| 19 | `staging/data_quality_checks.py` | 4 DQ rules; PASS/FAIL/WARN; logging |

### Phase 7: Understand the Warehouse

| Step | File | What You Learn |
|---|---|---|
| 20 | `warehouse/load_dimensions.sql` | dim_date, dim_location, dim_skill (CTAS) + dim_company (MERGE) |
| 21 | `warehouse/load_facts.sql` | fact_job_posting (MERGE upsert) + skill mentions (CTAS with RLIKE) |
| 22 | `warehouse/scd2_company.sql` | SCD Type 2: close old, open new on display_name change |
| 23 | `warehouse/loaders.py` | Python interface calling the SQL files |

### Phase 8: Understand Marts

| Step | File | What You Learn |
|---|---|---|
| 24 | `marts/mart_application_tracker.sql` | Main job view + is_likely_closed + application date |
| 25 | `marts/mart_skill_demand_trend.sql` | Skills × year-month |
| 26 | `marts/mart_hiring_velocity.sql` | Company × year-month → posting volume |
| 27 | `marts/mart_company_activity.sql` | Active vs likely closed per company |
| 28 | `marts/refresh.py` | Runs all .sql files atomically |

### Phase 9: Understand Orchestration

| Step | File | What You Learn |
|---|---|---|
| 29 | `orchestration/apply_schema.py` | Splits schema.sql; runs one statement at a time |
| 30 | `orchestration/run_pipeline.py` | Full pipeline coordination; locking; logging; partial failure |
| 31 | `orchestration/cleanup_raw_tables.sql` | Retention DELETE template |

### Phase 10: Understand Export and Dashboard

| Step | File | What You Learn |
|---|---|---|
| 32 | `export/export_tracker.py` | Excel generation; mark_application; locked-file retry |
| 33 | `dashboard/dashboard-spec.md` | Visual spec for Power BI/Tableau |
| 34 | `dashboard/generate_screenshots.py` | Reproducible PNG previews from marts |
| 35 | `dashboard/README.md` | BI tool connection instructions |

### Phase 11: Understand Tests

| Step | File | What You Learn |
|---|---|---|
| 36 | `tests/ingestion/test_adzuna_extractor.py` | Country validation, 429 retry, empty results |
| 37 | `tests/ingestion/test_greenhouse_extractor.py` | Empty token error, empty board |
| 38 | `tests/ingestion/test_lever_extractor.py` | Empty slug error |
| 39 | `tests/ingestion/test_rippling_extractor.py` | List+detail, concurrency, single-failure isolation, pagination |
| 40 | `tests/ingestion/test_http_utils.py` | Retry, parse-error |
| 41 | `tests/ingestion/test_bigquery_io.py` | Empty payload, unknown source |
| 42 | `tests/dbio/test_databricks.py` | Statement splitting, multi-statement, chunking |
| 43 | `tests/staging/test_data_quality_checks.py` | All pass, failed rule counted, zero postings = WARN |
| 44 | `tests/staging/test_staging_sql.py` | All 4 source branches present, dedup key, source-specific parsing |
| 45 | `tests/warehouse/test_loaders.py` | Dimensions SQL, facts SQL, SCD2 SQL, marts execution |
| 46 | `tests/export/test_export_tracker.py` | Zero rows, missing closing date, locked file, mark_application |
| 47 | `tests/orchestration/test_run_pipeline.py` | Lock rejection, watermark, logging, cleanup, partial failure |

---

## 6. The Pipeline Step by Step

When you run `uv run python -m orchestration.run_pipeline`, here is exactly
what happens, in order:

### Step 1: Lock Acquisition
- The pipeline tries to create a file `orchestration/.pipeline.lock` with the
  process PID.
- If the file already exists, it checks whether the PID inside is still running.
- If the PID is dead, the lock is stale and is removed; the pipeline proceeds.
- If the PID is alive, the pipeline logs `ALREADY_RUNNING` and exits.

### Step 2: Source Extraction (4 sources, sequentially)

For each source in order: adzuna, greenhouse, lever, rippling.

**Adzuna:**
- Reads `ADZUNA_QUERY`, `ADZUNA_COUNTRY`, `ADZUNA_PAGES` from `.env`.
- Validates the country against a 20-country allowlist.
- Fetches each page from `api.adzuna.com/v1/api/jobs/{country}/search/{page}`.
- Stops pagination early if a page returns fewer than 50 results.
- If 429: honors `Retry-After` header, retries once, then fails gracefully.
- Returns a list of job dictionaries.

**Greenhouse:**
- Reads companies from `config/companies.yaml` that have `greenhouse_board_token`.
- For each company (Figma, Stripe, Coinbase), fetches `api.greenhouse.io/v1/boards/{token}/jobs`.
- Enriches each job with `company_display_name` from the config.
- If no config entries, falls back to `GREENHOUSE_BOARD_TOKEN` from `.env`.

**Lever:**
- Reads companies from `config/companies.yaml` that have `lever_company_slug`.
- For each company (leverdemo, palantir), fetches `api.lever.co/v0/postings/{slug}?mode=json`.
- Enriches each posting with `company_display_name` from the config.

**Rippling:**
- Reads companies from `config/companies.yaml` that have `rippling_board_slug`.
- For each company (Gather), fetches `ats.rippling.com/api/v2/board/{slug}/jobs`.
- Paginates the list call using `page` and `pageSize` parameters.
- For each job ID, fetches the detail endpoint concurrently (max 5 threads).
- Single detail failures are logged and skipped; the list continues.

**Error isolation:** If any source fails, it is logged as `FAILED` and the
pipeline continues with the remaining sources. Zero results is a valid `SUCCESS`.

### Step 3: Raw Writes
- For each source, `write_to_bigquery_raw(source, payload, run_id)` serializes
  each job dict to JSON text and inserts it into `raw_{source}` with the
  `run_id` and a UTC timestamp.
- Inserts use size-aware multi-row batches (Databricks limits parameterized
  queries to ~1 MB total).

### Step 4: Per-Source Logging
- Each source's status (SUCCESS/FAILED) and row count is written to
  `pipeline_run_log`.

### Step 5: Staging
- `01_normalize_postings.sql` runs: creates `staging_postings_normalized` by
  UNION ALL-ing four branches, one per source. Each branch parses the
  source-specific JSON fields into the common posting shape.
- `02_deduplicate.sql` runs: creates `staging_postings` by grouping on the
  dedup key (`lower(company)|lower(title)|lower(location_normalized)`) and
  keeping the earliest `first_seen_at` and latest `last_seen_at`.

### Step 6: Data-Quality Checks
- `run_data_quality_checks(run_id)` runs 4 rules:
  1. `duplicate_posting_ids` — expects 0 duplicates
  2. `null_required_fields` — expects 0 nulls in posting_id, job_title, company_name
  3. `future_date_posted` — expects 0 dates in the future
  4. `zero_postings` — WARN if 0, PASS if >0
- Each result is written to `data_quality_log`.

### Step 7: Warehouse Loads
- `load_dim_company()` runs `load_dimensions.sql` then `scd2_company.sql`:
  - `dim_date` is rebuilt from the date range in staging_postings.
  - `dim_location` is rebuilt from distinct normalized locations.
  - `dim_skill` is rebuilt from the 25-skill seed dictionary.
  - `dim_company` is MERGEd (insert-only for new companies).
  - SCD2: if a company's `display_name` changed, the old version is closed
    (`valid_to = now, is_current = false`) and a new current version is opened.
- `load_fact_job_posting()` runs `load_facts.sql`:
  - `fact_job_posting` is MERGEd on `(posting_id, date_posted)` with null-safe
    matching. Matched rows update `last_seen_at` and `first_seen_at = LEAST()`.
    Unmatched rows are inserted.
  - `fact_posting_skill_mention` is rebuilt by cross-joining staging with
    `dim_skill` and matching skills via RLIKE word-boundary regex.

### Step 8: Mart Refresh
- `refresh_mart_views()` runs each `mart_*.sql` file:
  - Each is a `CREATE OR REPLACE VIEW` — atomic per view.

### Step 9: Overall Logging
- The overall run status (SUCCESS, PARTIAL, or FAILED) and total row count
  are written to `pipeline_run_log`.

### Step 10: Lock Release
- The lock file is deleted in a `finally` block, even if the pipeline failed.

---

## 7. Source APIs Deep Dive

### Adzuna

```
URL:     https://api.adzuna.com/v1/api/jobs/{country}/search/{page}
Auth:    app_id + app_key query params
Format:  JSON
Dates:   ISO 8601 ("2026-07-23T10:00:00Z")
Country: Validated against 20-country allowlist BEFORE request
Retry:   429 → honor Retry-After, retry once, then raise AdzunaRateLimitError
```

Normalized fields:
- `id` → posting_id = `"adzuna-{id}"`
- `company.display_name` → company_name
- `location.display_name` → location_raw
- `title` → job_title
- `created` → date_posted (first 10 chars → TO_DATE)
- `description` → description
- closing_date = NULL (Adzuna does not provide one)

### Greenhouse

```
URL:     https://api.greenhouse.io/v1/boards/{board_token}/jobs
Auth:    None (public boards)
Format:  JSON
Dates:   ISO 8601 with timezone offset ("2024-11-01T06:05:10-04:00")
```

Verified boards: `figma` (159 jobs), `stripe` (567), `coinbase` (166).

Normalized fields:
- `id` → posting_id = `"greenhouse-{id}"`
- `company_name` (present in payload) → company_name (with config fallback)
- `location.name` → location_raw
- `title` → job_title
- `first_published` → date_posted (ISO date parse)
- `application_deadline` → closing_date (nullable; ISO date parse)
- `content` → description (may be NULL; not treated as incomplete)

### Lever

```
URL:     https://api.lever.co/v0/postings/{company_slug}?mode=json
Auth:    None (public postings)
Format:  JSON array
Dates:   Epoch MILLISECONDS (1553186035299)
```

Verified boards: `leverdemo` (388 postings), `palantir` (309).

Normalized fields:
- `id` (UUID string) → posting_id = `"lever-{id}"`
- `company` (often NULL in payload) → company_name (config display_name fallback)
- `categories.location` → location_raw
- `text` → job_title
- `createdAt` → date_posted (`FROM_UNIXTIME(CAST(createdAt AS BIGINT) / 1000)`)
- `closedAt` → closing_date (nullable; same epoch conversion)
- `descriptionPlain` → description

### Rippling

```
URL:     https://ats.rippling.com/api/v2/board/{board_slug}/jobs
Detail:  https://ats.rippling.com/api/v2/board/{board_slug}/jobs/{job_id}
Auth:    None (public board)
Format:  JSON
Dates:   ISO 8601 with microseconds ("2026-07-08T16:46:36.252000-07:00")
```

Verified board: `gather` (1 job — Director of Marketing, Remote US).

List response shape:
```json
{
  "items": [{"id": "uuid", "name": "title", ...}],
  "page": 0,
  "pageSize": 20,
  "totalItems": 1,
  "totalPages": 1
}
```

Detail response fields: `uuid`, `name`, `workLocations` (array), `createdOn`,
`description` (object with `company` and `role` HTML strings), `companyName`.

Normalized fields:
- `uuid` → posting_id = `"rippling-{uuid}"`
- `companyName` (from detail) → company_name (with config fallback)
- `workLocations[0]` → location_raw
- `name` → job_title
- `createdOn` → date_posted (ISO date parse)
- `description.role` or `description.company` → description
- closing_date = NULL (Rippling does not provide one)

---

## 8. The Data Model

### Star Schema

```
                     dim_date
                       │
           dim_source──fact_job_posting──dim_company (SCD2)
                       │
                  dim_location
                       │
              fact_posting_skill_mention
                       │
                    dim_skill

           applications (manual, joins on posting_id)
```

### Every Table and Column

#### Dimensions

**dim_company** (SCD Type 2)
| Column | Type | Purpose |
|---|---|---|
| company_id | STRING | MD5(lower(company_name)) — stable hash |
| company_name | STRING | Source company name |
| display_name | STRING | Display-friendly name (tracked for SCD2) |
| valid_from | TIMESTAMP | When this version opened |
| valid_to | TIMESTAMP | When this version closed (NULL = current) |
| is_current | BOOLEAN | True for the active version |

**dim_location**
| Column | Type | Purpose |
|---|---|---|
| location_id | STRING | MD5(location_normalized) |
| location_raw | STRING | Original location text |
| location_normalized | STRING | Whitespace-collapsed, trimmed |

**dim_skill** (25 seed skills)
| Column | Type | Purpose |
|---|---|---|
| skill_id | STRING | MD5(lower(skill_name)) |
| skill_name | STRING | SQL, Python, Spark, Kafka, AWS, etc. |

**dim_date**
| Column | Type | Purpose |
|---|---|---|
| date_id | BIGINT | yyyyMMdd as integer |
| date | DATE | Calendar date |
| day_of_week | STRING | Monday, Tuesday, etc. |
| month | BIGINT | 1-12 |
| year | BIGINT | 4-digit year |

**dim_source** (4 fixed values)
| source_id | source_name |
|---|---|
| greenhouse | Greenhouse |
| lever | Lever |
| rippling | Rippling |
| adzuna | Adzuna |

#### Facts

**fact_job_posting**
| Column | Type | Purpose |
|---|---|---|
| posting_id | STRING | Source-prefixed unique ID |
| company_id | STRING | FK to dim_company |
| location_id | STRING | FK to dim_location |
| source_id | STRING | FK to dim_source |
| job_title | STRING | Posting title |
| date_posted | DATE | Source posting date (nullable) |
| closing_date | DATE | Closing date (nullable) |
| first_seen_at | TIMESTAMP | Earliest ingestion timestamp |
| last_seen_at | TIMESTAMP | Latest ingestion timestamp |
| is_incomplete | BOOLEAN | True if required fields were missing |

**fact_posting_skill_mention**
| Column | Type | Purpose |
|---|---|---|
| posting_id | STRING | FK to fact_job_posting |
| skill_id | STRING | FK to dim_skill |

#### Raw (Bronze, append-only)

All four raw tables have the same structure:

| Column | Type | Purpose |
|---|---|---|
| payload | STRING | Full API response JSON text |
| run_id | STRING | Pipeline run identifier |
| ingested_at | TIMESTAMP | UTC ingestion timestamp |

#### Manual Tracking

**applications**
| Column | Type | Purpose |
|---|---|---|
| posting_id | STRING | FK to fact_job_posting |
| date_applied | DATE | User-set application date |

#### Logging

**pipeline_run_log**
| Column | Type | Purpose |
|---|---|---|
| run_id | STRING | Run identifier |
| source | STRING | Source name or "OVERALL" |
| status | STRING | SUCCESS, FAILED, PARTIAL |
| rows_written | BIGINT | Rows written for this source |
| started_at | TIMESTAMP | Run start |
| ended_at | TIMESTAMP | Run end |

**data_quality_log**
| Column | Type | Purpose |
|---|---|---|
| run_id | STRING | Run identifier |
| rule_name | STRING | DQ rule name |
| status | STRING | PASS, FAIL, WARN |
| rows_affected | BIGINT | Rows matching the rule |
| checked_at | TIMESTAMP | Check timestamp |

#### Marts (Views)

**mart_application_tracker** — the main job view
| Column | Source |
|---|---|
| posting_id | fact_job_posting |
| company_name | dim_company (current) |
| job_title | fact_job_posting |
| location | dim_location |
| date_posted | fact_job_posting |
| closing_date | fact_job_posting |
| last_seen_at | fact_job_posting |
| is_likely_closed | computed: `last_seen_at < now - 3 days` |
| date_applied | applications (LEFT JOIN) |

**mart_skill_demand_trend** — skills × year-month

**mart_hiring_velocity** — company × year-month → posting count

**mart_company_activity** — company → total, active, likely_closed counts

---

## 9. Key Design Decisions and Why

### Why Delta Lake instead of BigQuery?
BigQuery Sandbox required billing for DML. Databricks Free Edition provides
Delta Lake with full MERGE support at no cost.

### Why one catalog/schema for everything?
No separate object store is needed. Databricks handles raw, staging, gold,
and marts in `workspace.default`. This simplifies the pipeline and avoids
cross-platform data movement.

### Why the `dbio/` package?
Centralizing all database access in one package means every module talks to
Databricks the same way. If the driver or connection logic changes, only one
file needs updating. It also makes testing easy — mock `dbio` and the whole
pipeline is testable without a live warehouse.

### Why `run_sql_script` instead of `cursor.executemany`?
The Databricks SQL connector executes one statement per `cursor.execute()` call.
Multi-statement SQL files (like `load_dimensions.sql` with 4 statements) would
fail if sent as one string. `run_sql_script` splits on semicolons and runs each
statement separately.

### Why multi-row INSERT instead of `executemany`?
Testing revealed that `executemany` on Free Edition executes row-by-row, each
taking ~3 seconds. 892 rows took 2.5 minutes. Multi-row `VALUES` inserts reduced
this to ~15 seconds. The 1 MB parameter limit required size-aware chunking.

### Why a file-based lock?
Prevents concurrent pipeline runs from double-writing raw tables or corrupting
staging. The lock includes the PID so stale locks from killed processes can be
detected and removed.

### Why keep `write_to_bigquery_raw` as the function name?
The AGENTS.md function spec defines this name as the public contract. Renaming
would break the contract even though the backend changed. The function now
writes to Databricks, but the name is preserved for spec compliance.

### Why enrich payloads with `company_display_name`?
Greenhouse jobs do not include a company name in the payload. Lever postings
have `company = null` in practice. The pipeline adds `company_display_name`
from `config/companies.yaml` at fetch time so normalization can use it.

### Why RLIKE for skill matching?
The seed skill dictionary has single-word and multi-word skills. `RLIKE` with
word boundaries (`\bPython\b`) matches skills in the job title and description
without requiring a full NLP pipeline. It is documented as a heuristic.

### Why is `is_likely_closed` in a mart, not in the fact?
The 3-day absence rule is a business metric, not a source-of-truth fact. If the
rule changes, only the mart SQL needs updating, not the fact table.

---

## 10. Every Edge Case and How It Is Handled

| Edge Case | How It Is Handled | Where in Code |
|---|---|---|
| Empty API response / zero results | Valid outcome; logged as SUCCESS with 0 rows | `run_pipeline.py` try/except per source |
| One source fails | Logged as FAILED; other sources continue; pipeline fails only if ALL fail | `run_pipeline.py` source loop |
| Malformed JSON from API | Caught by `http_utils.get_json`; logged as PARSE_ERROR; source skipped | `ingestion/http_utils.py` |
| Rate limit (429) | Honor Retry-After if present; backoff 30s; retry once; then fail gracefully | `ingestion/adzuna_extractor.py` |
| Cross-source duplicate posting | Dedup key = lower(company) + title + lower(location); keep earliest first_seen_at | `staging/02_deduplicate.sql` |
| Missing closing_date | Stored as NULL in warehouse; rendered as "Not specified" in Excel | `export/export_tracker.py` `_format_row` |
| Posting re-seen later | MERGE updates last_seen_at; no duplicate fact row | `warehouse/load_facts.sql` WHEN MATCHED |
| Posting disappears from pull | NOT deleted; last_seen_at stops advancing; is_likely_closed computed in mart | `load_facts.sql` (no DELETE branch) |
| dim_company unchanged | No new SCD2 version; only version on display_name change | `warehouse/scd2_company.sql` |
| Excel export with zero rows | Still writes valid file with headers | `export/export_tracker.py` — append headers always |
| Excel export file locked | PermissionError caught; retries once with timestamp-suffixed filename | `export_tracker.py` `export_tracker_to_excel` |
| mark_application unknown posting | Raises PostingNotFoundError (specific, not generic) | `export/export_tracker.py` |
| mark_application future date | Raises FutureDateError | `export/export_tracker.py` |
| Pipeline interrupted mid-run | Idempotent: raw tables are append-only; staging is CREATE OR REPLACE; facts are upserts | Entire design |
| Concurrent pipeline runs | File-based lock with PID; second run logs ALREADY_RUNNING and exits | `run_pipeline.py` `_acquire_lock` |
| Stale lock from killed process | PID checked via `os.kill(pid, 0)`; if dead, lock is removed and pipeline proceeds | `run_pipeline.py` `_acquire_lock` |
| Databricks parameter limit (1 MB) | Size-aware chunking in `insert_rows` reduces batch size when parameter bytes exceed 900 KB | `dbio/databricks.py` |
| Multi-statement SQL files | `run_sql_script` splits on semicolons and runs each statement separately | `dbio/databricks.py` |
| Lever epoch-millisecond dates | `FROM_UNIXTIME(CAST(createdAt AS BIGINT) / 1000)` converts to date | `staging/01_normalize_postings.sql` |
| Greenhouse timezone-offset dates | `TO_DATE(SUBSTR(first_published, 1, 10))` extracts date portion | `staging/01_normalize_postings.sql` |

---

## 11. Errors Encountered and How They Were Solved

This section is interview gold. Every error below was encountered during the
actual build and solved.

### Error 1: BigQuery Sandbox Cannot Run DML

**Symptom:** `INSERT`, `MERGE`, and `DELETE` statements failed with a billing
error on BigQuery Sandbox.

**Root Cause:** Google requires billing-enabled BigQuery for DML. Sandbox is
read-only for DML.

**Solution:** Switched the entire backend to Databricks Free Edition, which
provides full DML support at no cost.

---

### Error 2: hive_metastore Disabled in Databricks

**Symptom:** `UC_HIVE_METASTORE_DISABLED_EXCEPTION` — "The operation attempted
to use Hive Metastore, which is disabled."

**Root Cause:** The Databricks Free Edition workspace runs Unity Catalog only.
The default `hive_metastore` catalog is permanently disabled.

**Solution:** Ran `SHOW CATALOGS` to discover available catalogs
(`samples`, `system`, `workspace`). Set `DATABRICKS_CATALOG=workspace` in
`.env` and in `dbio/databricks.py`.

---

### Error 3: dotenv Not Finding .env

**Symptom:** `load_dotenv()` returned `False` and `DATABRICKS_HOST` was `None`
when running probe scripts from outside the project directory.

**Root Cause:** `python-dotenv`'s `find_dotenv()` searches from the caller's
`__file__` location, not from `os.getcwd()`. Scripts in a temp directory
never found the project `.env`.

**Solution:** Changed `dbio` to load `.env` from an absolute path:
`load_dotenv(PROJECT_ROOT / ".env")` where `PROJECT_ROOT` is computed from
the package's `__file__`.

---

### Error 4: Telemetry DNS Failure

**Symptom:** `HTTP request failed after retries: ... host='unknown-host' ...
Failed to resolve 'unknown-host'`.

**Root Cause:** The `databricks-sql-connector` sends telemetry to a placeholder
host that could not be resolved.

**Solution:** Passed `enable_telemetry=False` to `sql.connect()` in
`dbio/databricks.py`.

---

### Error 5: Multi-Statement SQL Failed

**Symptom:** `PARSE_SYNTAX_ERROR: Syntax error at or near 'CREATE': extra input
'CREATE'.` when running `load_dimensions.sql`.

**Root Cause:** The connector's `cursor.execute()` runs exactly one statement.
Multi-statement files (4 statements in `load_dimensions.sql`) were sent as one
string and the parser rejected the second statement.

**Solution:** Added `split_statements()` and `run_sql_script()` to `dbio`.
The function splits on semicolons (dropping comment lines) and runs each
statement separately.

---

### Error 6: executemany Extremely Slow

**Symptom:** Inserting 50 Adzuna rows took 2.5 minutes; 892 Greenhouse rows
would have taken ~45 minutes.

**Root Cause:** `cursor.executemany()` on Free Edition executes one
`cursor.execute()` per row, each with ~3 seconds of network round-trip overhead.

**Solution:** Replaced `executemany` with multi-row `VALUES` inserts:
`INSERT INTO t (a,b,c) VALUES (?,?,?),(?,?,?),...`. 50 rows in one round trip
instead of 50.

---

### Error 7: Databricks Parameter Limit (1 MB)

**Symptom:** `BAD_REQUEST: Parameterized query's parameters are too large: the
combined size of parameters is 1267438, exceeding the limit of 1048576
characters.`

**Root Cause:** Lever postings have large description text (~25 KB each).
200 rows × 3 columns exceeded the 1 MB combined parameter limit.

**Solution:** Added size-aware chunking to `insert_rows`: the function
accumulates rows until the estimated parameter size approaches 900 KB, then
flushes. This handles both small and large payloads correctly.

---

### Error 8: Stale Lock from Interrupted Process

**Symptom:** After a timeout killed a pipeline run, the `.pipeline.lock` file
remained and blocked all future runs with `ALREADY_RUNNING`.

**Root Cause:** The `finally` block that deletes the lock never executed because
the process was forcibly killed.

**Solution:** Added stale-lock detection: `_acquire_lock` reads the PID from the
lock file and checks if the process is still alive via `os.kill(pid, 0)`. If the
process is dead, the lock is removed and the pipeline proceeds.

---

### Error 9: Rippling API Endpoint Wrong

**Symptom:** All Rippling board slugs returned 404 at
`app.rippling.com/api/boards/{slug}/jobs`.

**Root Cause:** The assumed endpoint was outdated. Rippling's public job boards
use a different API path.

**Solution:** Inspected the HTML of `ats.rippling.com/gather/jobs` to find the
embedded API: `ats.rippling.com/api/v2/board/{slug}/jobs`. Updated the
extractor URL, added pagination support, and updated the normalization branch
to use the correct fields (`uuid`, `name`, `workLocations`, `createdOn`,
`description.role`).

---

### Error 10: Lever `createdAt` Is Epoch Milliseconds, Not ISO

**Symptom:** Lever postings had `date_posted = NULL` in staging, triggering
`is_incomplete = TRUE` for all 697 rows.

**Root Cause:** The original normalization used `TO_DATE(SUBSTR(createdAt, 1, 10))`
assuming ISO strings. Lever returns epoch milliseconds (e.g., `1553186035299`).
`SUBSTR("1553186035299", 1, 10)` = `"1553186035"` which is not a valid date.

**Solution:** Changed to
`TO_DATE(FROM_UNIXTIME(CAST(createdAt AS BIGINT) / 1000))` which converts
milliseconds to a timestamp and then to a date.

---

### Error 11: `python -m` Required Instead of `python script.py`

**Symptom:** `ModuleNotFoundError: No module named 'dbio'` when running
`python orchestration/run_pipeline.py`.

**Root Cause:** Running a script by path adds only the script's directory to
`sys.path`, not the project root. `dbio` lives at the project root.

**Solution:** All commands use `uv run python -m orchestration.run_pipeline`
(module mode), which adds the current directory (project root) to `sys.path`.

---

### Error 12: Power BI Closed Without Saving

**Symptom:** Power BI Desktop was installed and launched, data was loaded, but
the application closed before a `.pbix` could be saved. The window title went
blank and the process consumed CPU without responding.

**Root Cause:** The browser-based authentication flow and the large data import
on a resource-constrained Free Edition warehouse caused the application to
become unresponsive.

**Solution:** Generated reproducible dashboard preview PNGs directly from the
live marts using `dashboard/generate_screenshot.py` (matplotlib, dev-only
dependency). The native `.pbix` remains a manual desktop step documented in
the dashboard specification.

---

## 12. Testing Strategy and Coverage

### Philosophy

Tests prioritize in this order (from AGENTS.md):
1. Idempotency — safe to re-run any stage
2. Empty/zero-result behavior
3. Date/type parsing across sources
4. Clear error messages on user-facing functions
5. Retry/rate-limit logic (lower priority)

### Test Files and What They Cover

| Test File | Tests | What Is Verified |
|---|---|---|
| `test_adzuna_extractor.py` | 6+ | Country allowlist rejection, missing credentials, 429 retry with Retry-After, empty results, successful fetch |
| `test_greenhouse_extractor.py` | 2+ | Empty token raises error, empty board returns empty list |
| `test_lever_extractor.py` | 2+ | Empty slug raises error, successful fetch |
| `test_rippling_extractor.py` | 6+ | Empty board, list+detail, concurrency limit (5), single-failure isolation, pagination, missing slug |
| `test_http_utils.py` | 3+ | Retry on 429, parse-error handling |
| `test_bigquery_io.py` | 2 | Empty payload returns 0, unknown source raises ValueError |
| `test_databricks.py` | 3 | Comment stripping, single statement, multi-statement batch |
| `test_data_quality_checks.py` | 3 | All rules pass, failed rule counted, zero postings = WARN |
| `test_staging_sql.py` | 3 | All 4 source branches present, dedup key, source-specific parsing (first_published, epoch, FROM_UNIXTIME) |
| `test_loaders.py` | 3 | Dimensions SQL content, facts SQL content, SCD2 SQL content, marts execution |
| `test_export_tracker.py` | 6 | Zero rows → headers, missing closing date → "Not specified", locked file retry, future date error, unknown posting error, valid upsert |
| `test_run_pipeline.py` | 7+ | Lock rejection, cleanup rejection, watermark default, watermark return, logging, successful run, all-sources-failed skip, ALREADY_RUNNING |
| **Total** | **58** | |

### How Tests Mock the Database

All DB-facing tests patch `dbio.*` at the consumer site:
`@patch("warehouse.loaders.run_sql_script")`,
`@patch("export.export_tracker.query_rows")`, etc. This means tests never
connect to Databricks and run in under 2 seconds.

---

## 13. How to Set Up and Run

### Prerequisites

- Python 3.12+
- uv installed (`pip install uv` or `winget install astral-sh.uv`)
- A Databricks Free Edition workspace with a running SQL warehouse
- Adzuna API credentials (free at developer.adzuna.com)

### Setup Steps

1. Clone the repository.
2. Copy `.env.example` to `.env` and fill in:
   ```
   DATABRICKS_HOST=your-workspace.cloud.databricks.com
   DATABRICKS_HTTP_PATH=/sql/1.0/warehouses/your-warehouse-id
   DATABRICKS_TOKEN=your-personal-access-token
   DATABRICKS_CATALOG=workspace
   DATABRICKS_SCHEMA=default
   ADZUNA_APP_ID=your-app-id
   ADZUNA_APP_KEY=your-app-key
   ADZUNA_QUERY=data engineer
   ADZUNA_COUNTRY=in
   ADZUNA_PAGES=1
   ```
3. Edit `config/companies.yaml` to add or remove public boards.
4. Install dependencies:
   ```
   uv sync
   ```

### Run Commands

```text
# Apply the warehouse schema (rerunnable)
uv run python -m orchestration.apply_schema

# Run the full pipeline (extract → raw → stage → DQ → load → marts)
uv run python -m orchestration.run_pipeline

# Export the Excel tracker
uv run python -c "from export.export_tracker import export_tracker_to_excel; export_tracker_to_excel('exports/application_tracker.xlsx')"

# Generate dashboard preview PNGs
uv run python dashboard/generate_screenshots.py

# Run all tests
uv run pytest

# Clean up raw tables older than 30 days
uv run python -c "from orchestration.run_pipeline import cleanup_raw_tables; print(cleanup_raw_tables(30))"
```

---

## 14. How to See and Use the Jobs

### In Databricks SQL Editor

```sql
-- See all current postings
SELECT
  posting_id, company_name, job_title, location,
  date_posted, closing_date, is_likely_closed, date_applied
FROM workspace.default.mart_application_tracker
ORDER BY date_posted DESC;

-- Search for a role
SELECT * FROM workspace.default.mart_application_tracker
WHERE lower(job_title) LIKE '%data engineer%'
ORDER BY date_posted DESC;

-- See skill demand
SELECT skill_name, postings_mentioning_skill
FROM workspace.default.mart_skill_demand_trend
ORDER BY postings_mentioning_skill DESC;

-- See company activity
SELECT company_name, total_postings, active_postings, likely_closed_postings
FROM workspace.default.mart_company_activity
ORDER BY total_postings DESC;

-- Check the latest run status
SELECT run_id, source, status, rows_written
FROM workspace.default.pipeline_run_log
ORDER BY ended_at DESC LIMIT 10;

-- Check data quality
SELECT rule_name, status, rows_affected
FROM workspace.default.data_quality_log
ORDER BY checked_at DESC;
```

### In Excel

```text
uv run python -c "from export.export_tracker import export_tracker_to_excel; export_tracker_to_excel('exports/application_tracker.xlsx')"
```

Open `exports/application_tracker.xlsx`. It has one sheet, headers, and
one row per posting. Missing closing dates show "Not specified". Blank
application dates mean "not yet applied".

### In Python (from another project)

```python
import os
from databricks import sql
from dotenv import load_dotenv

load_dotenv()
conn = sql.connect(
    server_hostname=os.environ["DATABRICKS_HOST"],
    http_path=os.environ["DATABRICKS_HTTP_PATH"],
    access_token=os.environ["DATABRICKS_TOKEN"],
    catalog="workspace",
    schema="default",
    enable_telemetry=False,
)
cursor = conn.cursor()
cursor.execute("SELECT * FROM mart_application_tracker ORDER BY date_posted DESC")
jobs = [row.asDict() for row in cursor.fetchall()]
conn.close()
```

### Mark a Posting as Applied

```python
from datetime import date
from export.export_tracker import mark_application

mark_application("adzuna-5812528535", date(2026, 8, 13))
```

### In Power BI or Tableau

Connect to Databricks with host, HTTP path, and token. Import only the four
`mart_*` views. See `dashboard/dashboard-spec.md` for visual field mappings.

---

## 15. How to Extend the Project

### Add a New Company

Add to `config/companies.yaml`:

```yaml
companies:
  - display_name: New Company
    greenhouse_board_token: new-token
```

Run the pipeline. The new company appears in staging, warehouse, and marts.

### Add a New Source

1. Create `ingestion/newsource_extractor.py` with `fetch_newsource_jobs(...) -> list[dict]`.
2. Add `raw_newsource` table to `warehouse/schema.sql`.
3. Add a UNION ALL branch to `staging/01_normalize_postings.sql`.
4. Add the source to the seed in `schema.sql` (`dim_source`).
5. Add the source name to `SOURCES` in `orchestration/run_pipeline.py`.
6. Add the fetch logic to `_fetch_source()` in `run_pipeline.py`.
7. Write tests in `tests/ingestion/test_newsource_extractor.py`.
8. Run the full pipeline and verify DQ, facts, marts.

### Add a New Mart

1. Create `marts/mart_new_view.sql` with `CREATE OR REPLACE VIEW ...`.
2. `refresh_mart_views()` will automatically pick it up (it globs `*.sql`).
3. No code change needed in `refresh.py`.

### Add a New Data-Quality Rule

Add a rule to the `RULES` list in `staging/data_quality_checks.py`:

```python
{
    "rule_name": "my_new_rule",
    "sql": "SELECT COUNT(*) AS n FROM staging_postings WHERE ...",
    "expected": 0,
}
```

It will automatically run on every pipeline execution and log to
`data_quality_log`.

---

## 16. Interview Talking Points

### "Tell me about your data engineering project."

> I built a multi-source job-market data warehouse on Databricks Delta Lake.
> It ingests postings from four REST APIs — Adzuna, Greenhouse, Lever, and
> Rippling — stores raw JSON in Delta bronze tables, normalizes differing
> field names and date formats into a common staging shape, deduplicates
> across sources on a normalized company-title-location key, loads a star
> schema with SCD Type 2 company versioning, and publishes four analytics
> marts consumed by Excel, Power BI, and external Python projects.

### "How do you handle source failures?"

> Each source is wrapped in a try/except inside the pipeline loop. If one
> source fails, it is logged as FAILED and the pipeline continues with the
> remaining sources. The overall run is PARTIAL if at least one succeeded,
> and FAILED only if all sources failed. Zero results is a valid SUCCESS
> outcome, not an error.

### "How do you ensure idempotency?"

> Raw tables are append-only — re-running just adds more rows with a new
> run_id. Staging tables use CREATE OR REPLACE — rebuilt on every run. Facts
> use MERGE with a null-safe match on (posting_id, date_posted) — re-seen
> postings update last_seen_at without creating duplicates. Dimensions use
> MERGE (insert-only) or CTAS. Marts use CREATE OR REPLACE VIEW.

### "What was the hardest technical problem?"

> The Databricks Free Edition had high per-statement latency (~3 seconds per
> round trip) and a 1 MB parameterized query limit. Row-by-row executemany
> inserts would have taken 45 minutes for a single run. I built size-aware
> multi-row batch inserts that chunk payloads under 900 KB per parameter set,
> reducing insert time from minutes to seconds while respecting the platform
> limit.

### "How do you handle different date formats?"

> Adzuna uses ISO 8601 strings, Greenhouse uses ISO with timezone offsets,
> Lever uses epoch milliseconds, and Rippling uses ISO with microseconds.
> Each source has its own normalization branch in staging SQL:
> - Adzuna/Greenhouse/Rippling: `TO_DATE(SUBSTR(field, 1, 10))`
> - Lever: `TO_DATE(FROM_UNIXTIME(CAST(createdAt AS BIGINT) / 1000))`

### "What is SCD Type 2 and how did you implement it?"

> SCD Type 2 tracks historical changes to dimension attributes. When a
> company's display name changes, the old version is closed (valid_to set,
> is_current = false) and a new current version is opened. Unchanged
> attributes do not trigger a new version. I implemented it as a two-step
> SQL script: UPDATE to close changed versions, INSERT to open new ones,
> with a null-safe comparison.

### "How do you test?"

> 58 tests covering extractors, HTTP retry, empty results, date parsing,
> idempotency, data quality, exports, locking, and Rippling pagination.
> DB-facing tests mock `dbio` at the consumer site so they run in under
> 2 seconds without connecting to Databricks. Tests are named
> `test_<condition>_<expected_behavior>()` for readability.

### "What would you improve next?"

> I would add a scheduler for automated runs, a dbt project for more
> structured SQL testing, a proper NLP-based skill extractor instead of
> regex, and a Streamlit or Flask dashboard for interactive exploration.
> I would also add integration tests that run against a live Databricks
> warehouse in CI/CD.

---

*This document is the complete end-to-end reference for the Job Market Pulse
project. It was generated from the live codebase and verified against the
actual Databricks warehouse state on 2026-08-13.*