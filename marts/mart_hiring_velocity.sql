-- Job Market Pulse mart: hiring velocity.
-- Postings per company per month; shows posting-volume velocity over time.
-- Databricks SQL / Delta.

CREATE OR REPLACE VIEW mart_hiring_velocity AS
SELECT
  d.`year`,
  d.`month`,
  c.company_name,
  COUNT(DISTINCT f.posting_id) AS postings_posted
FROM fact_job_posting f
JOIN dim_company c
  ON c.company_id = f.company_id
  AND c.is_current = TRUE
LEFT JOIN dim_date d
  ON d.date_id = CAST(DATE_FORMAT(f.date_posted, 'yyyyMMdd') AS BIGINT)
GROUP BY d.`year`, d.`month`, c.company_name;
