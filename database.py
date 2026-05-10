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
                enrichment  TEXT,
                title       TEXT
            )
        """)
        try:
            conn.execute("ALTER TABLE entries ADD COLUMN title TEXT")
        except Exception:
            pass  # column already exists
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
    title: str = "",
):
    with _conn() as conn:
        conn.execute(
            """INSERT INTO entries
               (user_id, created_at, media_type, raw_content, summary, tags, folder, fact_check, enrichment, title)
               VALUES (?, date('now'), ?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_id, media_type, raw_content, summary, tags, folder, fact_check, enrichment, title),
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


def get_recent_entries(user_id: int, limit: int = 10) -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            """SELECT id, created_at, folder, summary, media_type
               FROM entries WHERE user_id = ?
               ORDER BY created_at DESC, id DESC LIMIT ?""",
            (user_id, limit),
        ).fetchall()
    keys = ["id", "created_at", "folder", "summary", "media_type"]
    return [dict(zip(keys, row)) for row in rows]


def search_entries(user_id: int, query: str, limit: int = 5) -> list[dict]:
    pattern = f"%{query}%"
    with _conn() as conn:
        rows = conn.execute(
            """SELECT id, created_at, folder, summary, media_type
               FROM entries
               WHERE user_id = ?
                 AND (summary LIKE ? OR tags LIKE ? OR raw_content LIKE ?)
               ORDER BY created_at DESC, id DESC LIMIT ?""",
            (user_id, pattern, pattern, pattern, limit),
        ).fetchall()
    keys = ["id", "created_at", "folder", "summary", "media_type"]
    return [dict(zip(keys, row)) for row in rows]


def delete_entry(entry_id: int, user_id: int) -> bool:
    with _conn() as conn:
        cur = conn.execute(
            "DELETE FROM entries WHERE id = ? AND user_id = ?",
            (entry_id, user_id),
        )
        conn.commit()
    return cur.rowcount > 0


# ---------------------------------------------------------------------------
# Users / token management
# ---------------------------------------------------------------------------

_USERS_DDL = """
    CREATE TABLE IF NOT EXISTS users (
        user_id    INTEGER PRIMARY KEY,
        token      TEXT UNIQUE NOT NULL,
        created_at TEXT DEFAULT (date('now'))
    )
"""


def ensure_user_token(user_id: int) -> str:
    import secrets
    with _conn() as conn:
        conn.execute(_USERS_DDL)
        conn.commit()
        row = conn.execute(
            "SELECT token FROM users WHERE user_id = ?", (user_id,)
        ).fetchone()
        if row:
            return row[0]
        token = secrets.token_urlsafe(8)
        conn.execute(
            "INSERT INTO users (user_id, token) VALUES (?, ?)", (user_id, token)
        )
        conn.commit()
        return token


def get_user_by_token(token: str):
    with _conn() as conn:
        conn.execute(_USERS_DDL)
        row = conn.execute(
            "SELECT user_id FROM users WHERE token = ?", (token,)
        ).fetchone()
    return row[0] if row else None


# ---------------------------------------------------------------------------
# Web API queries
# ---------------------------------------------------------------------------

def get_entries_web(
    user_id: int,
    folder: str = None,
    query: str = None,
    limit: int = 100,
) -> list[dict]:
    sql = "SELECT id, title, summary, tags, folder, created_at FROM entries WHERE user_id = ?"
    params: list = [user_id]
    if folder and folder != "All":
        sql += " AND folder = ?"
        params.append(folder)
    if query:
        sql += " AND (summary LIKE ? OR tags LIKE ? OR raw_content LIKE ?)"
        q = f"%{query}%"
        params.extend([q, q, q])
    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    with _conn() as conn:
        rows = conn.execute(sql, params).fetchall()
    keys = ["id", "title", "summary", "tags", "folder", "created_at"]
    return [dict(zip(keys, row)) for row in rows]


def get_web_stats(user_id: int) -> dict:
    with _conn() as conn:
        total = conn.execute(
            "SELECT COUNT(*) FROM entries WHERE user_id = ?", (user_id,)
        ).fetchone()[0]
        this_week = conn.execute(
            "SELECT COUNT(*) FROM entries WHERE user_id = ? AND created_at >= date('now', '-7 days')",
            (user_id,),
        ).fetchone()[0]
        top_row = conn.execute(
            "SELECT folder, COUNT(*) AS c FROM entries WHERE user_id = ? GROUP BY folder ORDER BY c DESC LIMIT 1",
            (user_id,),
        ).fetchone()
        top_folder = top_row[0] if top_row else "None"
    return {"total": total, "this_week": this_week, "top_folder": top_folder}
