# Listo Bot

Telegram bot for AI-powered content capture and knowledge management.

## Stack
- Python 3.13
- aiogram (Telegram framework)
- mistralai SDK
- APScheduler for cron jobs
- SQLite (Railway Volume via DB_PATH)

## Key rules
- Vision model: pixtral-12b-2409 (image description)
- Text model: mistral-small-latest (analysis, digests)
- All bot-facing text must be in English
- Never use parse_mode="Markdown" in send_message calls
- Global asyncio.Semaphore(1) wraps all Mistral API calls to avoid 429s
- Bot is open to all users — no allowlist
- ADMIN_ID user has unlimited daily saves; regular users capped at 20/day

## File structure
- listo.py — bot handlers and scheduler
- pipeline.py — Mistral API calls and analysis
- database.py — SQLite (entries table with user_id column)
- digest.py — weekly/quarterly digests

## Environment variables
BOT_TOKEN, MISTRAL_API_KEY, ADMIN_ID, DB_PATH
