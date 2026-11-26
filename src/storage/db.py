"""
storage/db.py
=============
Lightweight SQLite connection manager with schema migrations.
Use as a context manager::

    with DB() as db:
        db.execute("SELECT ...")
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from config.settings import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Schema (DDL)
# ---------------------------------------------------------------------------

_MIGRATIONS = [
    # v1 – initial schema
    """
    CREATE TABLE IF NOT EXISTS schema_version (
        version INTEGER PRIMARY KEY
    );

    CREATE TABLE IF NOT EXISTS habits (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        habit_name  TEXT    NOT NULL,
        log_date    TEXT    NOT NULL,          -- ISO date YYYY-MM-DD
        notes       TEXT    NOT NULL DEFAULT '',
        created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
    );
    CREATE UNIQUE INDEX IF NOT EXISTS idx_habits_name_date
        ON habits (habit_name, log_date);

    CREATE TABLE IF NOT EXISTS timers (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        label       TEXT    NOT NULL,
        minutes     INTEGER NOT NULL,
        started_at  TEXT    NOT NULL DEFAULT (datetime('now')),
        completed   INTEGER NOT NULL DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS file_moves (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        src_path    TEXT    NOT NULL,
        dst_path    TEXT    NOT NULL,
        moved_at    TEXT    NOT NULL DEFAULT (datetime('now'))
    );
    """,
]


# ---------------------------------------------------------------------------
# DB class
# ---------------------------------------------------------------------------


class DB:
    """
    Thread-safe SQLite context manager.

    Attributes
    ----------
    conn : sqlite3.Connection
        The underlying connection (available inside the ``with`` block).
    """

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or settings.db_path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self.conn: sqlite3.Connection | None = None

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self) -> "DB":
        self.conn = sqlite3.connect(str(self._path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL;")
        self.conn.execute("PRAGMA foreign_keys=ON;")
        self._run_migrations()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        if self.conn:
            if exc_type is None:
                self.conn.commit()
            else:
                self.conn.rollback()
            self.conn.close()
            self.conn = None
        return False   # do not suppress exceptions

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        if self.conn is None:
            raise RuntimeError("DB not connected – use inside a 'with DB()' block.")
        return self.conn.execute(sql, params)

    def executemany(self, sql: str, params_seq) -> sqlite3.Cursor:
        if self.conn is None:
            raise RuntimeError("DB not connected.")
        return self.conn.executemany(sql, params_seq)

    # ------------------------------------------------------------------
    # Migrations
    # ------------------------------------------------------------------

    def _run_migrations(self) -> None:
        assert self.conn is not None
        # Determine current version
        try:
            row = self.conn.execute(
                "SELECT MAX(version) AS v FROM schema_version"
            ).fetchone()
            current = row["v"] if row["v"] is not None else -1
        except sqlite3.OperationalError:
            current = -1

        for idx, ddl in enumerate(_MIGRATIONS):
            if idx > current:
                logger.info("DB: applying migration v%d", idx)
                self.conn.executescript(ddl)
                self.conn.execute(
                    "INSERT OR REPLACE INTO schema_version (version) VALUES (?)", (idx,)
                )
                self.conn.commit()

        logger.debug("DB: schema up to date (v%d)", len(_MIGRATIONS) - 1)
