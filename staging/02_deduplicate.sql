-- Job Market Pulse staging: deduplicate normalized postings across pulls and sources.
-- Dedup key = normalized(company_name) + title + normalized(location).
-- Known false-positive risk for exact-title collisions; documented, not solved perfectly.
-- Keep the earliest first_seen_at; re-seen postings keep one row with a later last_seen_at.
-- Databricks SQL / Delta.

CREATE OR REPLACE TABLE staging_postings AS
WITH grouped AS (
  SELECT
    posting_id,
    source_id,
    company_name,
    display_name,
    location_raw,
    location_normalized,
    job_title,
    date_posted,
    closing_date,
    description,
    is_incomplete,
    dedup_key,
    MIN(seen_at) AS first_seen_at,
    MAX(seen_at) AS last_seen_at
  FROM staging_postings_normalized
  GROUP BY
    posting_id,
    source_id,
    company_name,
    display_name,
    location_raw,
    location_normalized,
    job_title,
    date_posted,
    closing_date,
    description,
    is_incomplete,
    dedup_key
),
ranked AS (
  SELECT
    *,
    ROW_NUMBER() OVER (PARTITION BY dedup_key ORDER BY first_seen_at ASC, posting_id ASC) AS dedup_rn
  FROM grouped
)
SELECT
  posting_id,
  source_id,
  company_name,
  display_name,
  location_raw,
  location_normalized,
  job_title,
  date_posted,
  closing_date,
  description,
  first_seen_at,
  last_seen_at,
  is_incomplete
FROM ranked
WHERE dedup_rn = 1;
