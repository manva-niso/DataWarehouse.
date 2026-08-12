-- Job Market Pulse warehouse: populate gold dimensions from staging_postings.
-- Rerunnable: dates/locations/skills use CREATE OR REPLACE; companies MERGE
-- insert-only so existing versions are never touched (full SCD2 follows later).
-- Databricks SQL / Delta.

CREATE OR REPLACE TABLE dim_date AS
SELECT
  CAST(DATE_FORMAT(day, 'yyyyMMdd') AS BIGINT) AS date_id,
  day AS `date`,
  DATE_FORMAT(day, 'EEEE') AS day_of_week,
  MONTH(day) AS `month`,
  YEAR(day) AS `year`
FROM (
  SELECT EXPLODE(SEQUENCE(
    (SELECT COALESCE(MIN(date_posted), CURRENT_DATE()) FROM staging_postings),
    (SELECT COALESCE(MAX(date_posted), CURRENT_DATE()) FROM staging_postings),
    INTERVAL 1 DAY
  )) AS day
);

CREATE OR REPLACE TABLE dim_location AS
SELECT
  MD5(location_normalized) AS location_id,
  MIN(location_raw) AS location_raw,
  location_normalized
FROM staging_postings
GROUP BY location_normalized;

CREATE OR REPLACE TABLE dim_skill AS
SELECT
  MD5(LOWER(skill_name)) AS skill_id,
  skill_name
FROM (VALUES
  ('SQL'), ('Python'), ('BigQuery'), ('Tableau'), ('Power BI'), ('Excel'), ('Airflow'),
  ('Spark'), ('Kafka'), ('Docker'), ('AWS'), ('GCP'), ('Azure'), ('Snowflake'),
  ('Pandas'), ('ETL'), ('Machine Learning'), ('Data Modeling'), ('Java'),
  ('JavaScript'), ('React'), ('Statistics'), ('Git'), ('Linux'), ('Kubernetes')
) AS seed(skill_name);

MERGE INTO dim_company AS target
USING (
  SELECT
    MD5(LOWER(company_name)) AS company_id,
    company_name,
    MIN(display_name) AS display_name,
    CURRENT_TIMESTAMP() AS valid_from,
    CAST(NULL AS TIMESTAMP) AS valid_to,
    TRUE AS is_current
  FROM staging_postings
  GROUP BY company_name
) AS source
ON target.company_id = source.company_id
WHEN NOT MATCHED THEN
  INSERT (company_id, company_name, display_name, valid_from, valid_to, is_current)
  VALUES (source.company_id, source.company_name, source.display_name, source.valid_from, source.valid_to, source.is_current);
