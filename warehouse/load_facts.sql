-- Job Market Pulse warehouse: populate gold fact tables from staging_postings.
-- fact_job_posting upsert key is (posting_id, date_posted); the match is
-- null-safe because date_posted may be NULL for sources that do not provide it.
-- Disappeared postings are never deleted; last_seen_at simply stops advancing.
-- is_likely_closed is computed downstream in marts, not here.
-- Databricks SQL / Delta.

MERGE INTO fact_job_posting AS target
USING (
  SELECT
    p.posting_id,
    c.company_id,
    l.location_id,
    p.source_id,
    p.job_title,
    p.date_posted,
    p.closing_date,
    p.first_seen_at,
    p.last_seen_at,
    p.is_incomplete
  FROM staging_postings p
  LEFT JOIN dim_company c
    ON c.company_id = MD5(LOWER(p.company_name))
    AND c.is_current = TRUE
  LEFT JOIN dim_location l
    ON l.location_normalized = p.location_normalized
) AS source
ON target.posting_id = source.posting_id
   AND (target.date_posted = source.date_posted
        OR (target.date_posted IS NULL AND source.date_posted IS NULL))
WHEN MATCHED THEN
  UPDATE SET
    last_seen_at = source.last_seen_at,
    first_seen_at = LEAST(target.first_seen_at, source.first_seen_at),
    is_incomplete = target.is_incomplete OR source.is_incomplete
WHEN NOT MATCHED THEN
  INSERT (
    posting_id, company_id, location_id, source_id, job_title, date_posted,
    closing_date, first_seen_at, last_seen_at, is_incomplete
  )
  VALUES (
    source.posting_id, source.company_id, source.location_id, source.source_id,
    source.job_title, source.date_posted, source.closing_date,
    source.first_seen_at, source.last_seen_at, source.is_incomplete
  );

-- Skill mentions are derived from title + description against the seed skill
-- dictionary. Heuristic matching; documented as a known limitation.
CREATE OR REPLACE TABLE fact_posting_skill_mention AS
SELECT DISTINCT
  p.posting_id,
  s.skill_id
FROM staging_postings p
CROSS JOIN dim_skill s
WHERE LOWER(CONCAT(p.job_title, ' ', COALESCE(p.description, ''))) RLIKE CONCAT('\\b', LOWER(s.skill_name), '\\b');
