-- Job Market Pulse mart: application tracker.
-- Source of truth for the Excel export and personal tracking.
-- Live postings + archived postings for tracked applications survive indefinitely.
-- Databricks SQL / Delta.

CREATE OR REPLACE VIEW mart_application_tracker AS
WITH combined_postings AS (
  SELECT
    posting_id,
    company_id,
    location_id,
    job_title,
    role_family,
    date_posted,
    closing_date,
    last_seen_at,
    FALSE AS is_archived
  FROM fact_job_posting

  UNION ALL

  SELECT
    arc.posting_id,
    arc.company_id,
    arc.location_id,
    arc.job_title,
    arc.role_family,
    arc.date_posted,
    arc.closing_date,
    arc.last_seen_at,
    TRUE AS is_archived
  FROM fact_job_posting_archive arc
)
SELECT
  f.posting_id,
  c.company_name,
  f.job_title,
  l.location_normalized AS location,
  f.date_posted,
  f.closing_date,
  f.last_seen_at,
  (f.is_archived OR (f.closing_date IS NOT NULL AND f.closing_date < CURRENT_DATE()) OR f.last_seen_at < CURRENT_TIMESTAMP() - INTERVAL 7 DAY) AS is_likely_closed,
  a.date_applied,
  f.role_family,
  COALESCE(a.status, 'NOT_APPLIED') AS status
FROM combined_postings f
JOIN dim_company c
  ON c.company_id = f.company_id
  AND c.is_current = TRUE
LEFT JOIN dim_location l
  ON l.location_id = f.location_id
LEFT JOIN applications a
  ON a.posting_id = f.posting_id;
