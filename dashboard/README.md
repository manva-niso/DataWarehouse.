# Dashboard

Power BI Desktop or Tableau Free Edition connects ONLY to the mart views,
never to raw or staging tables. `is_likely_closed` is already computed inside
the mart views.

The exact visual design, field mappings, filters, and acceptance checks are in
[`dashboard-spec.md`](dashboard-spec.md). Power BI is the recommended tool for
this project because it connects directly to the Databricks SQL warehouse.

## Preview Images

When Power BI/Tableau is unavailable, generate reproducible PNG previews from
the same mart views:

```text
uv run python dashboard/generate_screenshots.py
```

The output goes to `docs/screenshots/`. These previews are not a replacement
for a native `.pbix` or `.twbx` report; they provide verified visual evidence
until the report is saved from the desktop BI tool.

## Power BI Desktop

1. Get Data -> Databricks, sign in with the SQL warehouse HTTP path and personal access token (see `docs/setup-checklist.md`).
2. Import the mart views: `mart_skill_demand_trend`, `mart_application_tracker`, `mart_hiring_velocity`, and `mart_company_activity`.
3. Implement the four visuals in `dashboard-spec.md`.
4. Save the `.pbix` workbook under `dashboard/` and export visual screenshots to `docs/screenshots/`.

## Tableau Free Edition

1. Connect -> Databricks, sign in with the SQL warehouse HTTP path and personal access token.
2. Import the same mart views.
3. Implement the four visuals in `dashboard-spec.md`.
4. Save the `.twb`/`.twbx` workbook under `dashboard/` and export visual screenshots to `docs/screenshots/`.

Only one BI tool is required; the other is optional.
