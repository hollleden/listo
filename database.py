import os
import secrets
from collections import Counter
from datetime import date, timedelta

import httpx

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_KEY"]

_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}


def _url(table: str) -> str:
    return f"{SUPABASE_URL}/rest/v1/{table}"


def _h(**extra):
    return {**_HEADERS, **extra}


def init_db():
    pass  # Tables managed via Supabase SQL Editor


# ── entries ───────────────────────────────────────────────────────────────────

def save_entry(user_id, media_type, raw_content, summary, tags, folder,
               fact_check, enrichment, title="",
               tg_message_link="", formatted_output=""):
    with httpx.Client() as c:
        r = c.post(_url("entries"), json={
            "user_id": user_id, "created_at": str(date.today()),
            "media_type": media_type, "raw_content": raw_content,
            "summary": summary, "tags": tags, "folder": folder,
            "fact_check": fact_check, "enrichment": enrichment, "title": title,
            "tg_message_link": tg_message_link, "formatted_output": formatted_output,
        }, headers=_h())
        r.raise_for_status()


def get_today_count(user_id: int) -> int:
    with httpx.Client() as c:
        r = c.get(_url("entries"), params={
            "select": "id", "user_id": f"eq.{user_id}",
            "created_at": f"eq.{date.today()}",
        }, headers=_h(Prefer="count=exact"))
        cr = r.headers.get("content-range", "*/0")
        return int(cr.split("/")[-1]) if "/" in cr else 0


def get_entries_since(user_id: int, since_date: str) -> list[dict]:
    with httpx.Client() as c:
        r = c.get(_url("entries"), params={
            "select": "created_at,media_type,summary,tags,folder,fact_check,enrichment",
            "user_id": f"eq.{user_id}", "created_at": f"gte.{since_date}",
            "order": "created_at.asc",
        }, headers=_h())
        r.raise_for_status()
        return r.json()


def get_active_users() -> list[int]:
    with httpx.Client() as c:
        r = c.get(_url("entries"), params={"select": "user_id"}, headers=_h())
        r.raise_for_status()
        return list({row["user_id"] for row in r.json()})


def get_recent_entries(user_id: int, limit: int = 10) -> list[dict]:
    with httpx.Client() as c:
        r = c.get(_url("entries"), params={
            "select": "id,created_at,folder,summary,media_type",
            "user_id": f"eq.{user_id}",
            "order": "created_at.desc,id.desc", "limit": limit,
        }, headers=_h())
        r.raise_for_status()
        return r.json()


def search_entries(user_id: int, query: str, limit: int = 5) -> list[dict]:
    q = query.replace("*", "").replace("(", "").replace(")", "")
    with httpx.Client() as c:
        r = c.get(_url("entries"), params={
            "select": "id,created_at,folder,summary,media_type",
            "user_id": f"eq.{user_id}",
            "or": f"(summary.ilike.*{q}*,tags.ilike.*{q}*,raw_content.ilike.*{q}*)",
            "order": "created_at.desc,id.desc", "limit": limit,
        }, headers=_h())
        r.raise_for_status()
        return r.json()


def delete_entry(entry_id: int, user_id: int) -> bool:
    with httpx.Client() as c:
        r = c.delete(_url("entries"), params={
            "id": f"eq.{entry_id}", "user_id": f"eq.{user_id}",
        }, headers=_h())
        r.raise_for_status()
        return r.status_code in (200, 204)


def get_entry_public(entry_id: int) -> dict | None:
    with httpx.Client() as c:
        r = c.get(_url("entries"), params={
            "select": "id,title,summary,tags,folder,created_at,formatted_output",
            "id": f"eq.{entry_id}", "limit": 1,
        }, headers=_h())
        r.raise_for_status()
        rows = r.json()
    return rows[0] if rows else None


# ── users / tokens ────────────────────────────────────────────────────────────

def ensure_user_token(user_id: int) -> str:
    with httpx.Client() as c:
        r = c.get(_url("users"), params={
            "user_id": f"eq.{user_id}", "select": "token",
        }, headers=_h())
        r.raise_for_status()
        rows = r.json()
        if rows:
            return rows[0]["token"]
        token = secrets.token_urlsafe(8)
        r2 = c.post(_url("users"), json={
            "user_id": user_id, "token": token,
        }, headers=_h(Prefer="return=representation"))
        r2.raise_for_status()
        return token


