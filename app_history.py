"""
app_history.py
--------------
SQLite-backed run history for PrepKit.

Every script generation and run is logged as a row so users can:
  - Re-download any previously generated script
  - Restore template + parameters into Tab 2 ("re-load")
  - View a timeline of what they built and when

DB location: prepkit_history.db next to gradio_app.py (auto-created on first use).
"""
from __future__ import annotations

import sqlite3
import datetime
from pathlib import Path

import pandas as pd

DB_PATH = Path(__file__).resolve().parent / "prepkit_history.db"

_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS runs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp       TEXT    NOT NULL,
    template_name   TEXT    NOT NULL,
    display_name    TEXT    NOT NULL,
    params_json     TEXT    NOT NULL,
    script_name     TEXT    NOT NULL,
    action          TEXT    NOT NULL,   -- 'generate' | 'run'
    status          TEXT    NOT NULL,   -- 'ok' | 'error'
    output_summary  TEXT    DEFAULT '',
    script_content  TEXT    DEFAULT ''
)
"""


def init_db() -> None:
    """Create the DB and table if they don't exist yet. Safe to call repeatedly."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(_CREATE_SQL)
        conn.commit()


def log_run(
    *,
    template_name: str,
    display_name: str,
    params_json: str,
    script_name: str,
    action: str,
    status: str,
    output_summary: str = "",
    script_content: str = "",
) -> int:
    """
    Insert a history entry.

    Parameters
    ----------
    template_name   : internal key e.g. 'file_join_two'
    display_name    : human label e.g. 'PS-03 — Join Two Files'
    params_json     : serialized parameters JSON string
    script_name     : generated script filename
    action          : 'generate' or 'run'
    status          : 'ok' or 'error'
    output_summary  : short text shown in the history table
    script_content  : full text of the generated script (stored for re-download)

    Returns the new row id.
    """
    init_db()
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute(
            """
            INSERT INTO runs
                (timestamp, template_name, display_name, params_json,
                 script_name, action, status, output_summary, script_content)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ts, template_name, display_name, params_json,
                script_name, action, status, output_summary, script_content,
            ),
        )
        conn.commit()
        return cur.lastrowid


def get_history(limit: int = 100) -> list[dict]:
    """Return the last *limit* runs, newest first."""
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM runs ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def get_run(run_id: int) -> dict | None:
    """Fetch a single run by id. Returns None if not found."""
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM runs WHERE id = ?", (run_id,)
        ).fetchone()
    return dict(row) if row else None


def delete_run(run_id: int) -> None:
    """Remove a single history entry."""
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM runs WHERE id = ?", (run_id,))
        conn.commit()


def clear_history() -> None:
    """Delete all history rows."""
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM runs")
        conn.commit()


def history_dataframe(limit: int = 100) -> pd.DataFrame:
    """
    Return history as a DataFrame ready for gr.Dataframe display.
    Columns: ID | Time | Action | Template | Script | Status | Summary
    """
    rows = get_history(limit)
    if not rows:
        return pd.DataFrame(
            columns=["ID", "Time", "Action", "Template", "Script", "Status", "Summary"]
        )
    data = [
        [
            r["id"],
            r["timestamp"],
            r["action"],
            r["display_name"],
            r["script_name"],
            r["status"],
            r["output_summary"],
        ]
        for r in rows
    ]
    return pd.DataFrame(
        data,
        columns=["ID", "Time", "Action", "Template", "Script", "Status", "Summary"],
    )
