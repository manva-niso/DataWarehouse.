-- Job Market Pulse mart: posting longevity and duration active.
-- Distribution of days postings remain live before expiring or disappearing.
-- Reads live and archived postings.
-- Databricks SQL / Delta.

CREATE OR REPLACE VIEW mart_posting_longevity AS
WITH all_postings AS (
  SELECT
    posting_id,
    company_id,
    source_id,
    role_family,
    first_seen_at,
    last_seen_at,
    FALSE AS is_archived
  FROM fact_job_posting

  UNION ALL

  SELECT
    posting_id,
    company_id,
    source_id,
    role_family,
    first_seen_at,
    last_seen_at,
    TRUE AS is_archived
  FROM fact_job_posting_archive
),
longevity_calc AS (
  SELECT
    p.posting_id,
    c.company_name,
    p.source_id,
    p.role_family,
    p.is_archived,
    DATEDIFF(CAST(p.last_seen_at AS DATE), CAST(p.first_seen_at AS DATE)) AS active_days
  FROM all_postings p
  JOIN dim_company c
    ON c.company_id = p.company_id
    AND c.is_current = TRUE
)
SELECT
  role_family,
  source_id,
  CASE
    WHEN active_days <= 3 THEN '0-3 days'
    WHEN active_days <= 7 THEN '4-7 days'
    WHEN active_days <= 14 THEN '8-14 days'
    WHEN active_days <= 30 THEN '15-30 days'
    ELSE '30+ days'
  END AS longevity_bracket,
  COUNT(DISTINCT posting_id) AS postings_count,
  ROUND(AVG(active_days), 1) AS avg_active_days,
  MAX(active_days) AS max_active_days
FROM longevity_calc
GROUP BY
  role_family,
  source_id,
  CASE
    WHEN active_days <= 3 THEN '0-3 days'
    WHEN active_days <= 7 THEN '4-7 days'
    WHEN active_days <= 14 THEN '8-14 days'
    WHEN active_days <= 30 THEN '15-30 days'
    ELSE '30+ days'
  END;
