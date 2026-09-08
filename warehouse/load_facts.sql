-- Job Market Pulse warehouse: populate gold fact tables from staging_postings.
-- fact_job_posting upsert key is (posting_id, date_posted); the match is
-- null-safe because date_posted may be NULL for sources that do not provide it.
-- Disappeared postings are never deleted; last_seen_at simply stops advancing.
-- is_likely_closed is computed downstream in marts, not here.
-- Databricks SQL / Delta.

MERGE INTO fact_job_posting AS target
USING (
  SELECT
    posting_id,
    company_id,
    location_id,
    source_id,
    job_title,
    role_family,
    date_posted,
    closing_date,
    first_seen_at,
    last_seen_at,
    is_incomplete
  FROM (
    SELECT
      p.posting_id,
      c.company_id,
      l.location_id,
      p.source_id,
      p.job_title,
      p.role_family,
      p.date_posted,
      p.closing_date,
      p.first_seen_at,
      p.last_seen_at,
      p.is_incomplete,
      ROW_NUMBER() OVER (
        PARTITION BY p.posting_id, COALESCE(p.date_posted, '1970-01-01')
        ORDER BY p.last_seen_at DESC, p.first_seen_at DESC
      ) AS rn
    FROM staging_postings p
    LEFT JOIN dim_company c
      ON c.company_id = MD5(LOWER(p.company_name))
      AND c.is_current = TRUE
    LEFT JOIN dim_location l
      ON l.location_normalized = p.location_normalized
  )
  WHERE rn = 1
) AS source
ON target.posting_id = source.posting_id
   AND (target.date_posted = source.date_posted
        OR (target.date_posted IS NULL AND source.date_posted IS NULL))
WHEN MATCHED THEN
  UPDATE SET
    role_family = source.role_family,
    last_seen_at = source.last_seen_at,
    first_seen_at = LEAST(target.first_seen_at, source.first_seen_at),
    is_incomplete = target.is_incomplete OR source.is_incomplete
WHEN NOT MATCHED THEN
  INSERT (
    posting_id, company_id, location_id, source_id, job_title, role_family, date_posted,
    closing_date, first_seen_at, last_seen_at, is_incomplete
  )
  VALUES (
    source.posting_id, source.company_id, source.location_id, source.source_id,
    source.job_title, source.role_family, source.date_posted, source.closing_date,
    source.first_seen_at, source.last_seen_at, source.is_incomplete
  );

-- Detail table is refreshed via MERGE on posting_id with experience requirements parsed.
MERGE INTO job_posting_detail AS target
USING (
  SELECT
    posting_id,
    description,
    posting_url,
    apply_url,
    salary_min,
    salary_max,
    currency,
    employment_type,
    last_seen_at,
    min_years_exp,
    max_years_exp,
    is_fresher,
    CASE
      WHEN is_fresher OR (min_years_exp IS NOT NULL AND min_years_exp <= 1) THEN 'FRESHER'
      WHEN min_years_exp IS NOT NULL AND min_years_exp <= 2 THEN 'JUNIOR'
      WHEN min_years_exp IS NOT NULL AND min_years_exp <= 5 THEN 'MID'
      WHEN min_years_exp IS NOT NULL AND min_years_exp <= 8 THEN 'SENIOR'
      WHEN min_years_exp IS NOT NULL AND min_years_exp > 8 THEN 'LEAD'
      WHEN LOWER(job_title) RLIKE '\\b(lead|principal|staff|architect|director)\\b' THEN 'LEAD'
      WHEN LOWER(job_title) RLIKE '\\b(senior|sr\\.?)\\b' THEN 'SENIOR'
      ELSE 'UNSPECIFIED'
    END AS experience_level
  FROM (
    SELECT
      posting_id,
      job_title,
      description,
      posting_url,
      apply_url,
      salary_min,
      salary_max,
      currency,
      employment_type,
      last_seen_at,
      is_fresher,
      CASE
        WHEN is_fresher THEN 0
        WHEN range_min IS NOT NULL AND range_min >= 0 AND range_min <= 20 THEN range_min
        WHEN single_min IS NOT NULL AND single_min >= 0 AND single_min <= 20 THEN single_min
        WHEN LOWER(job_title) RLIKE '\\b(senior|sr\\.?|lead|principal|staff)\\b' THEN 5
        ELSE NULL
      END AS min_years_exp,
      CASE
        WHEN is_fresher THEN 1
        WHEN range_max IS NOT NULL AND range_max >= 0 AND range_max <= 25 THEN range_max
        ELSE NULL
      END AS max_years_exp,
      ROW_NUMBER() OVER (PARTITION BY posting_id ORDER BY last_seen_at DESC) AS rn
    FROM (
      SELECT
        posting_id,
        job_title,
        description,
        posting_url,
        apply_url,
        salary_min,
        salary_max,
        currency,
        employment_type,
        last_seen_at,
        CASE
          WHEN LOWER(job_title) RLIKE '\\b(intern|internship|trainee|apprentice|co-op|fresher|graduate|new grad|entry level)\\b'
            OR LOWER(COALESCE(description, '')) RLIKE '\\b(freshers?|new grads?|college grads?|entry level|no experience required|0\\s*years?|0\\s*-\\s*1\\s*years?)\\b'
          THEN TRUE
          ELSE FALSE
        END AS is_fresher,
        TRY_CAST(REGEXP_EXTRACT(LOWER(COALESCE(description, '')), '(\\d+)\\s*(?:-|to)\\s*\\d+\\+?\\s*(?:years?|yrs?)', 1) AS INT) AS range_min,
        TRY_CAST(REGEXP_EXTRACT(LOWER(COALESCE(description, '')), '\\d+\\s*(?:-|to)\\s*(\\d+)\\+?\\s*(?:years?|yrs?)', 1) AS INT) AS range_max,
        TRY_CAST(REGEXP_EXTRACT(LOWER(COALESCE(description, '')), '(?:at least|minimum|min\\.?|over)?\\s*(\\d+)\\+?\\s*(?:years?|yrs?)(?:\\s+of)?(?:\\s+relevant|\\s+demonstrated|\\s+professional|\\s+working)?\\s*experience', 1) AS INT) AS single_min
      FROM staging_postings
    ) sub1
  ) sub2
  WHERE rn = 1
) AS source
ON target.posting_id = source.posting_id
WHEN MATCHED THEN
  UPDATE SET
    description = COALESCE(source.description, target.description),
    posting_url = COALESCE(source.posting_url, target.posting_url),
    apply_url = COALESCE(source.apply_url, target.apply_url),
    salary_min = COALESCE(source.salary_min, target.salary_min),
    salary_max = COALESCE(source.salary_max, target.salary_max),
    currency = COALESCE(source.currency, target.currency),
    employment_type = COALESCE(source.employment_type, target.employment_type),
    last_seen_at = source.last_seen_at,
    min_years_exp = source.min_years_exp,
    max_years_exp = source.max_years_exp,
    is_fresher = source.is_fresher,
    experience_level = source.experience_level
WHEN NOT MATCHED THEN
  INSERT (
    posting_id, description, posting_url, apply_url, salary_min, salary_max,
    currency, employment_type, last_seen_at, min_years_exp, max_years_exp,
    is_fresher, experience_level
  )
  VALUES (
    source.posting_id, source.description, source.posting_url, source.apply_url,
    source.salary_min, source.salary_max, source.currency, source.employment_type,
    source.last_seen_at, source.min_years_exp, source.max_years_exp,
    source.is_fresher, source.experience_level
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
