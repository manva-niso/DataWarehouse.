-- Job Market Pulse mart: salary summary.
-- Aggregated salary statistics by role family, location, and source.
-- Reads live and archived postings where salary data is available.
-- Databricks SQL / Delta.

CREATE OR REPLACE VIEW mart_salary_summary AS
WITH all_postings AS (
  SELECT posting_id, company_id, location_id, source_id, role_family
  FROM fact_job_posting
  UNION ALL
  SELECT posting_id, company_id, location_id, source_id, role_family
  FROM fact_job_posting_archive
)
SELECT
  p.role_family,
  COALESCE(l.location_normalized, 'Unknown') AS location,
  p.source_id,
  COALESCE(d.currency, 'Unknown') AS currency,
  COUNT(DISTINCT p.posting_id) AS postings_with_salary,
  ROUND(MIN(d.salary_min), 2) AS min_salary_lowest,
  ROUND(AVG(d.salary_min), 2) AS avg_salary_min,
  ROUND(AVG(d.salary_max), 2) AS avg_salary_max,
  ROUND(MAX(d.salary_max), 2) AS max_salary_highest
FROM all_postings p
JOIN job_posting_detail d
  ON d.posting_id = p.posting_id
  AND (d.salary_min IS NOT NULL OR d.salary_max IS NOT NULL)
LEFT JOIN dim_location l
  ON l.location_id = p.location_id
GROUP BY
  p.role_family,
  COALESCE(l.location_normalized, 'Unknown'),
  p.source_id,
  COALESCE(d.currency, 'Unknown');
