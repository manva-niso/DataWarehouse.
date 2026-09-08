-- Job Market Pulse mart: role market dynamics.
-- Postings count, salary stats, and volume per role family and month.
-- Reads live and archived postings.
-- Databricks SQL / Delta.

CREATE OR REPLACE VIEW mart_role_market AS
WITH all_postings AS (
  SELECT posting_id, role_family, date_posted, source_id
  FROM fact_job_posting
  UNION ALL
  SELECT posting_id, role_family, date_posted, source_id
  FROM fact_job_posting_archive
),
postings_with_detail AS (
  SELECT
    p.posting_id,
    p.role_family,
    DATE_FORMAT(COALESCE(p.date_posted, CURRENT_DATE()), 'yyyy-MM') AS year_month,
    d.salary_min,
    d.salary_max
  FROM all_postings p
  LEFT JOIN job_posting_detail d ON d.posting_id = p.posting_id
)
SELECT
  role_family,
  year_month,
  COUNT(DISTINCT posting_id) AS total_postings,
  ROUND(AVG(salary_min), 2) AS avg_salary_min,
  ROUND(AVG(salary_max), 2) AS avg_salary_max
FROM postings_with_detail
GROUP BY role_family, year_month;
