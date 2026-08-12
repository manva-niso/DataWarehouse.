"""Mart refresh for Job Market Pulse.

Recreates every mart view atomically per view by executing the numbered SQL
files under marts/. Dashboard and Excel export read these views only.
"""

import logging
from pathlib import Path

from dbio import run_sql_script

logger = logging.getLogger(__name__)

MARTS_SQL_DIR = Path(__file__).parent


def refresh_mart_views() -> None:
    """Recreate each mart view atomically by running its SQL file."""
    sql_files = sorted(MARTS_SQL_DIR.glob("*.sql"))
    if not sql_files:
        logger.info("No mart SQL files found")
        return
    for sql_file in sql_files:
        run_sql_script(sql_file.read_text(encoding="utf-8"))
        logger.info("Refreshed mart view from %s", sql_file.name)
