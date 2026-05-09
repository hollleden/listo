import os
import sqlite3
from datetime import date

DB_PATH = os.getenv("DB_PATH", "listo.db")


def _conn():
    return sqlite3.connect(DB_PATH)


def init_db():
    with _conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS entries (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                created_at  TEXT    NOT NULL DEFAULT (date('now')),
                media_type  TEXT,
                raw_content TEXT,
                summary     TEXT,
                tags        TEXT,
                folder      TEXT,
                fact_check  TEXT,
                enrichment  TEXT
            )
        """)
        conn.commit()


def save_entry(
    user_id: int,
    media_type: str,
    raw_content: str,
    summary: str,
    tags: str,
    folder: str,
    fact_check: str,
    enrichment: str,
):
    with _conn() as conn:
        conn.execute(
            """INSERT INTO entries
               (user_id, created_at, media_type, raw_content, summary, tags, folder, fact_check, enrichment)
               VALUES (?, date('now'), ?, ?, ?, ?, ?, ?, ?)""",
            (user_id, media_type, raw_content, summary, tags, folder, fact_check, enrichment),
        )
        conn.commit()


def get_today_count(user_id: int) -> int:
    with _conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) FROM entries WHERE user_id = ? AND created_at = date('now')",
            (user_id,),
        ).fetchone()
        return row[0] if row else 0


def get_entries_since(user_id: int, since_date: str) -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            """SELECT created_at, media_type, summary, tags, folder, fact_check, enrichment
               FROM entries
               WHERE user_id = ? AND created_at >= ?
               ORDER BY created_at""",
            (user_id, since_date),
        ).fetchall()
    keys = ["created_at", "media_type", "summary", "tags", "folder", "fact_check", "enrichment"]
    return [dict(zip(keys, row)) for row in rows]


def get_active_users() -> list[int]:
    with _conn() as conn:
        rows = conn.execute("SELECT DISTINCT user_id FROM entries").fetchall()
    return [row[0] for row in rows]
