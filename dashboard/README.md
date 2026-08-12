# Dashboard

Power BI Desktop or Tableau Free Edition connects ONLY to the mart views,
never to raw or staging tables. `is_likely_closed` is already computed inside
the mart views.

## Power BI Desktop

1. Get Data -> Databricks, sign in with the SQL warehouse HTTP path and personal access token (see `docs/setup-checklist.md`).
2. Import the mart views: `mart_skill_demand_trend`, `mart_application_tracker`, `mart_hiring_velocity`, `mart_company_activity`.
3. Build 3-4 visuals, for example:
   - Skill demand trend over months (line or column chart)
   - Application tracker table (posting, company, closing date, applied, likely closed)
   - Postings by company (bar chart)
   - Postings by location (bar or map)
4. Save the workbook under `dashboard/` and export visual screenshots to `docs/screenshots/`.

## Tableau Free Edition

1. Connect -> Databricks, sign in with the SQL warehouse HTTP path and personal access token.
2. Import the same mart views.
3. Build the same 3-4 visuals.
4. Save the workbook under `dashboard/` and export visual screenshots to `docs/screenshots/`.

Only one BI tool is required; the other is optional.
