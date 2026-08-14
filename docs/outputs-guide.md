# Outputs and External Consumption Guide

This guide explains where the jobs are stored, which output to use for each
purpose, and how another project can connect to the warehouse.

## Where the Jobs Are

The recommended source is:

```text
workspace.default.mart_application_tracker
```

It contains one row per current deduplicated posting and is safe for Excel,
Power BI, Tableau, or another application.

Useful columns:

| Column | Meaning |
|---|---|
| `posting_id` | Stable source-prefixed posting identifier |
| `company_name` | Current company name |
| `job_title` | Job title |
| `location` | Normalized location |
| `date_posted` | Source posting date when available |
| `closing_date` | Closing date, nullable |
| `last_seen_at` | Last successful ingestion timestamp |
| `is_likely_closed` | Downstream signal based on a three-day absence |
| `date_applied` | User-maintained application date, nullable |

## SQL Examples

### See the newest jobs

```sql
SELECT
  posting_id,
  company_name,
  job_title,
  location,
  date_posted,
  closing_date,
  is_likely_closed
FROM workspace.default.mart_application_tracker
ORDER BY date_posted DESC, company_name, job_title;
```

### Search for a skill or title

```sql
SELECT *
FROM workspace.default.mart_application_tracker
WHERE lower(job_title) LIKE '%data engineer%'
   OR lower(job_title) LIKE '%analytics%'
ORDER BY date_posted DESC;
```

### Filter by company or location

```sql
SELECT *
FROM workspace.default.mart_application_tracker
WHERE company_name = 'Figma'
   OR lower(location) LIKE '%remote%';
```

### See the source distribution

```sql
SELECT
  source_id,
  COUNT(*) AS postings
FROM workspace.default.fact_job_posting
GROUP BY source_id
ORDER BY postings DESC;
```

### See mentioned skills

```sql
SELECT
  s.skill_name,
  COUNT(DISTINCT m.posting_id) AS postings
FROM workspace.default.fact_posting_skill_mention AS m
JOIN workspace.default.dim_skill AS s
  ON s.skill_id = m.skill_id
GROUP BY s.skill_name
ORDER BY postings DESC;
```

### Inspect raw source JSON

```sql
SELECT
  run_id,
  ingested_at,
  payload
FROM workspace.default.raw_rippling
ORDER BY ingested_at DESC;
```

Use `get_json_object(payload, '$.field')` in Databricks SQL when investigating
a raw payload. Raw payloads are JSON text, not a structured JSON column.

## Python Consumer Example

Install the connector in the separate project:

```text
uv add databricks-sql-connector
```

Use environment variables rather than hardcoding credentials:

```python
import os

from databricks import sql
from dotenv import load_dotenv

load_dotenv()

connection = sql.connect(
    server_hostname=os.environ["DATABRICKS_HOST"],
    http_path=os.environ["DATABRICKS_HTTP_PATH"],
    access_token=os.environ["DATABRICKS_TOKEN"],
    catalog=os.getenv("DATABRICKS_CATALOG", "workspace"),
    schema=os.getenv("DATABRICKS_SCHEMA", "default"),
    enable_telemetry=False,
)

try:
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT posting_id, company_name, job_title, location, date_posted
        FROM mart_application_tracker
        WHERE lower(job_title) LIKE :pattern
        ORDER BY date_posted DESC
        LIMIT :limit
        """,
        {"pattern": "%data engineer%", "limit": 100},
    )
    jobs = [row.asDict() for row in cursor.fetchall()]
    print(jobs)
finally:
    connection.close()
```

If the external project does not use the same schema defaults, fully qualify
the view as `workspace.default.mart_application_tracker`.

## Excel Output

Generate the current tracker:

```text
uv run python -c "from export.export_tracker import export_tracker_to_excel; export_tracker_to_excel('exports/application_tracker.xlsx')"
```

The workbook contains the tracker view and renders a NULL closing date as
`Not specified`. A blank application date means the user has not marked the
posting as applied.

## Mark an Application

Applications are stored separately from job facts:

```python
from datetime import date

from export.export_tracker import mark_application

mark_application("adzuna-5812528535", date(2026, 8, 13))
```

The function validates that the posting exists and rejects future dates. The
next mart query and Excel export will show the application date.

## Analytics Marts

| View | Use it for |
|---|---|
| `mart_application_tracker` | Job search, application tracking, Excel |
| `mart_skill_demand_trend` | Skills by year/month |
| `mart_hiring_velocity` | Posting volume by company and month |
| `mart_company_activity` | Active versus likely closed postings |

These views are the stable consumption layer. Their SQL definitions are in
`marts/` and are refreshed with:

```text
uv run python -c "from marts.refresh import refresh_mart_views; refresh_mart_views()"
```

## Power BI and Tableau

Connect the Databricks connector to:

```text
Host:       DATABRICKS_HOST
HTTP path:  DATABRICKS_HTTP_PATH
Catalog:    workspace
Schema:     default
```

Import the four `mart_*` views only. The visual field mappings are in
`dashboard/dashboard-spec.md`. Verified PNG previews are under
`docs/screenshots/` and can be regenerated with:

```text
uv run python dashboard/generate_screenshots.py
```

## Reusing Jobs in Another Project

Recommended reuse patterns:

1. Read `mart_application_tracker` for a ready-to-use job search dataset.
2. Read `mart_skill_demand_trend` for skill analytics.
3. Read `mart_company_activity` for company activity scoring.
4. Read the fact/dimension tables only when you need warehouse-level joins.
5. Read raw tables only for parser debugging or building a new normalization rule.

Do not modify raw payloads or fact rows from an external project. If the other
project needs additional attributes, add a new mart or a separate downstream
table rather than changing the source-of-truth pipeline tables directly.

## Refresh and Data Freshness

The warehouse is manually refreshed. A full refresh is:

```text
uv run python -m orchestration.run_pipeline
```

After a refresh, query `pipeline_run_log`:

```sql
SELECT run_id, source, status, rows_written, started_at, ended_at
FROM workspace.default.pipeline_run_log
ORDER BY ended_at DESC;
```

Check DQ outcomes:

```sql
SELECT run_id, rule_name, status, rows_affected, checked_at
FROM workspace.default.data_quality_log
ORDER BY checked_at DESC;
```

## Security Rules

- Never commit `.env` or a Databricks personal access token.
- Do not place tokens in SQL files, notebooks, screenshots, or README files.
- Use a read-only Databricks credential for external consumers whenever possible.
- Keep write access limited to the ingestion/orchestration project.
