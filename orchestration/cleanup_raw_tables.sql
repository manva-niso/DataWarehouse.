-- Job Market Pulse raw retention cleanup.
-- Executed by cleanup_raw_tables() once per allowed raw source: the {table}
-- placeholder is substituted from a hardcoded source allowlist, and
-- {retention_days} is substituted with a positive integer.
-- cleanup_raw_tables() rejects non-positive windows before executing.
-- Databricks SQL / Delta.

DELETE FROM `{table}`
WHERE ingested_at < CURRENT_TIMESTAMP() - INTERVAL {retention_days} DAY;