def upsert_user_profile(user_id: int, first_name: str, username: str) -> str:
    with httpx.Client() as c:
        # Check if user exists
        r = c.get(_url("users"), params={
            "user_id": f"eq.{user_id}", "select": "token",
        }, headers=_h())
        r.raise_for_status()
        rows = r.json()
        if rows:
            token = rows[0]["token"]
            # Update profile fields
            c.patch(_url("users"), params={"user_id": f"eq.{user_id}"}, json={
                "first_name": first_name, "username": username,
            }, headers=_h()).raise_for_status()
            return token
        # Insert new user
        token = secrets.token_urlsafe(8)
        c.post(_url("users"), json={
            "user_id": user_id, "token": token,
            "first_name": first_name, "username": username,
        }, headers=_h(Prefer="return=representation")).raise_for_status()
        return token


def update_avatar(user_id: int, avatar_url: str) -> None:
    with httpx.Client() as c:
        c.patch(_url("users"), params={"user_id": f"eq.{user_id}"}, json={
            "avatar_url": avatar_url,
        }, headers=_h()).raise_for_status()


def get_user_by_token(token: str):
    with httpx.Client() as c:
        r = c.get(_url("users"), params={
            "token": f"eq.{token}", "select": "user_id",
        }, headers=_h())
        r.raise_for_status()
        rows = r.json()
    return rows[0]["user_id"] if rows else None


def get_user_profile(token: str) -> dict | None:
    with httpx.Client() as c:
        r = c.get(_url("users"), params={
            "token": f"eq.{token}",
            "select": "user_id,first_name,username,avatar_url,token",
            "limit": 1,
        }, headers=_h())
        r.raise_for_status()
        rows = r.json()
        if not rows:
            return None
        user = rows[0]
        user_id = user["user_id"]

        rt = c.get(_url("entries"), params={
            "select": "id", "user_id": f"eq.{user_id}",
        }, headers=_h(Prefer="count=exact"))
        total = int(rt.headers.get("content-range", "*/0").split("/")[-1])

        rf = c.get(_url("entries"), params={
            "select": "created_at", "user_id": f"eq.{user_id}",
            "order": "created_at.asc", "limit": 1,
        }, headers=_h())
        first_rows = rf.json()
        first_save_date = first_rows[0]["created_at"] if first_rows else ""

    return {
        "user_id":        user_id,
        "first_name":     user.get("first_name") or "",
        "username":       user.get("username") or "",
        "avatar_url":     user.get("avatar_url") or "",
        "token":          user["token"],
        "first_save_date": first_save_date,
        "total_saves":    total,
    }


# ── web API queries ───────────────────────────────────────────────────────────

def get_entries_web(user_id, folder=None, query=None, limit=20, offset=0) -> list[dict]:
    params = {
        "select": "id,title,summary,tags,folder,created_at,tg_message_link,formatted_output",
        "user_id": f"eq.{user_id}", "order": "created_at.desc",
        "limit": limit, "offset": offset,
    }
    if folder and folder != "All":
        params["folder"] = f"eq.{folder}"
    if query:
        q = query.replace("*", "")
        params["or"] = f"(summary.ilike.*{q}*,tags.ilike.*{q}*,raw_content.ilike.*{q}*)"
    with httpx.Client() as c:
        r = c.get(_url("entries"), params=params, headers=_h())
        r.raise_for_status()
        return r.json()


def get_web_stats(user_id: int) -> dict:
    week_ago = str(date.today() - timedelta(days=7))
    with httpx.Client() as c:
        rt = c.get(_url("entries"), params={
            "select": "id", "user_id": f"eq.{user_id}",
        }, headers=_h(Prefer="count=exact"))
        total = int(rt.headers.get("content-range", "*/0").split("/")[-1])

        rw = c.get(_url("entries"), params={
            "select": "id", "user_id": f"eq.{user_id}",
            "created_at": f"gte.{week_ago}",
        }, headers=_h(Prefer="count=exact"))
        this_week = int(rw.headers.get("content-range", "*/0").split("/")[-1])

        rf = c.get(_url("entries"), params={
            "select": "folder", "user_id": f"eq.{user_id}",
        }, headers=_h())
        counts = Counter(row["folder"] for row in rf.json() if row.get("folder"))
        top_folder = counts.most_common(1)[0][0] if counts else "None"

    return {"total": total, "this_week": this_week, "top_folder": top_folder}


def save_entry(user_id, media_type, raw_content, summary, tags, folder,
               fact_check, enrichment, title="", message_id=None,
               formatted_output=None):  # ← add this
    payload = {
        "user_id": user_id, "created_at": str(date.today()),
        "media_type": media_type, "raw_content": raw_content,
        "summary": summary, "tags": tags, "folder": folder,
        "fact_check": fact_check, "enrichment": enrichment, "title": title,
    }
    if message_id:
        payload["message_id"] = message_id
    if formatted_output:
        payload["formatted_output"] = formatted_output  # ← add this
    with httpx.Client() as c:
        r = c.post(_url("entries"), json=payload, headers=_h())
        r.raise_for_status()
