-- Job Market Pulse staging: normalize raw source payloads into a common shape.
-- One branch per source (adzuna, greenhouse, lever, rippling), UNION ALL'd.
-- Each raw payload row is JSON text in the raw_{source}.payload column.
-- Greenhouse payloads carry company_name/first_published themselves; the
-- pipeline still enriches greenhouse/lever/rippling with company_display_name
-- from config/companies.yaml as a fallback. Lever createdAt/closedAt are epoch
-- milliseconds, converted with FROM_UNIXTIME. Rippling field names are a
-- documented assumption (publishedAt/createdAt, location string or object)
-- to be verified on first live pull.
-- Databricks SQL / Delta. Tables are unqualified; the configured catalog and
-- schema (workspace.default) resolve them.

CREATE OR REPLACE TABLE staging_postings_normalized AS
WITH normalized AS (
  SELECT
    CONCAT('adzuna-', get_json_object(payload, '$.id')) AS posting_id,
    'adzuna' AS source_id,
    COALESCE(TRIM(get_json_object(payload, '$.company.display_name')), 'Unknown') AS company_name,
    COALESCE(TRIM(get_json_object(payload, '$.company.display_name')), 'Unknown') AS display_name,
    get_json_object(payload, '$.location.display_name') AS location_raw,
    TO_DATE(SUBSTR(get_json_object(payload, '$.created'), 1, 10)) AS date_posted,
    CAST(NULL AS DATE) AS closing_date,
    COALESCE(TRIM(get_json_object(payload, '$.title')), 'Unknown') AS job_title,
    get_json_object(payload, '$.description') AS description,
    ingested_at AS seen_at,
    (
      get_json_object(payload, '$.title') IS NULL
      OR get_json_object(payload, '$.company.display_name') IS NULL
      OR get_json_object(payload, '$.location.display_name') IS NULL
      OR TO_DATE(SUBSTR(get_json_object(payload, '$.created'), 1, 10)) IS NULL
    ) AS is_incomplete
  FROM raw_adzuna

  UNION ALL

  SELECT
    CONCAT('greenhouse-', get_json_object(payload, '$.id')) AS posting_id,
    'greenhouse' AS source_id,
    COALESCE(
      TRIM(get_json_object(payload, '$.company_display_name')),
      TRIM(get_json_object(payload, '$.company_name')),
      'Unknown'
    ) AS company_name,
    COALESCE(
      TRIM(get_json_object(payload, '$.company_display_name')),
      TRIM(get_json_object(payload, '$.company_name')),
      'Unknown'
    ) AS display_name,
    get_json_object(payload, '$.location.name') AS location_raw,
    TO_DATE(SUBSTR(get_json_object(payload, '$.first_published'), 1, 10)) AS date_posted,
    TO_DATE(SUBSTR(get_json_object(payload, '$.application_deadline'), 1, 10)) AS closing_date,
    COALESCE(TRIM(get_json_object(payload, '$.title')), 'Unknown') AS job_title,
    get_json_object(payload, '$.content') AS description,
    ingested_at AS seen_at,
    (
      get_json_object(payload, '$.title') IS NULL
      OR COALESCE(get_json_object(payload, '$.company_display_name'), get_json_object(payload, '$.company_name')) IS NULL
      OR get_json_object(payload, '$.location.name') IS NULL
      OR TO_DATE(SUBSTR(get_json_object(payload, '$.first_published'), 1, 10)) IS NULL
    ) AS is_incomplete
  FROM raw_greenhouse

  UNION ALL

  SELECT
    CONCAT('lever-', get_json_object(payload, '$.id')) AS posting_id,
    'lever' AS source_id,
    COALESCE(
      TRIM(get_json_object(payload, '$.company_display_name')),
      TRIM(get_json_object(payload, '$.company')),
      'Unknown'
    ) AS company_name,
    COALESCE(
      TRIM(get_json_object(payload, '$.company_display_name')),
      TRIM(get_json_object(payload, '$.company')),
      'Unknown'
    ) AS display_name,
    get_json_object(payload, '$.categories.location') AS location_raw,
    TO_DATE(FROM_UNIXTIME(CAST(get_json_object(payload, '$.createdAt') AS BIGINT) / 1000)) AS date_posted,
    TO_DATE(FROM_UNIXTIME(CAST(get_json_object(payload, '$.closedAt') AS BIGINT) / 1000)) AS closing_date,
    COALESCE(TRIM(get_json_object(payload, '$.text')), 'Unknown') AS job_title,
    get_json_object(payload, '$.descriptionPlain') AS description,
    ingested_at AS seen_at,
    (
      get_json_object(payload, '$.text') IS NULL
      OR COALESCE(get_json_object(payload, '$.company_display_name'), get_json_object(payload, '$.company')) IS NULL
      OR get_json_object(payload, '$.categories.location') IS NULL
      OR TO_DATE(FROM_UNIXTIME(CAST(get_json_object(payload, '$.createdAt') AS BIGINT) / 1000)) IS NULL
    ) AS is_incomplete
  FROM raw_lever

  UNION ALL

  SELECT
    CONCAT('rippling-', get_json_object(payload, '$.id')) AS posting_id,
    'rippling' AS source_id,
    COALESCE(TRIM(get_json_object(payload, '$.company_display_name')), 'Unknown') AS company_name,
    COALESCE(TRIM(get_json_object(payload, '$.company_display_name')), 'Unknown') AS display_name,
    COALESCE(
      get_json_object(payload, '$.location.name'),
      get_json_object(payload, '$.location')
    ) AS location_raw,
    TO_DATE(SUBSTR(
      COALESCE(
        get_json_object(payload, '$.publishedAt'),
        get_json_object(payload, '$.createdAt')
      ),
      1, 10
    )) AS date_posted,
    CAST(NULL AS DATE) AS closing_date,
    COALESCE(TRIM(get_json_object(payload, '$.title')), 'Unknown') AS job_title,
    get_json_object(payload, '$.description') AS description,
    ingested_at AS seen_at,
    (
      get_json_object(payload, '$.title') IS NULL
      OR get_json_object(payload, '$.company_display_name') IS NULL
      OR get_json_object(payload, '$.location') IS NULL
      OR TO_DATE(SUBSTR(
        COALESCE(
          get_json_object(payload, '$.publishedAt'),
          get_json_object(payload, '$.createdAt')
        ),
        1, 10
      )) IS NULL
    ) AS is_incomplete
  FROM raw_rippling
),
normalized_clean AS (
  SELECT
    posting_id,
    source_id,
    company_name,
    display_name,
    location_raw,
    COALESCE(
      NULLIF(REGEXP_REPLACE(TRIM(COALESCE(location_raw, '')), '\\s+', ' '), ''),
      'Unknown'
    ) AS location_normalized,
    job_title,
    date_posted,
    closing_date,
    description,
    seen_at,
    is_incomplete
  FROM normalized
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
FROM normalized_clean;
