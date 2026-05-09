import logging
from datetime import date, timedelta

import database
import pipeline

log = logging.getLogger(__name__)


async def _send_digest(bot, user_id: int, since: str, period_label: str):
    entries = database.get_entries_since(user_id, since)
    if not entries:
        return
    text = await pipeline.summarize_entries(entries, period_label)
    if not text:
        return
    header = f"Your {period_label.title()} ({since} — {date.today()})\n\n"
    await bot.send_message(user_id, header + text)


async def send_weekly_digest(bot):
    since = (date.today() - timedelta(days=7)).isoformat()
    for user_id in database.get_active_users():
        try:
            await _send_digest(bot, user_id, since, "weekly digest")
        except Exception:
            log.exception("Weekly digest failed for user %s", user_id)


async def send_quarterly_review(bot):
    since = (date.today() - timedelta(days=91)).isoformat()
    for user_id in database.get_active_users():
        try:
            await _send_digest(bot, user_id, since, "quarterly review")
        except Exception:
            log.exception("Quarterly review failed for user %s", user_id)
