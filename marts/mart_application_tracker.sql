-- Job Market Pulse mart: application tracker.
-- Source of truth for the Excel export. is_likely_closed is computed here as
-- last_seen_at < now - 3 days; postings that disappear are never deleted.
-- Databricks SQL / Delta.

CREATE OR REPLACE VIEW mart_application_tracker AS
SELECT
  f.posting_id,
  c.company_name,
  f.job_title,
  l.location_normalized AS location,
  f.date_posted,
  f.closing_date,
  f.last_seen_at,
  f.last_seen_at < CURRENT_TIMESTAMP() - INTERVAL 3 DAY AS is_likely_closed,
  a.date_applied
FROM fact_job_posting f
JOIN dim_company c
  ON c.company_id = f.company_id
  AND c.is_current = TRUE
LEFT JOIN dim_location l
  ON l.location_id = f.location_id
LEFT JOIN applications a
  ON a.posting_id = f.posting_id;
