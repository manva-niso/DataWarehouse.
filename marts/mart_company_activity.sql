-- Job Market Pulse mart: company activity.
-- Posting volume and activity signal per company. is_likely_closed uses the
-- same downstream rule as the tracker mart: last_seen_at < now - 3 days.
-- Databricks SQL / Delta.

CREATE OR REPLACE VIEW mart_company_activity AS
SELECT
  c.company_id,
  c.company_name,
  COUNT(DISTINCT f.posting_id) AS total_postings,
  COUNT(DISTINCT CASE
    WHEN f.last_seen_at < CURRENT_TIMESTAMP() - INTERVAL 3 DAY
    THEN f.posting_id
  END) AS likely_closed_postings,
  COUNT(DISTINCT CASE
    WHEN f.last_seen_at >= CURRENT_TIMESTAMP() - INTERVAL 3 DAY
    THEN f.posting_id
  END) AS active_postings,
  MIN(f.first_seen_at) AS earliest_first_seen,
  MAX(f.last_seen_at) AS latest_last_seen
FROM fact_job_posting f
JOIN dim_company c
  ON c.company_id = f.company_id
  AND c.is_current = TRUE
GROUP BY c.company_id, c.company_name;
