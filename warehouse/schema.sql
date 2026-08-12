-- Job Market Pulse warehouse schema
-- Databricks SQL / Delta (hive_metastore). Run this file against the configured
-- catalog and schema via orchestration/apply_schema.py.
-- The DDL is rerunnable; raw tables remain append-only by pipeline behavior.

-- Dimensions
CREATE TABLE IF NOT EXISTS dim_company (
  company_id STRING NOT NULL,
  company_name STRING NOT NULL,
  display_name STRING NOT NULL,
  valid_from TIMESTAMP NOT NULL,
  valid_to TIMESTAMP,
  is_current BOOLEAN NOT NULL
)
USING DELTA
COMMENT 'SCD Type 2 company dimension. A company can have multiple historical versions.';

CREATE TABLE IF NOT EXISTS dim_location (
  location_id STRING NOT NULL,
  location_raw STRING NOT NULL,
  location_normalized STRING NOT NULL
)
USING DELTA
COMMENT 'Normalized job-posting locations.';

CREATE TABLE IF NOT EXISTS dim_skill (
  skill_id STRING NOT NULL,
  skill_name STRING NOT NULL
)
USING DELTA
COMMENT 'Canonical skills mentioned by job postings.';

CREATE TABLE IF NOT EXISTS dim_date (
  date_id BIGINT NOT NULL,
  `date` DATE NOT NULL,
  day_of_week STRING NOT NULL,
  `month` BIGINT NOT NULL,
  `year` BIGINT NOT NULL
)
USING DELTA
COMMENT 'Calendar dimension used by warehouse facts and marts.';

CREATE TABLE IF NOT EXISTS dim_source (
  source_id STRING NOT NULL,
  source_name STRING NOT NULL
)
USING DELTA
COMMENT 'Job-posting source system dimension.';

-- Keep the fixed source vocabulary available on every schema setup.
MERGE INTO dim_source AS target
USING (
  SELECT source_id, source_name
  FROM VALUES
    ('greenhouse', 'Greenhouse'),
    ('lever', 'Lever'),
    ('rippling', 'Rippling'),
    ('adzuna', 'Adzuna')
  AS seed(source_id, source_name)
) AS source
ON target.source_id = source.source_id
WHEN NOT MATCHED THEN
  INSERT (source_id, source_name)
  VALUES (source.source_id, source.source_name);

-- Facts
-- The natural upsert key is (posting_id, date_posted). It is intentionally
-- documented rather than enforced because date_posted can be incomplete.
CREATE TABLE IF NOT EXISTS fact_job_posting (
  posting_id STRING NOT NULL,
  company_id STRING NOT NULL,
  location_id STRING NOT NULL,
  source_id STRING NOT NULL,
  job_title STRING NOT NULL,
  date_posted DATE,
  closing_date DATE,
  first_seen_at TIMESTAMP NOT NULL,
  last_seen_at TIMESTAMP NOT NULL,
  is_incomplete BOOLEAN NOT NULL
)
USING DELTA
COMMENT 'Current deduplicated job postings. Rows are never deleted when a posting disappears from a pull.';

CREATE TABLE IF NOT EXISTS fact_posting_skill_mention (
  posting_id STRING NOT NULL,
  skill_id STRING NOT NULL
)
USING DELTA
COMMENT 'Many-to-many relationship between postings and mentioned skills.';

-- Raw bronze tables. Each source writes one JSON payload row and never
-- updates or deletes rows during normal ingestion. payload is JSON text.
CREATE TABLE IF NOT EXISTS raw_greenhouse (
  payload STRING NOT NULL,
  run_id STRING NOT NULL,
  ingested_at TIMESTAMP NOT NULL
)
USING DELTA
COMMENT 'Append-only raw Greenhouse API payloads.';

CREATE TABLE IF NOT EXISTS raw_lever (
  payload STRING NOT NULL,
  run_id STRING NOT NULL,
  ingested_at TIMESTAMP NOT NULL
)
USING DELTA
COMMENT 'Append-only raw Lever API payloads.';

CREATE TABLE IF NOT EXISTS raw_rippling (
  payload STRING NOT NULL,
  run_id STRING NOT NULL,
  ingested_at TIMESTAMP NOT NULL
)
USING DELTA
COMMENT 'Append-only raw Rippling API payloads.';

CREATE TABLE IF NOT EXISTS raw_adzuna (
  payload STRING NOT NULL,
  run_id STRING NOT NULL,
  ingested_at TIMESTAMP NOT NULL
)
USING DELTA
COMMENT 'Append-only raw Adzuna API payloads.';

-- Manually maintained application tracking.
CREATE TABLE IF NOT EXISTS applications (
  posting_id STRING NOT NULL,
  date_applied DATE NOT NULL
)
USING DELTA
COMMENT 'User-maintained application dates keyed by posting.';

-- Operational and data-quality logging.
CREATE TABLE IF NOT EXISTS pipeline_run_log (
  run_id STRING NOT NULL,
  source STRING NOT NULL,
  status STRING NOT NULL,
  rows_written BIGINT NOT NULL,
  started_at TIMESTAMP NOT NULL,
  ended_at TIMESTAMP NOT NULL
)
USING DELTA
COMMENT 'One record per source and pipeline run outcome.';

CREATE TABLE IF NOT EXISTS data_quality_log (
  run_id STRING NOT NULL,
  rule_name STRING NOT NULL,
  status STRING NOT NULL,
  rows_affected BIGINT NOT NULL,
  checked_at TIMESTAMP NOT NULL
)
USING DELTA
COMMENT 'Results from staging and warehouse data-quality rules.';
