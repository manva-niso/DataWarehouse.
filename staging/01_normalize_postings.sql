-- Job Market Pulse staging: normalize raw source payloads into a common shape.
-- Reads raw_adzuna (vertical slice). Later sources append below this step.
-- Databricks SQL / Delta. Tables are unqualified; the configured catalog and
-- schema (hive_metastore.default) resolve them.

CREATE OR REPLACE TABLE staging_postings_normalized AS
WITH normalized AS (
  SELECT
    CONCAT('adzuna-', get_json_object(payload, '$.id')) AS posting_id,
    'adzuna' AS source_id,
    COALESCE(TRIM(get_json_object(payload, '$.company.display_name')), 'Unknown') AS company_name,
    COALESCE(TRIM(get_json_object(payload, '$.company.display_name')), 'Unknown') AS display_name,
    get_json_object(payload, '$.location.display_name') AS location_raw,
    COALESCE(
      NULLIF(REGEXP_REPLACE(TRIM(COALESCE(get_json_object(payload, '$.location.display_name'), '')), '\\s+', ' '), ''),
      'Unknown'
    ) AS location_normalized,
    COALESCE(TRIM(get_json_object(payload, '$.title')), 'Unknown') AS job_title,
    TO_DATE(SUBSTR(get_json_object(payload, '$.created'), 1, 10)) AS date_posted,
    CAST(NULL AS DATE) AS closing_date,
    get_json_object(payload, '$.description') AS description,
    ingested_at AS seen_at,
    (
      get_json_object(payload, '$.title') IS NULL
      OR get_json_object(payload, '$.company.display_name') IS NULL
      OR get_json_object(payload, '$.location.display_name') IS NULL
      OR TO_DATE(SUBSTR(get_json_object(payload, '$.created'), 1, 10)) IS NULL
    ) AS is_incomplete
  FROM raw_adzuna
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
  seen_at,
  is_incomplete,
  CONCAT(LOWER(company_name), '|', LOWER(job_title), '|', LOWER(location_normalized)) AS dedup_key
FROM normalized;
