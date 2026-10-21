"""SQLite storage. Every query is parameterized (no string-built SQL)."""
import logging
import os
import sqlite3
from contextlib import contextmanager

log = logging.getLogger("copilot.db")
DB_PATH = os.environ.get("DB_PATH", "data/copilot.db")


class DuplicateOpportunityError(ValueError):
    """Raised when an opportunity with the same title and organization exists."""


@contextmanager
def _conn():
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    finally:
        con.close()


def init_db() -> None:
    with _conn() as con:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS opportunities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                organization TEXT NOT NULL,
                category TEXT NOT NULL,
                deadline TEXT NOT NULL DEFAULT '',
                url TEXT NOT NULL DEFAULT '',
                description TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'saved',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (title, organization)
            )
            """
        )


def insert_opportunity(title, organization, category, deadline, url, description) -> int:
    try:
        with _conn() as con:
            cur = con.execute(
                "INSERT INTO opportunities (title, organization, category, deadline, url, description) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (title, organization, category, deadline, url, description),
            )
            return cur.lastrowid
    except sqlite3.IntegrityError:
        raise DuplicateOpportunityError(f"'{title}' at {organization} is already saved.")
    except sqlite3.Error:
        log.exception("database error while saving")
        raise RuntimeError("Database error while saving. Please try again.")


def fetch_opportunities(status: str, category: str, limit: int) -> list[dict]:
    query = "SELECT * FROM opportunities WHERE 1=1"
    params: list = []
    if status:
        query += " AND status = ?"
        params.append(status)
    if category:
        query += " AND category = ?"
        params.append(category)
    query += " ORDER BY CASE WHEN deadline = '' THEN 1 ELSE 0 END, deadline ASC LIMIT ?"
    params.append(limit)
    try:
        with _conn() as con:
            return [dict(r) for r in con.execute(query, params).fetchall()]
    except sqlite3.Error:
        log.exception("database error while listing")
        raise RuntimeError("Database error while listing. Please try again.")