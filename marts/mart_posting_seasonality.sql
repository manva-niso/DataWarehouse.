-- Job Market Pulse mart: posting seasonality & domain hiring cycles.
-- Computes seasonal hiring cycles (Winter, Spring, Summer, Fall), quarters,
-- domain/role family releases, and entry-level/fresher hiring spikes.
-- Reads live and historical postings to ensure continuous longitudinal analysis.
-- Databricks SQL / Delta.

CREATE OR REPLACE VIEW mart_posting_seasonality AS
WITH all_postings AS (
  SELECT
    f.posting_id,
    f.source_id,
    f.role_family,
    f.date_posted,
    COALESCE(d.is_fresher, FALSE) AS is_fresher,
    COALESCE(d.experience_level, 'UNSPECIFIED') AS experience_level
  FROM fact_job_posting f
  LEFT JOIN job_posting_detail d ON d.posting_id = f.posting_id

  UNION ALL

  SELECT
    arc.posting_id,
    arc.source_id,
    arc.role_family,
    arc.date_posted,
    FALSE AS is_fresher,
    'UNSPECIFIED' AS experience_level
  FROM fact_job_posting_archive arc
)
SELECT
  role_family,
  CASE role_family
    WHEN 'DE' THEN 'Data Engineering'
    WHEN 'DA' THEN 'Data Analytics'
    WHEN 'DS' THEN 'Data Science'
    WHEN 'SWE' THEN 'Software Engineering'
    WHEN 'BI' THEN 'Business Intelligence'
    ELSE 'Other Tech'
  END AS domain_name,
  CASE
    WHEN MONTH(COALESCE(date_posted, CURRENT_DATE())) IN (12, 1, 2) THEN 'Winter'
    WHEN MONTH(COALESCE(date_posted, CURRENT_DATE())) IN (3, 4, 5) THEN 'Spring'
    WHEN MONTH(COALESCE(date_posted, CURRENT_DATE())) IN (6, 7, 8) THEN 'Summer'
    ELSE 'Fall / Autumn'
  END AS season,
  CONCAT('Q', QUARTER(COALESCE(date_posted, CURRENT_DATE()))) AS quarter,
  YEAR(COALESCE(date_posted, CURRENT_DATE())) AS posting_year,
  MONTH(COALESCE(date_posted, CURRENT_DATE())) AS month_of_year,
  DATE_FORMAT(COALESCE(date_posted, CURRENT_DATE()), 'MMMM') AS month_name,
  DATE_FORMAT(COALESCE(date_posted, CURRENT_DATE()), 'yyyy-MM') AS year_month,
  source_id,
  COUNT(DISTINCT posting_id) AS posting_count,
  SUM(CASE WHEN is_fresher OR experience_level = 'FRESHER' THEN 1 ELSE 0 END) AS fresher_postings_count
FROM all_postings
GROUP BY
  role_family,
  source_id,
  season,
  quarter,
  posting_year,
  month_of_year,
  month_name,
  year_month;
