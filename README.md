# Job Market Pulse

Job Market Pulse is a manually run, multi-source job-market data warehouse.
It ingests public job postings, stores the raw JSON in Databricks Delta Lake,
normalizes and deduplicates the records, loads a star schema, publishes four
analytics marts, and produces an Excel application tracker.

The project is designed as a portfolio-quality data engineering system rather
than a disposable scraper. The important properties are rerunnable stages,
clear source isolation, idempotent warehouse loads, data-quality logging, and
outputs that other tools can consume without reading raw tables.

## What It Does

The pipeline follows this sequence:

```text
Adzuna / Greenhouse / Lever / Rippling
        |
        v
raw_* Delta tables          append-only JSON bronze layer
        |
        v
staging_postings_normalized source-specific parsing and cleansing
        |
        v
staging_postings            cross-source deduplication
        |
        v
dim_* + fact_*              star-schema warehouse and SCD2 companies
        |
        v
mart_* views                dashboard and export contract
        |
        +--> Excel tracker
        +--> Power BI / Tableau
        +--> Other Python or SQL projects
```

The current live verification loaded 50 Adzuna, 892 Greenhouse, 697 Lever,
and 1 Rippling/Gather payloads. The warehouse contained 1,602 deduplicated
postings at that verification point. Counts change when the APIs change or a
new pipeline run is performed.

## Backend

The backend is Databricks Free Edition using Unity Catalog and Delta Lake:

```text
catalog: workspace
schema:  default
```

The legacy `hive_metastore` catalog is disabled in this workspace. Python
access is centralized in `dbio/`, which wraps `databricks-sql-connector`.
Never commit `.env`; use `.env.example` as the configuration template.

Required local variables:

```text
DATABRICKS_HOST
DATABRICKS_HTTP_PATH
DATABRICKS_TOKEN
DATABRICKS_CATALOG=workspace
DATABRICKS_SCHEMA=default
ADZUNA_APP_ID
ADZUNA_APP_KEY
ADZUNA_QUERY
ADZUNA_COUNTRY
ADZUNA_PAGES
```

Public board identifiers are stored in `config/companies.yaml`. Secrets and
tokens stay in `.env`.

## Quick Start

Install the environment:

```text
uv sync
```

Apply the schema once, or rerun it safely:

```text
uv run python -m orchestration.apply_schema
```

Run the complete pipeline:

```text
uv run python -m orchestration.run_pipeline
```

The pipeline obtains a file lock, fetches each source independently, logs
source results, runs staging and data-quality checks, loads dimensions and
facts, refreshes marts, logs the overall result, and releases the lock.

Generate the Excel tracker:

```text
uv run python -c "from export.export_tracker import export_tracker_to_excel; export_tracker_to_excel('exports/application_tracker.xlsx')"
```

Generate the verified dashboard preview images:

```text
uv run python dashboard/generate_screenshots.py
```

Run all tests:

```text
uv run pytest
```

The current suite contains 58 tests covering extractors, retries, parsing,
empty results, idempotency-oriented behavior, data quality, exports, locking,
SCD2 SQL execution, and Rippling pagination.

## Repository Guide

Read `PROJECT.md` for the technical project guide and `docs/outputs-guide.md`
for the complete output catalogue and external-consumer examples.

| Path | Purpose |
|---|---|
| `ingestion/` | REST API clients and raw payload writing |
| `dbio/` | Databricks connection, SQL execution, queries, and batch inserts |
| `staging/` | Four-source normalization, deduplication, and DQ checks |
| `warehouse/` | Delta schema, dimensions, facts, loaders, and SCD2 company logic |
| `marts/` | Four dashboard/export views |
| `orchestration/` | Schema application, pipeline entrypoint, and retention cleanup |
| `export/` | Excel tracker and application updates |
| `exports/` | Generated Excel output; runtime files are ignored except the sample |
| `dashboard/` | Dashboard specification and reproducible preview generator |
| `docs/` | Architecture, setup, integrations, outputs, changelog, screenshots |
| `tests/` | Automated behavior and regression coverage |
| `config/` | Public company and board configuration |

## Source Details

### Adzuna

Adzuna is paginated by query, country, and page. The country is validated
against an allowlist before the request. Its records are normalized from
`company.display_name`, `location.display_name`, `title`, `created`, and
`description`.

### Greenhouse

Greenhouse boards are configured with public board identifiers. The pipeline
uses `company_name`, `first_published`, `application_deadline`,
`location.name`, and `content` from the board response. The current verified
boards are Figma, Stripe, and Coinbase.

### Lever

Lever is called with `mode=json`. The API returns epoch-millisecond values for
`createdAt` and `closedAt`, which are converted to warehouse dates. The
current verified boards are `leverdemo` and `palantir`.

### Rippling

Rippling uses the public v2 board API. The list call is paginated and each job
is followed by a detail call with a maximum of five concurrent detail calls.
The verified board is Gather:

```text
https://ats.rippling.com/api/v2/board/gather/jobs
```

The normalized fields are `uuid`, `name`, `workLocations`, `createdOn`,
`description`, and `companyName`.

## Data Rules

- Raw tables append one JSON text payload per source row.
- Staging normalizes source-specific fields into one common shape.
- Cross-source deduplication uses normalized company, title, and location.
- The earliest `first_seen_at` is retained and `last_seen_at` advances on re-seen records.
- Facts are upserted on `(posting_id, date_posted)` and disappeared jobs are not deleted.
- Missing closing dates remain NULL in the warehouse and become `Not specified` in Excel.
- `is_likely_closed` is computed in marts when `last_seen_at` is older than three days.
- SCD2 company versions are created only when the tracked display attribute changes.
- A source failure is isolated; zero rows are valid; all-source failure skips downstream stages.

## Connecting Another Project

Use the marts rather than the raw or staging tables. The simplest SQL query is:

```sql
SELECT
  posting_id,
  company_name,
  job_title,
  location,
  date_posted,
  closing_date,
  date_applied,
  is_likely_closed,
  last_seen_at
FROM workspace.default.mart_application_tracker
ORDER BY date_posted DESC;
```

From Python, use the Databricks SQL connector with the same host, HTTP path,
token, catalog, and schema values used by this project. See the complete
example in `docs/outputs-guide.md`.

Power BI and Tableau should connect to `workspace.default` and import only:

```text
mart_skill_demand_trend
mart_hiring_velocity
mart_company_activity
mart_application_tracker
```

## Known Limitations

- The pipeline is manually run; no scheduler is included.
- Power BI/Tableau native report files must be saved from the desktop tool.
- The repository contains verified PNG previews, not a native `.pbix` file.
- Exact-title collisions across companies remain a known deduplication risk.
- Raw data is append-only until the configured retention cleanup is run.
- External projects must not write directly to fact or dimension tables.

## GitHub

Repository:

```text
https://github.com/manva-niso/DataWarehouse.
```

The repository intentionally excludes `.env`, virtual environments, caches,
agent/LLM tooling, and other runtime clutter.
