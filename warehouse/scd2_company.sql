-- Job Market Pulse: SCD Type 2 on dim_company.
-- A new version is created only when a tracked attribute (display_name)
-- actually changes. Unchanged companies keep their current version.
-- Rerunnable: closing is idempotent, and step 2 only inserts a fresh current
-- version when no current version exists.

-- Step 1: close current versions whose tracked attributes differ from staging.
UPDATE dim_company AS c
SET valid_to = CURRENT_TIMESTAMP(), is_current = FALSE
WHERE c.is_current = TRUE
  AND EXISTS (
    SELECT 1
    FROM (
      SELECT
        TO_HEX(MD5(LOWER(company_name))) AS company_id,
        MIN(display_name) AS display_name
      FROM staging_postings
      GROUP BY company_name
    ) AS s
    WHERE s.company_id = c.company_id
      AND s.display_name IS DISTINCT FROM c.display_name
  );

-- Step 2: open a fresh current version for any company without one.
INSERT INTO dim_company (company_id, company_name, display_name, valid_from, valid_to, is_current)
SELECT
  s.company_id,
  s.company_name,
  s.display_name,
  CURRENT_TIMESTAMP(),
  CAST(NULL AS TIMESTAMP),
  TRUE
FROM (
  SELECT
    TO_HEX(MD5(LOWER(company_name))) AS company_id,
    company_name,
    MIN(display_name) AS display_name
  FROM staging_postings
  GROUP BY company_name
) AS s
LEFT JOIN dim_company AS c
  ON c.company_id = s.company_id AND c.is_current = TRUE
WHERE c.company_id IS NULL;
