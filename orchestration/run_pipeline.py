"""Pipeline entrypoint for Job Market Pulse.

Runs all extractors -> staging -> warehouse -> marts in sequence behind a
file-based lock that prevents concurrent runs. Partial success is preferred
over aborting: a failed source is logged while the remaining sources run, and
downstream stages run when at least one source succeeded. The run logger is
always called, even on partial or complete failure.

Greenhouse, Lever, and Rippling payloads are enriched with a
company_display_name field at fetch time (from config/companies.yaml) because
their APIs do not include a human-readable company name; the raw payload
columns otherwise stay untouched. All warehouse access goes through the dbio
package (Databricks SQL).
"""

import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml
from dotenv import load_dotenv

from dbio import insert_rows, query_rows, run_sql, run_sql_script
from ingestion.adzuna_extractor import RESULTS_PER_PAGE, fetch_adzuna_jobs
from ingestion.bigquery_io import write_to_bigquery_raw
from ingestion.greenhouse_extractor import fetch_greenhouse_jobs
from ingestion.lever_extractor import fetch_lever_jobs
from ingestion.rippling_extractor import fetch_rippling_jobs
from marts.refresh import refresh_mart_views
from staging.data_quality_checks import run_data_quality_checks
from warehouse.loaders import load_dim_company, load_fact_job_posting, load_user_profile

logger = logging.getLogger(__name__)

SOURCES = ("adzuna", "greenhouse", "lever", "rippling")
LOCK_FILE = Path(__file__).with_name(".pipeline.lock")
STAGING_SQL_DIR = Path(__file__).parents[1] / "staging"
DEFAULT_WATERMARK_DAYS = 30


def _acquire_lock() -> bool:
    try:
        fd = os.open(LOCK_FILE, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, str(os.getpid()).encode("ascii"))
        os.close(fd)
        return True
    except FileExistsError:
        try:
            pid = int(LOCK_FILE.read_text(encoding="ascii").strip())
        except (OSError, ValueError):
            return False
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            logger.warning("Removing stale pipeline lock for pid %d", pid)
            _release_lock()
            return _acquire_lock()
        except PermissionError:
            return False
        except OSError:
            logger.warning("Removing stale pipeline lock for pid %d", pid)
            _release_lock()
            return _acquire_lock()
        return False


def _release_lock() -> None:
    try:
        LOCK_FILE.unlink()
    except FileNotFoundError:
        pass


def get_last_watermark(source: str) -> datetime:
    """Return the last successful run's timestamp for source; default 30 days ago."""
    rows = query_rows(
        "SELECT MAX(ended_at) AS last_run FROM pipeline_run_log "
        "WHERE source = :source AND status = 'SUCCESS'",
        {"source": source},
    )
    last_run = rows[0]["last_run"] if rows else None
    if last_run is None:
        default = datetime.now(timezone.utc) - timedelta(days=DEFAULT_WATERMARK_DAYS)
        logger.info("No watermark for %s; defaulting to %s", source, default)
        return default
    return last_run


