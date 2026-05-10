import asyncio
import html
import logging
import os

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, ErrorEvent
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv

import database
import pipeline
from digest import send_weekly_digest, send_quarterly_review

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
DAILY_LIMIT = 20

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Media group accumulator
_mg_buffer: dict[str, list[tuple[bytes, str]]] = {}   # group_id -> [(bytes, mime)]
_mg_meta: dict[str, dict] = {}                         # group_id -> {user_id, message, caption}
_mg_tasks: dict[str, asyncio.Task] = {}                # group_id -> timer task

HTML = "HTML"

IGNORE_PHRASES = [
    "Рад был помочь",
    "Спасибо, что пользуетесь",
    "@SaveAsBot",
    "SaveAsBot",
]


def _should_ignore(message: Message) -> bool:
    text = message.text or message.caption or ""
    return any(phrase in text for phrase in IGNORE_PHRASES)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_admin(user_id: int) -> bool:
    return ADMIN_ID != 0 and user_id == ADMIN_ID


async def _can_save(user_id: int) -> bool:
    if _is_admin(user_id):
        return True
    return database.get_today_count(user_id) < DAILY_LIMIT


def _limit_message() -> str:
    return (
        f"You've reached your daily limit of {DAILY_LIMIT} saves. "
        "Upgrade to Listo Pro for unlimited saves and priority processing!"
    )


async def _safe_delete(msg) -> None:
    try:
        await msg.delete()
    except Exception:
        pass


async def _send_long(message: Message, text: str) -> None:
    """Send text, splitting into chunks if it exceeds Telegram's 4096-char limit."""
    MAX = 4000
    if len(text) <= MAX:
        await message.answer(text, parse_mode=HTML)
        return
    lines = text.split("\n")
    chunk_lines: list[str] = []
    chunk_len = 0
    for line in lines:
        line_cost = len(line) + 1
        if chunk_len + line_cost > MAX and chunk_lines:
            await message.answer("\n".join(chunk_lines), parse_mode=HTML)
            chunk_lines = [line]
            chunk_len = line_cost
        else:
            chunk_lines.append(line)
            chunk_len += line_cost
    if chunk_lines:
        await message.answer("\n".join(chunk_lines), parse_mode=HTML)


async def _get_image_bytes(message: Message) -> tuple[str, str]:
    """Returns (file_id, mime_type)."""
    if message.photo:
        return message.photo[-1].file_id, "image/jpeg"
    mime = message.document.mime_type or "image/jpeg"
    return message.document.file_id, mime


async def _download(file_id: str) -> bytes:
    file = await bot.get_file(file_id)
    buf = await bot.download_file(file.file_path)
    return buf.read()


async def _reply_result(message: Message, result: dict, media_type: str):
    user_id = message.from_user.id
    fields = pipeline.extract_db_fields(result)
    database.save_entry(
        user_id=user_id,
        media_type=media_type,
        raw_content=result.get("raw_content", ""),
        summary=fields["summary"],
        tags=fields["tags"],
        folder=fields["folder"],
        fact_check=fields["fact_check"],
        enrichment=fields["enrichment"],
    )
    await _send_long(message, pipeline.format_result(result))


# ---------------------------------------------------------------------------
# Media group timer
# ---------------------------------------------------------------------------

async def _flush_media_group(group_id: str):
    await asyncio.sleep(0.8)  # wait for remaining group messages to arrive

    images = _mg_buffer.pop(group_id, [])
    meta = _mg_meta.pop(group_id, {})
    _mg_tasks.pop(group_id, None)

    if not images:
        return

    user_id = meta["user_id"]
    message: Message = meta["message"]

    if not await _can_save(user_id):
        await message.answer(_limit_message(), parse_mode=HTML)
        return

    status = await message.answer("Analyzing your images...", parse_mode=HTML)
    try:
        result = await pipeline.process_images(images, "")
        await _safe_delete(status)
        await _reply_result(message, result, "image_group")
    except Exception:
        await _safe_delete(status)
        await message.answer("Something went wrong while analyzing your images. Please try again.", parse_mode=HTML)
        log.exception("Media group processing failed")


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "Welcome to Listo!\n\n"
        "Send me a photo (or a group of photos) and I'll extract text, summarize, tag, "
        "fact-check, and file it for you.\n"
        "Send a text message and I'll analyze and save it the same way.\n\n"
        f"Free plan: {DAILY_LIMIT} saves per day. Upgrade to Pro for unlimited.",
        parse_mode=HTML,
    )


@dp.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "How to use Listo:\n"
        "• Send a photo or group of photos — I'll read text and analyze the image.\n"
        "• Send any text — I'll summarize, tag, and fact-check it.\n"
        f"• Free users: up to {DAILY_LIMIT} saves per day.\n\n"
        "You also get:\n"
        "• Weekly digest every Sunday morning\n"
        "• Quarterly review 4 times a year",
        parse_mode=HTML,
    )


FOLDER_EMOJI = {
    "Travel": "✈️", "Books": "📚", "AI": "🤖", "Fashion": "👗",
    "Movies": "🎬", "Knitting": "🧶", "Food": "🍽️", "Tech": "💻",
    "LifeHack": "💡", "Other": "📌",
}


