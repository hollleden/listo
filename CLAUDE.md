# Listo Bot

Telegram bot for AI-powered content capture and knowledge management.

## Stack
- Python 3.13
- aiogram (Telegram framework)
- google-genai SDK (NOT google-generativeai — that one is deprecated)
- APScheduler for cron jobs
- SQLite on Railway Volume

## Key rules
- Model: gemini-2.5-flash-lite
- All bot-facing text must be in English
- Never use parse_mode="Markdown" in send_message calls
- Global asyncio.Semaphore(1) must wrap all Gemini API calls to avoid 429s
- ALLOWED_ID check must be in every handler — bot is private

## File structure
- listo.py — bot handlers and scheduler
- pipeline.py — Gemini API calls and analysis
- database.py — SQLite
- digest.py — weekly/quarterly digests

## Environment variables
BOT_TOKEN, GEMINI_API_KEY, ALLOWED_ID, DB_PATH