def log_pipeline_run(run_id: str, status: str, row_counts: dict[str, int]) -> None:
    """Write one pipeline_run_log row per entry; runs even on partial failure."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    rows = [
        {
            "run_id": run_id,
            "source": source,
            "status": status,
            "rows_written": rows_count,
            "started_at": now,
            "ended_at": now,
        }
        for source, rows_count in row_counts.items()
    ]
    inserted = insert_rows("pipeline_run_log", rows)
    if inserted != len(rows):
        raise RuntimeError(f"pipeline_run_log insert failed: wrote {inserted}/{len(rows)} rows")
    logger.info("Logged run %s status %s: %s", run_id, status, row_counts)


def cleanup_raw_tables(retention_days: int = 30) -> dict[str, int]:
    """Delete raw_* rows older than the window; reject retention_days <= 0."""
    if retention_days <= 0:
        raise ValueError(f"retention_days must be positive; got {retention_days}")
    template = Path(__file__).with_name("cleanup_raw_tables.sql").read_text(encoding="utf-8")
    deleted: dict[str, int] = {}
    for source in ("greenhouse", "lever", "rippling", "adzuna"):
        table = f"raw_{source}"
        affected = run_sql(template.format(table=table, retention_days=retention_days))
        deleted[table] = affected
        logger.info("Deleted %d rows from %s", affected, table)
    return deleted


def archive_stale_postings(retention_days: int = 7) -> dict[str, int]:
    """Archive and purge stale postings from database into compressed cold-storage archive."""
    if retention_days <= 0:
        raise ValueError(f"retention_days must be positive; got {retention_days}")

    from orchestration.archive_encoder import encode_and_purge_outdated_postings

    res = encode_and_purge_outdated_postings(retention_days=retention_days)
    archived_count = res.get("encoded_count", 0)
    deleted_count = res.get("purged_count", 0)
    logger.info("Archived (encoded) %d and purged %d stale postings from database", archived_count, deleted_count)
    return {"archived": archived_count, "deleted": deleted_count}


def _company_configs() -> list[dict]:
    config_path = Path(__file__).parents[1] / "config" / "companies.yaml"
    with open(config_path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("companies", []) or []


def _fetch_source(source: str) -> list[dict]:
    load_dotenv()
    companies = _company_configs()
    if source == "adzuna":
        query = os.getenv("ADZUNA_QUERY")
        country = os.getenv("ADZUNA_COUNTRY")
        pages = int(os.getenv("ADZUNA_PAGES", "1"))
        if not query or not country:
            raise RuntimeError("ADZUNA_QUERY and ADZUNA_COUNTRY must be set in .env")
        results: list[dict] = []
        for page in range(1, pages + 1):
            page_results = fetch_adzuna_jobs(query, country, page)
            results.extend(page_results)
            if len(page_results) < RESULTS_PER_PAGE:
                break
        return results
    if source == "greenhouse":
        config_companies = [c for c in companies if c.get("greenhouse_board_token")]
        if config_companies:
            results = []
            for entry in config_companies:
                for job in fetch_greenhouse_jobs(entry["greenhouse_board_token"]):
                    results.append({
                        **job,
                        "company_display_name": entry.get("display_name") or "Unknown",
                    })
            return results
        token = os.getenv("GREENHOUSE_BOARD_TOKEN")
        if not token:
            raise RuntimeError("GREENHOUSE_BOARD_TOKEN must be set in .env")
        jobs = fetch_greenhouse_jobs(token)
        return [{**job, "company_display_name": "Unknown"} for job in jobs]
    if source == "lever":
        results = []
        for entry in companies:
            slug = entry.get("lever_company_slug")
            if not slug:
                continue
            for posting in fetch_lever_jobs(slug):
                results.append({
                    **posting,
                    "company_display_name": entry.get("display_name")
                    or posting.get("company")
                    or "Unknown",
                })
        return results
    if source == "rippling":
        results = []
        for entry in companies:
            slug = entry.get("rippling_board_slug")
            if not slug:
                continue
            for job in fetch_rippling_jobs(slug):
                results.append({
                    **job,
                    "company_display_name": entry.get("display_name") or "Unknown",
                })
        return results
    raise ValueError(f"Unknown source {source!r}")


def _run_staging() -> None:
    for sql_file in sorted(STAGING_SQL_DIR.glob("*.sql")):
        run_sql_script(sql_file.read_text(encoding="utf-8"))
        logger.info("Executed %s", sql_file.name)


def main() -> None:
    """Run the full pipeline once; second concurrent invocation exits cleanly."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("databricks.sql").setLevel(logging.WARNING)
    if not _acquire_lock():
        logger.warning("ALREADY_RUNNING: another pipeline run is in progress")
        return
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    source_statuses: dict[str, str] = {}
    row_counts: dict[str, int] = {}
    try:
        for source in SOURCES:
            try:
                logger.info("Starting source %s", source)
                payload = _fetch_source(source)
                row_counts[source] = write_to_bigquery_raw(source, payload, run_id)
                source_statuses[source] = "SUCCESS"
                logger.info("Finished source %s: %d rows", source, row_counts[source])
            except Exception as exc:  # noqa: BLE001 - one source must not stop the rest
                logger.error("Source %s failed: %s", source, exc)
                row_counts[source] = 0
                source_statuses[source] = "FAILED"
        for source in SOURCES:
            try:
                log_pipeline_run(run_id, source_statuses[source], {source: row_counts[source]})
            except Exception as exc:  # noqa: BLE001
                logger.error("Failed to log source %s: %s", source, exc)
        succeeded = [s for s in SOURCES if source_statuses[s] == "SUCCESS"]
        if not succeeded:
            overall = "FAILED"
            logger.error("All sources failed; skipping downstream stages")
        else:
            try:
                logger.info("Starting staging")
                _run_staging()
                logger.info("Starting data-quality checks")
                run_data_quality_checks(run_id)
                logger.info("Starting warehouse loads")
                load_dim_company()
                load_fact_job_posting()
                load_user_profile()
                logger.info("Starting mart refresh")
                refresh_mart_views()
                logger.info("Starting archive retention")
                archive_res = archive_stale_postings(retention_days=7)
                log_pipeline_run(run_id, "SUCCESS", {"ARCHIVE": archive_res["archived"]})
                overall = "SUCCESS" if len(succeeded) == len(SOURCES) else "PARTIAL"
            except Exception as exc:  # noqa: BLE001
                logger.error("Downstream stages failed: %s", exc)
                overall = "FAILED"
        try:
            log_pipeline_run(run_id, overall, {"OVERALL": sum(row_counts.values())})
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to log overall run: %s", exc)
        logger.info("Run %s finished with status %s", run_id, overall)
    finally:
        _release_lock()


if __name__ == "__main__":
    main()
