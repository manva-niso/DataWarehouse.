-- Job Market Pulse mart: application funnel and status conversion over time.
-- Counts by status, month applied, and conversion tracking.
-- Databricks SQL / Delta.

CREATE OR REPLACE VIEW mart_application_funnel AS
SELECT
  status,
  DATE_FORMAT(date_applied, 'yyyy-MM') AS application_month,
  COUNT(DISTINCT posting_id) AS applications_count,
  ROUND(COUNT(DISTINCT posting_id) * 100.0 / SUM(COUNT(DISTINCT posting_id)) OVER (PARTITION BY DATE_FORMAT(date_applied, 'yyyy-MM')), 2) AS percentage_of_month
FROM applications
GROUP BY
  status,
  DATE_FORMAT(date_applied, 'yyyy-MM');
