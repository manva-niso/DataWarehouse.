-- Job Market Pulse mart: skill demand trend.
-- One row per skill per year-month; dashboard and export read marts only.
-- Databricks SQL / Delta.

CREATE OR REPLACE VIEW mart_skill_demand_trend AS
SELECT
  d.`year`,
  d.`month`,
  s.skill_name,
  COUNT(DISTINCT m.posting_id) AS postings_mentioning_skill
FROM fact_posting_skill_mention m
JOIN dim_skill s ON s.skill_id = m.skill_id
JOIN fact_job_posting f ON f.posting_id = m.posting_id
LEFT JOIN dim_date d
  ON d.date_id = CAST(DATE_FORMAT(f.date_posted, 'yyyyMMdd') AS BIGINT)
GROUP BY d.`year`, d.`month`, s.skill_name;
