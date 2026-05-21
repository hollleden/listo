import os
import json
import tempfile
import asyncio
import time
from google import genai
from google.genai import types

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=GEMINI_API_KEY)
MODEL = "gemini-2.0-flash-lite"

_api_semaphore = asyncio.Semaphore(1)

DIVIDER = "━" * 40


def _extract_image(file_bytes: bytes) -> str:
    response = client.models.generate_content(
        model=MODEL,
        contents=[
            types.Part.from_bytes(data=file_bytes, mime_type="image/jpeg"),
            """Extract content from this video in clearly labeled sections:

AUDIO TRANSCRIPT:
[Transcribe all spoken words verbatim]

ON-SCREEN TEXT:
[List all text overlays and captions with timestamps, format: MM:SS — text]

VISUAL DESCRIPTION:
[Brief description of what is shown]""",
        ],
    )
    return response.text


def _extract_video(file_bytes: bytes) -> str:
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
        f.write(file_bytes)
        tmp_path = f.name
    try:
        video_file = client.files.upload(file=tmp_path, config={"mime_type": "video/mp4"})
        while video_file.state.name == "PROCESSING":
            time.sleep(3)
            video_file = client.files.get(name=video_file.name)
        response = client.models.generate_content(
            model=MODEL,
            contents=[
                video_file,
                "Extract ALL text from subtitles and overlays. Transcribe all speech. Describe what is happening.",
            ],
        )
        return response.text
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def _analyze(raw_content: str) -> dict:
    prompt = f"""You are an assistant for organizing saved content.
Content:
{raw_content}

Return a JSON with these fields:
{{
  "title": "short punchy title (max 10 words)",
  "summary": "2-3 sentences in English.",
  "tags": ["tag1", "tag2", "tag3"],
  "folder": "Grow|Rest|Health|Creativity|Money|Work|Curation|Personal",
  "key_points": ["concise bullet point 1", "concise bullet point 2", "concise bullet point 3"],
  "fact_check": "one sentence on accuracy or empty string",
  "enrichment": {{
    "concepts": ["Term (brief definition)", "Term2 (brief definition)"],
    "context": "one sentence on background, origin, or inspiration",
    "source": "website URL or name if found, else empty string"
  }}
}}
Return ONLY valid JSON."""

    response = client.models.generate_content(model=MODEL, contents=prompt)
    text = response.text.strip().replace("```json", "").replace("```", "").strip()
    data = json.loads(text)
    # guard: ensure no nested dicts slip through
    for key in ("summary", "fact_check", "enrichment", "title"):
        if isinstance(data.get(key), dict):
            data[key] = json.dumps(data[key])
    return data


def format_result(result: dict) -> str:
    """Format analysis dict into a human-readable bot message."""
    folder = result.get("folder", "Personal")
    tags = result.get("tags", [])
    title = result.get("title", "Untitled")
    key_points = result.get("key_points", [])
    raw_content = result.get("raw_content", "")

    # Parse enrichment
    enr_raw = result.get("enrichment", "")
    concepts, context, source = "", "", ""
    if enr_raw:
        try:
            enr = json.loads(enr_raw) if isinstance(enr_raw, str) else enr_raw
            if isinstance(enr, dict):
                c = enr.get("concepts", [])
                concepts = ", ".join(c) if isinstance(c, list) else str(c)
                context = enr.get("context", "")
                source = enr.get("source", "")
        except (json.JSONDecodeError, TypeError):
            pass

    first_tag = f"#{tags[0].lstrip('#')}" if tags else ""
    header = f"📁 {folder} | {first_tag}" if first_tag else f"📁 {folder}"

    lines = [header, "", f"🤖 {title}", ""]

    # SUMMARY
    lines += [DIVIDER, "📋 SUMMARY"]
    for pt in key_points[:4]:
        lines.append(f"• {pt}")

    # TRANSCRIPTION
    if raw_content.strip():
        lines += ["", DIVIDER, "📝 TRANSCRIPTION (OCRs & NOTES)", raw_content.strip()]

    # NERDY METADATA
    if concepts or context or source:
        lines += ["", DIVIDER, "🔍 NERDY METADATA"]
        if concepts:
            lines.append(f"• Concepts: {concepts}")
        if context:
            lines.append(f"• Context: {context}")
        if source:
            lines.append(f"• Source: {source}")

    # TAGS
    if tags:
        tag_line = " ".join(f"#{t.lstrip('#')}" for t in tags[:6])
        lines += ["", DIVIDER, tag_line]

    return "\n".join(lines)


def extract_db_fields(result: dict) -> dict:
    """Extract fields needed for database.save_entry."""
    tags = result.get("tags", [])
    if isinstance(tags, list):
        tags = json.dumps(tags, ensure_ascii=False)
    return {
        "summary": result.get("summary", ""),
        "tags": tags,
        "folder": result.get("folder", "Personal"),
        "fact_check": result.get("fact_check", ""),
        "enrichment": result.get("enrichment", ""),
        "title": result.get("title", ""),
    }


async def _run_pipeline(raw_content: str, is_video: bool = False) -> dict:
    """Run analysis and return result dict (saving is handled by listo.py)."""
    analysis = await asyncio.wait_for(
        asyncio.to_thread(_analyze, raw_content), timeout=60.0
    )
    analysis["raw_content"] = raw_content
    return analysis


async def process_media(file_bytes: bytes, media_type: str, caption: str = "") -> dict:
    async with _api_semaphore:
        try:
            if media_type == "image":
                raw_media = await asyncio.to_thread(_extract_image, file_bytes)
            else:
                raw_media = await asyncio.to_thread(_extract_video, file_bytes)
            raw = f"{caption}\n\n{raw_media}" if caption else raw_media
            return await _run_pipeline(raw, is_video=(media_type == "video"))
        except Exception as e:
            return {"error": str(e), "raw_content": "", "content_type": "other",
                    "title": "Error", "summary": str(e), "tags": [], "folder": "Personal",
                    "fact_check": "", "enrichment": ""}


async def process_media_group(images: list[bytes], caption: str = "") -> dict:
    async with _api_semaphore:
        try:
            parts = []
            for i, img in enumerate(images):
                text = await asyncio.to_thread(_extract_image, img)
                parts.append(f"[Image {i+1}]: {text}")
            raw = f"{caption}\n\n" + "\n".join(parts)
            return await _run_pipeline(raw)
        except Exception as e:
            return {"error": str(e), "raw_content": "", "content_type": "other",
                    "title": "Error", "summary": str(e), "tags": [], "folder": "Personal",
                    "fact_check": "", "enrichment": ""}


async def process_text(text: str) -> dict:
    async with _api_semaphore:
        try:
            return await _run_pipeline(text)
        except Exception as e:
            return {"error": str(e), "raw_content": text, "content_type": "other",
                    "title": "Error", "summary": str(e), "tags": [], "folder": "Personal",
                    "fact_check": "", "enrichment": ""}
