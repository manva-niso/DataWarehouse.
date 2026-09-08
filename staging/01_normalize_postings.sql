-- Job Market Pulse staging: normalize raw source payloads into a common shape.
-- One branch per source (adzuna, greenhouse, lever, rippling), UNION ALL'd.
-- Each raw payload row is JSON text in the raw_{source}.payload column.
-- Greenhouse payloads carry company_name/first_published themselves; the
-- pipeline still enriches greenhouse/lever/rippling with company_display_name
-- from config/companies.yaml as a fallback. Lever createdAt/closedAt are epoch
-- milliseconds, converted with FROM_UNIXTIME. Rippling is normalized from the
-- verified v2 API fields (uuid/name/workLocations/createdOn/description).
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
    get_json_object(payload, '$.redirect_url') AS posting_url,
    get_json_object(payload, '$.redirect_url') AS apply_url,
    CAST(get_json_object(payload, '$.salary_min') AS DOUBLE) AS salary_min,
    CAST(get_json_object(payload, '$.salary_max') AS DOUBLE) AS salary_max,
    COALESCE(get_json_object(payload, '$.salary_currency'), get_json_object(payload, '$.currency')) AS currency,
    COALESCE(get_json_object(payload, '$.contract_type'), get_json_object(payload, '$.contract_time')) AS employment_type,
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
    get_json_object(payload, '$.absolute_url') AS posting_url,
    get_json_object(payload, '$.absolute_url') AS apply_url,
    CAST(NULL AS DOUBLE) AS salary_min,
    CAST(NULL AS DOUBLE) AS salary_max,
    CAST(NULL AS STRING) AS currency,
    CAST(NULL AS STRING) AS employment_type,
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
    get_json_object(payload, '$.hostedUrl') AS posting_url,
    get_json_object(payload, '$.applyUrl') AS apply_url,
    CAST(get_json_object(payload, '$.salaryRange.min') AS DOUBLE) AS salary_min,
    CAST(get_json_object(payload, '$.salaryRange.max') AS DOUBLE) AS salary_max,
    get_json_object(payload, '$.salaryRange.currency') AS currency,
    get_json_object(payload, '$.categories.commitment') AS employment_type,
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
    CONCAT('rippling-', COALESCE(
      get_json_object(payload, '$.uuid'),
      get_json_object(payload, '$.id')
    )) AS posting_id,
    'rippling' AS source_id,
    COALESCE(
      TRIM(get_json_object(payload, '$.company_display_name')),
      TRIM(get_json_object(payload, '$.companyName')),
      'Unknown'
    ) AS company_name,
    COALESCE(
      TRIM(get_json_object(payload, '$.company_display_name')),
      TRIM(get_json_object(payload, '$.companyName')),
      'Unknown'
    ) AS display_name,
    COALESCE(
      get_json_object(payload, '$.workLocations[0]'),
      get_json_object(payload, '$.location')
    ) AS location_raw,
    TO_DATE(SUBSTR(
      COALESCE(
        get_json_object(payload, '$.createdOn'),
        get_json_object(payload, '$.publishedAt'),
        get_json_object(payload, '$.createdAt')
      ),
      1, 10
    )) AS date_posted,
    CAST(NULL AS DATE) AS closing_date,
    COALESCE(TRIM(get_json_object(payload, '$.name')), 'Unknown') AS job_title,
    COALESCE(
      get_json_object(payload, '$.description.role'),
      get_json_object(payload, '$.description.company'),
      get_json_object(payload, '$.description')
    ) AS description,
    get_json_object(payload, '$.url') AS posting_url,
    get_json_object(payload, '$.url') AS apply_url,
    CAST(get_json_object(payload, '$.payRangeDetails.minSalary') AS DOUBLE) AS salary_min,
    CAST(get_json_object(payload, '$.payRangeDetails.maxSalary') AS DOUBLE) AS salary_max,
    get_json_object(payload, '$.payRangeDetails.currency') AS currency,
    get_json_object(payload, '$.employmentType') AS employment_type,
    ingested_at AS seen_at,
    (
      get_json_object(payload, '$.name') IS NULL
      OR COALESCE(
        get_json_object(payload, '$.company_display_name'),
        get_json_object(payload, '$.companyName')
      ) IS NULL
      OR COALESCE(
        get_json_object(payload, '$.workLocations[0]'),
        get_json_object(payload, '$.location')
      ) IS NULL
      OR TO_DATE(SUBSTR(
        COALESCE(
          get_json_object(payload, '$.createdOn'),
          get_json_object(payload, '$.publishedAt'),
          get_json_object(payload, '$.createdAt')
        ),
        1, 10
      )) IS NULL
    ) AS is_incomplete
  FROM raw_rippling

  UNION ALL

  SELECT
    CONCAT('ashby-', get_json_object(payload, '$.id')) AS posting_id,
    'ashby' AS source_id,
    COALESCE(
      TRIM(get_json_object(payload, '$.company_display_name')),
      'Unknown'
    ) AS company_name,
    COALESCE(
      TRIM(get_json_object(payload, '$.company_display_name')),
      'Unknown'
    ) AS display_name,
    COALESCE(
      get_json_object(payload, '$.location'),
      CONCAT_WS(', ',
        get_json_object(payload, '$.address.postalAddress.addressLocality'),
        get_json_object(payload, '$.address.postalAddress.addressCountry')
      ),
      CASE WHEN get_json_object(payload, '$.isRemote') = 'true' THEN 'Remote' ELSE 'Unspecified' END
    ) AS location_raw,
    TO_DATE(SUBSTR(get_json_object(payload, '$.publishedAt'), 1, 10)) AS date_posted,
    CAST(NULL AS DATE) AS closing_date,
    COALESCE(TRIM(get_json_object(payload, '$.title')), 'Unknown') AS job_title,
    COALESCE(
      get_json_object(payload, '$.descriptionPlain'),
      get_json_object(payload, '$.descriptionHtml')
    ) AS description,
    get_json_object(payload, '$.jobUrl') AS posting_url,
    COALESCE(
      get_json_object(payload, '$.applyUrl'),
      get_json_object(payload, '$.jobUrl')
    ) AS apply_url,
    CAST(NULL AS DOUBLE) AS salary_min,
    CAST(NULL AS DOUBLE) AS salary_max,
    CAST(NULL AS STRING) AS currency,
    get_json_object(payload, '$.employmentType') AS employment_type,
    ingested_at AS seen_at,
    (
      get_json_object(payload, '$.title') IS NULL
      OR get_json_object(payload, '$.company_display_name') IS NULL
      OR (get_json_object(payload, '$.location') IS NULL AND get_json_object(payload, '$.address.postalAddress.addressLocality') IS NULL)
      OR TO_DATE(SUBSTR(get_json_object(payload, '$.publishedAt'), 1, 10)) IS NULL
    ) AS is_incomplete
  FROM raw_ashby
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
    CASE
      WHEN LOWER(job_title) RLIKE '\\b(data engineer|data engineering|analytics engineer|etl|pipeline|big data|database engineer|warehouse engineer)\\b' THEN 'DE'
      WHEN LOWER(job_title) RLIKE '\\b(business intelligence|bi developer|bi engineer|bi analyst|tableau developer|power bi developer)\\b' THEN 'BI'
      WHEN LOWER(job_title) RLIKE '\\b(data scientist|data science|machine learning|ml engineer|mle|ai engineer|nlp|deep learning|computer vision)\\b' THEN 'DS'
      WHEN LOWER(job_title) RLIKE '\\b(data analyst|data analytics|business analyst|product analyst|reporting analyst|operations analyst|quantitative analyst)\\b' THEN 'DA'
      WHEN LOWER(job_title) RLIKE '\\b(software engineer|software developer|backend|frontend|full stack|fullstack|devops|sre|systems engineer|programmer|ios developer|android developer|web developer|platform engineer)\\b' THEN 'SWE'
      ELSE 'OTHER'
    END AS role_family,
    date_posted,
    closing_date,
    TRIM(REGEXP_REPLACE(REGEXP_REPLACE(COALESCE(description, ''), '<[^>]+>', ' '), '\\s+', ' ')) AS description,
    posting_url,
    apply_url,
    salary_min,
    salary_max,
    currency,
    employment_type,
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
  role_family,
  date_posted,
  closing_date,
  description,
  posting_url,
  apply_url,
  salary_min,
  salary_max,
  currency,
  employment_type,
  seen_at,
  is_incomplete,
  CONCAT(LOWER(company_name), '|', LOWER(job_title), '|', LOWER(location_normalized)) AS dedup_key
FROM normalized_clean;
