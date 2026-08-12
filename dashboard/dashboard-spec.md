# Dashboard Specification

Use Power BI Desktop or Tableau Free Edition. Connect only to the four views in
the `workspace.default` Databricks schema. Do not connect the dashboard to raw,
staging, or warehouse tables.

## Connection

- Connector: Databricks
- Server hostname: value of `DATABRICKS_HOST`
- HTTP path: value of `DATABRICKS_HTTP_PATH`
- Catalog: `workspace`
- Schema: `default`
- Authentication: personal access token stored in the local credential store

## Page Layout

### 1. Skill Demand Trend

- Source: `mart_skill_demand_trend`
- Chart: line chart
- X-axis: `year` + `month` as a Year-Month hierarchy
- Legend: `skill_name`
- Values: `postings_mentioning_skill`
- Filter: top 10 skills by total postings

### 2. Hiring Velocity

- Source: `mart_hiring_velocity`
- Chart: clustered bar chart
- Axis: `company_name`
- Values: `postings_posted`
- Slicers: `year`, `month`
- Sort: descending by `postings_posted`

### 3. Company Activity

- Source: `mart_company_activity`
- Chart: stacked bar chart
- Axis: `company_name`
- Values: `active_postings`, `likely_closed_postings`
- Tooltip: `total_postings`, `earliest_first_seen`, `latest_last_seen`
- Sort: descending by `total_postings`

### 4. Application Tracker

- Source: `mart_application_tracker`
- Visual: table
- Columns: `posting_id`, `company_name`, `job_title`, `location`,
  `date_posted`, `closing_date`, `date_applied`, `is_likely_closed`,
  `last_seen_at`
- Conditional formatting: highlight `is_likely_closed = true` in amber and
  missing `date_applied` in light blue
- Preserve the Excel convention: a null `closing_date` displays as
  `Not specified` in the export

## Report Filters

- Company
- Year
- Month
- Likely closed
- Application status, derived from whether `date_applied` is blank

## Acceptance Checks

- All four visuals load from mart views only.
- Refresh does not require access to raw or staging tables.
- The tracker contains the same posting population as the Excel export.
- A zero-row mart still renders headers/axes without an error.
- Dashboard screenshots are exported to `docs/screenshots/` after the desktop
  artifact is created.