@dp.message(Command("list"))
async def cmd_list(message: Message):
    user_id = message.from_user.id
    entries = database.get_recent_entries(user_id, limit=10)
    if not entries:
        await message.answer("You have no saved items yet.", parse_mode=HTML)
        return
    lines = ["<b>Your last 10 saves:</b>"]
    for i, e in enumerate(entries, 1):
        emoji = FOLDER_EMOJI.get(e["folder"], "📌")
        snippet = (e["summary"] or "")[:60].strip()
        if len(e["summary"] or "") > 60:
            snippet += "…"
        lines.append(f"{i}. {emoji} <b>{e['folder']}</b> — {snippet} <i>({e['created_at']})</i>")
    await message.answer("\n".join(lines), parse_mode=HTML)


@dp.message(Command("search"))
async def cmd_search(message: Message):
    user_id = message.from_user.id
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        await message.answer("Usage: /search &lt;keyword&gt;", parse_mode=HTML)
        return
    query = parts[1].strip()
    entries = database.search_entries(user_id, query, limit=5)
    if not entries:
        await message.answer(f"No results for <b>{html.escape(query)}</b>.", parse_mode=HTML)
        return
    lines = [f"<b>Results for \"{html.escape(query)}\":</b>"]
    for i, e in enumerate(entries, 1):
        emoji = FOLDER_EMOJI.get(e["folder"], "📌")
        snippet = (e["summary"] or "")[:80].strip()
        if len(e["summary"] or "") > 80:
            snippet += "…"
        lines.append(f"{i}. {emoji} <b>{e['folder']}</b> — {snippet} <i>({e['created_at']})</i>")
    await message.answer("\n".join(lines), parse_mode=HTML)


@dp.errors()
async def handle_error(event: ErrorEvent):
    log.exception("Unhandled error: %s", event.exception)


@dp.message(F.photo | F.document)
async def handle_photo(message: Message):
    # Ignore non-image documents
    if message.document:
        mime = message.document.mime_type or ""
        if not mime.startswith("image/"):
            return

    user_id = message.from_user.id

    # Check limit before downloading anything
    if not message.media_group_id and not await _can_save(user_id):
        await message.answer(_limit_message(), parse_mode=HTML)
        return

    file_id, mime = await _get_image_bytes(message)
    try:
        image_bytes = await _download(file_id)
    except Exception:
        await message.answer("Could not download your image. Please try again.", parse_mode=HTML)
        log.exception("File download failed")
        return

    if message.media_group_id:
        gid = message.media_group_id
        if gid not in _mg_buffer:
            _mg_buffer[gid] = []
            _mg_meta[gid] = {"user_id": user_id, "message": message}
        _mg_buffer[gid].append((image_bytes, mime))

        existing = _mg_tasks.get(gid)
        if existing:
            existing.cancel()
        _mg_tasks[gid] = asyncio.create_task(_flush_media_group(gid))
        return

    status = await message.answer("Analyzing your image...", parse_mode=HTML)
    try:
        result = await pipeline.process_images([(image_bytes, mime)], "")
        await _safe_delete(status)
        await _reply_result(message, result, "image")
    except Exception:
        await _safe_delete(status)
        await message.answer("Something went wrong while analyzing your image. Please try again.", parse_mode=HTML)
        log.exception("Single image processing failed")


@dp.message(F.video | F.video_note)
async def handle_video(message: Message):
    user_id = message.from_user.id
    if not await _can_save(user_id):
        await message.answer(_limit_message(), parse_mode=HTML)
        return

    video = message.video or message.video_note
    file_size = getattr(video, "file_size", 0) or 0
    if file_size > 20 * 1024 * 1024:
        await message.answer(
            "Video is too large (max 20MB). Try sending a screenshot instead.",
            parse_mode=HTML,
        )
        return

    duration = getattr(video, "duration", 0) or 0
    status = await message.answer("Transcribing video...", parse_mode=HTML)
    try:
        video_bytes = await _download(video.file_id)
        result = await pipeline.process_video(video_bytes, duration)
        await _safe_delete(status)
        await _reply_result(message, result, "video")
    except Exception:
        await _safe_delete(status)
        await message.answer("Something went wrong while processing your video. Please try again.", parse_mode=HTML)
        log.exception("Video processing failed")


@dp.message(F.text & ~F.text.startswith("/"))
async def handle_text(message: Message):
    if _should_ignore(message):
        return

    user_id = message.from_user.id
    if not await _can_save(user_id):
        await message.answer(_limit_message(), parse_mode=HTML)
        return

    status = await message.answer("Analyzing your text...", parse_mode=HTML)
    try:
        result = await pipeline.process_text(message.text)
        await _safe_delete(status)
        await _reply_result(message, result, "text")
    except Exception:
        await _safe_delete(status)
        await message.answer("Something went wrong while analyzing your text. Please try again.", parse_mode=HTML)
        log.exception("Text processing failed")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def main():
    database.init_db()

    # Clear any active webhook so polling can receive updates
    await bot.delete_webhook(drop_pending_updates=True)

    scheduler = AsyncIOScheduler()
    # Weekly digest — every Sunday at 9:00 AM
    scheduler.add_job(send_weekly_digest, "cron", day_of_week="sun", hour=9, args=[bot])
    # Quarterly review — Jan 1, Apr 1, Jul 1, Oct 1 at 9:00 AM
    scheduler.add_job(
        send_quarterly_review, "cron", month="1,4,7,10", day=1, hour=9, args=[bot]
    )
    scheduler.start()

    log.info("Listo bot starting...")
    await dp.start_polling(bot, allowed_updates=["message"])


if __name__ == "__main__":
    asyncio.run(main())
