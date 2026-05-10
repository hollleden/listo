import asyncio
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
    database.save_entry(
        user_id=user_id,
        media_type=media_type,
        raw_content=result.get("raw_content", ""),
        summary=result.get("summary", ""),
        tags=result.get("tags", ""),
        folder=result.get("folder", "Other"),
        fact_check=result.get("fact_check", ""),
        enrichment=result.get("enrichment", ""),
    )

    tags_raw = result.get("tags", "")
    hashtags = " ".join(
        f"#{t.strip().replace(' ', '_').replace('-', '_').lower()}"
        for t in tags_raw.split(",")
        if t.strip()
    )

    text = (
        "Saved!\n\n"
        f"Folder: {result.get('folder', 'Other')}\n\n"
        f"Summary: {result.get('summary', '')}\n\n"
        f"Tags: {hashtags or 'none'}\n\n"
        f"Fact-check: {result.get('fact_check', '')}\n\n"
        f"Context: {result.get('enrichment', '')}"
    )
    await message.answer(text)


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
    caption: str = meta.get("caption", "")

    if not await _can_save(user_id):
        await message.answer(_limit_message())
        return

    status = await message.answer("Analyzing your images...")
    try:
        result = await pipeline.process_images(images, caption)
        await status.delete()
        await _reply_result(message, result, "image_group")
    except Exception:
        await status.delete()
        await message.answer("Something went wrong while analyzing your images. Please try again.")
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
        f"Free plan: {DAILY_LIMIT} saves per day. Upgrade to Pro for unlimited."
    )


@dp.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "How to use Listo:\n"
        "- Send a photo or group of photos — I'll read text and analyze the image.\n"
        "- Send any text — I'll summarize, tag, and fact-check it.\n"
        f"- Free users: up to {DAILY_LIMIT} saves per day.\n\n"
        "You also get:\n"
        "- Weekly digest every Sunday morning\n"
        "- Quarterly review 4 times a year"
    )


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
    file_id, mime = await _get_image_bytes(message)

    try:
        image_bytes = await _download(file_id)
    except Exception:
        await message.answer("Could not download your image. Please try again.")
        log.exception("File download failed")
        return

    if message.media_group_id:
        gid = message.media_group_id
        if gid not in _mg_buffer:
            _mg_buffer[gid] = []
            _mg_meta[gid] = {
                "user_id": user_id,
                "message": message,
                "caption": message.caption or "",
            }
        _mg_buffer[gid].append((image_bytes, mime))

        existing = _mg_tasks.get(gid)
        if existing:
            existing.cancel()
        _mg_tasks[gid] = asyncio.create_task(_flush_media_group(gid))
        return

    # Single image
    if not await _can_save(user_id):
        await message.answer(_limit_message())
        return

    status = await message.answer("Analyzing your image...")
    try:
        result = await pipeline.process_images([(image_bytes, mime)], message.caption or "")
        await status.delete()
        await _reply_result(message, result, "image")
    except Exception:
        await status.delete()
        await message.answer("Something went wrong while analyzing your image. Please try again.")
        log.exception("Single image processing failed")


@dp.message(F.video | F.video_note)
async def handle_video(message: Message):
    user_id = message.from_user.id

    if not await _can_save(user_id):
        await message.answer(_limit_message())
        return

    video = message.video or message.video_note
    file_size = getattr(video, "file_size", 0) or 0
    if file_size > 25 * 1024 * 1024:
        await message.answer("Video is too large (max 25MB). Please send a shorter clip.")
        return

    status = await message.answer("Transcribing video...")
    try:
        video_bytes = await _download(video.file_id)
        caption = message.caption or ""
        result = await pipeline.process_video(video_bytes, caption)
        await status.delete()
        await _reply_result(message, result, "video")
    except Exception:
        await status.delete()
        await message.answer("Something went wrong while processing your video. Please try again.")
        log.exception("Video processing failed")


@dp.message(F.text & ~F.text.startswith("/"))
async def handle_text(message: Message):
    user_id = message.from_user.id

    if not await _can_save(user_id):
        await message.answer(_limit_message())
        return

    status = await message.answer("Analyzing your text...")
    try:
        result = await pipeline.process_text(message.text)
        await status.delete()
        await _reply_result(message, result, "text")
    except Exception:
        await status.delete()
        await message.answer("Something went wrong while analyzing your text. Please try again.")
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
