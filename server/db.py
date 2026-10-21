"""SQLite storage. Every query is parameterized (no string-built SQL)."""
import logging
import os
import sqlite3
from contextlib import contextmanager
from datetime import date, timedelta

from server.errors import InputError

log = logging.getLogger("copilot.db")
DB_PATH = os.environ.get("DB_PATH", "data/copilot.db")
STATUS_ORDER = ["saved", "applied", "interview", "accepted", "rejected"]


@contextmanager
def _conn():
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    except sqlite3.IntegrityError:
        raise
    except sqlite3.Error:
        log.exception("database error")
        raise InputError("Database error. Please try again.")
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
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS status_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                opportunity_id INTEGER NOT NULL,
                status TEXT NOT NULL,
                changed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
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
            con.execute(
                "INSERT INTO status_history (opportunity_id, status) VALUES (?, 'saved')",
                (cur.lastrowid,),
            )
            return cur.lastrowid
    except sqlite3.IntegrityError:
        raise InputError(f"'{title}' at {organization} is already saved.")


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
    with _conn() as con:
        return [dict(r) for r in con.execute(query, params).fetchall()]


def get_opportunity(opp_id: int) -> dict:
    with _conn() as con:
        row = con.execute("SELECT * FROM opportunities WHERE id = ?", (opp_id,)).fetchone()
    if row is None:
        raise InputError(
            f"No saved opportunity with id {opp_id}. Use list_saved_opportunities to see the ids."
        )
    return dict(row)


def set_status(opp_id: int, status: str) -> str:
    """Change the status and record it in the history. Returns the old status."""
    with _conn() as con:
        row = con.execute("SELECT status FROM opportunities WHERE id = ?", (opp_id,)).fetchone()
        if row is None:
            raise InputError(
                f"No saved opportunity with id {opp_id}. Use list_saved_opportunities to see the ids."
            )
        old = row["status"]
        if old == status:
            raise InputError(f"Opportunity #{opp_id} already has the status '{status}'.")
        con.execute("UPDATE opportunities SET status = ? WHERE id = ?", (status, opp_id))
        con.execute(
            "INSERT INTO status_history (opportunity_id, status) VALUES (?, ?)", (opp_id, status)
        )
    return old


def status_counts() -> dict[str, int]:
    counts = {s: 0 for s in STATUS_ORDER}
    with _conn() as con:
        for r in con.execute("SELECT status, COUNT(*) AS n FROM opportunities GROUP BY status"):
            counts[r["status"]] = r["n"]
    return counts


def category_counts() -> dict[str, int]:
    with _conn() as con:
        rows = con.execute(
            "SELECT category, COUNT(*) AS n FROM opportunities GROUP BY category ORDER BY n DESC"
        ).fetchall()
    return {r["category"]: r["n"] for r in rows}


def upcoming(days: int) -> list[dict]:
    """Saved (not yet applied) opportunities whose deadline falls in the next N days."""
    today = date.today()
    end = today + timedelta(days=days)
    with _conn() as con:
        rows = con.execute(
            "SELECT * FROM opportunities WHERE status = 'saved' AND deadline != '' "
            "AND deadline BETWEEN ? AND ? ORDER BY deadline ASC",
            (today.isoformat(), end.isoformat()),
        ).fetchall()
    return [dict(r) for r in rows]