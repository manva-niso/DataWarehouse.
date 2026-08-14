# Job Market Pulse Project Guide

## Purpose

Job Market Pulse is a multi-source job-posting warehouse for discovering,
filtering, tracking, and analyzing job opportunities. It is also a complete
data engineering portfolio project showing REST ingestion, JSON handling,
Delta Lake modeling, SQL transformations, idempotent loads, data quality,
orchestration, analytics marts, and downstream consumption.

## System Boundary

The system begins at four public job APIs and ends at reusable mart views and
an Excel tracker. It does not include a web frontend or an always-on scheduler.

```text
REST APIs
  -> ingestion extractors
  -> raw_* Delta tables
  -> staging SQL
  -> star-schema warehouse
  -> mart views
  -> Excel / Power BI / Tableau / external SQL or Python consumers
```

## Technology

- Python 3.12+
- `uv` for dependency and environment management
- Databricks Free Edition
- Unity Catalog: `workspace.default`
- Delta Lake tables
- Databricks SQL Connector for Python
- Spark SQL / Databricks SQL
- Requests for REST APIs
- OpenPyXL for Excel output
- Pytest for automated tests
- Matplotlib for reproducible dashboard preview PNGs only

## Folder Responsibilities

### `ingestion/`

Each extractor returns a list of Python dictionaries. The functions are
source-isolated so a failure in one source does not prevent the other sources
from running.

`bigquery_io.py` retains the historical public function name
`write_to_bigquery_raw` for contract compatibility, but it writes to
Databricks through `dbio`.

### `dbio/`

This is the only Python database access layer. It provides:

- `run_sql`: execute one SQL statement
- `run_sql_script`: split and execute multi-statement SQL files
- `query_rows`: return query results as dictionaries
- `insert_rows`: size-aware multi-row inserts under Databricks parameter limits

The connector opens a connection per operation. Multi-row inserts are used
because Free Edition has high per-statement latency and parameterized queries
have an approximately 1 MB combined parameter limit.

### `staging/`

`01_normalize_postings.sql` has one UNION ALL branch for each source. It
converts differing JSON fields and date formats into the common posting shape.

`02_deduplicate.sql` groups repeated pulls and applies the cross-source key:

```text
lower(company_name) + title + normalized_location
```

### `warehouse/`

`schema.sql` creates all Delta tables. `load_dimensions.sql` builds the date,
location, skill, and company dimensions. `scd2_company.sql` closes old company
versions and opens a new current version only when the tracked display
attribute changes. `load_facts.sql` upserts job facts and rebuilds skill
mentions.

### `marts/`

Marts are the presentation contract. They contain the business-friendly
columns used by Excel, Power BI, and Tableau. Consumers should not reproduce
warehouse joins themselves unless they have a specific analytical reason.

### `orchestration/`

`apply_schema.py` applies the DDL one statement at a time. `run_pipeline.py`
coordinates source extraction, raw writes, staging, DQ, warehouse loads,
marts, logging, and lock handling. `cleanup_raw_tables.sql` supports positive
retention windows.

## Table Catalogue

### Raw tables

| Table | Contents |
|---|---|
| `raw_adzuna` | Adzuna JSON text, run ID, ingestion timestamp |
| `raw_greenhouse` | Greenhouse JSON text, run ID, ingestion timestamp |
| `raw_lever` | Lever JSON text, run ID, ingestion timestamp |
| `raw_rippling` | Rippling detail JSON text, run ID, ingestion timestamp |

### Dimensions

| Table | Key purpose |
|---|---|
| `dim_company` | SCD Type 2 company identity and display history |
| `dim_location` | Raw and normalized location values |
| `dim_skill` | Seed skill dictionary |
| `dim_date` | Calendar attributes for posted dates |
| `dim_source` | Fixed source vocabulary |

### Facts and tracking

| Table | Contents |
|---|---|
| `fact_job_posting` | Current deduplicated job postings |
| `fact_posting_skill_mention` | Posting-to-skill many-to-many rows |
| `applications` | User-maintained application dates |

### Logs

| Table | Contents |
|---|---|
| `pipeline_run_log` | Per-source and overall run status/counts |
| `data_quality_log` | DQ rule results and affected-row counts |

## Operating Sequence

1. Copy `.env.example` to `.env` and add local credentials.
2. Add or update public boards in `config/companies.yaml`.
3. Apply or reapply the schema:
   `uv run python -m orchestration.apply_schema`
4. Run the pipeline:
   `uv run python -m orchestration.run_pipeline`
5. Inspect source counts and DQ logs in Databricks.
6. Export the tracker or refresh the BI tool.
7. Run retention cleanup when appropriate:
   `cleanup_raw_tables(retention_days=30)`.

## How to Inspect Jobs

The normal job view is:

```sql
SELECT *
FROM workspace.default.mart_application_tracker
ORDER BY date_posted DESC;
```

Use `fact_job_posting` when you need warehouse keys and source IDs. Use
`raw_*` only when investigating source payloads or parsing behavior.

## How to Extend the Project

To add a new company, add its public board identifier to
`config/companies.yaml`, then run the pipeline. To add a new source:

1. Implement and test the extractor in `ingestion/`.
2. Add its raw table to `warehouse/schema.sql`.
3. Add its normalization branch to `staging/01_normalize_postings.sql`.
4. Add its source ID to the source dimension seed.
5. Add configuration and source-level tests.
6. Run the full pipeline and verify DQ, facts, marts, and export behavior.

Do not insert manually into gold facts to add jobs. The raw-to-staging-to-gold
path is the source of truth.

## External Consumers

External projects should read `workspace.default.mart_*` views. They can use:

- Databricks SQL editor
- Databricks SQL Connector for Python
- JDBC or ODBC
- Power BI Databricks connector
- Tableau Databricks connector
- The generated Excel workbook

Examples and output-specific guidance are in `docs/outputs-guide.md`.

## Verification Status

The latest verified state includes four configured sources, 1,602 staged/fact
postings, four populated marts, SCD2 company loading, retention cleanup, an
Excel export, four PNG dashboard previews, and 58 passing tests.
