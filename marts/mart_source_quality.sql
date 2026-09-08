-- Job Market Pulse mart: source quality and completeness metrics.
-- Rows per source, incomplete %, distinct companies, and date coverage.
-- Reads live and archived postings.
-- Databricks SQL / Delta.

CREATE OR REPLACE VIEW mart_source_quality AS
WITH all_postings AS (
  SELECT
    posting_id,
    company_id,
    source_id,
    date_posted,
    is_incomplete
  FROM fact_job_posting
  UNION ALL
  SELECT
    posting_id,
    company_id,
    source_id,
    date_posted,
    is_incomplete
  FROM fact_job_posting_archive
)
SELECT
  source_id,
  COUNT(DISTINCT posting_id) AS total_postings,
  COUNT(DISTINCT company_id) AS distinct_companies,
  SUM(CASE WHEN is_incomplete THEN 1 ELSE 0 END) AS incomplete_postings,
  ROUND(SUM(CASE WHEN is_incomplete THEN 1.0 ELSE 0.0 END) / COUNT(DISTINCT posting_id) * 100, 2) AS incomplete_percentage,
  MIN(date_posted) AS earliest_posting_date,
  MAX(date_posted) AS latest_posting_date
FROM all_postings
GROUP BY source_id;
