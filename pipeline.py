import asyncio
import base64
import html
import json
import logging
import os
import subprocess
import tempfile
from urllib.parse import quote_plus

import httpx
from mistralai import Mistral
from openai import AsyncOpenAI

MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
_client = Mistral(api_key=MISTRAL_API_KEY)
openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

VISION_MODEL = "pixtral-12b-2409"
TEXT_MODEL = "mistral-small-latest"

# Serialize all Mistral calls to avoid rate-limit errors
_semaphore = asyncio.Semaphore(1)

log = logging.getLogger(__name__)

_ANALYSIS_PROMPT = """Analyze the following content and return ONLY a valid JSON object.

Content:
{content}

Return this exact structure:
{{
  "transcription": {{
    "image_1": "all raw visible text from image 1 exactly as it appears, line by line",
    "image_2": "all raw visible text from image 2, line by line",
    "video": "full audio transcript",
    "frame_003": "all on-screen text visible in the frame at 0:03",
    "frame_006": "all on-screen text visible in the frame at 0:06"
  }},
  "entities": {{
    "places": [{{"name": "...", "type": "restaurant/city/landmark/etc"}}],
    "books": [{{"title": "...", "author": "..."}}],
    "movies_tv": [{{"title": "..."}}],
    "fashion": [{{"brand": "..."}}],
    "beauty_skincare": [{{"product": "...", "brand": "..."}}],
    "websites": [{{"name": "...", "url": "..."}}],
    "ai_terms": [{{"term": "..."}}],
    "social_handles": [{{"handle": "@username"}}],
    "other": [{{"entity": "..."}}]
  }},
  "summary": {{
    "what": "one clear sentence: what question does this content answer",
    "details": "key specifics: prices, steps, warnings, measurements"
  }},
  "tags": {{
    "category": "#Tech",
    "cta": ["#tutorial"],
    "extra": ["#python", "#ai_tools"]
  }},
  "fact_check": "any verifiable claims or concerns, or No concerns",
  "folder": "single category label"
}}

Rules:
- transcription: only include keys present in the content labels (image_1, image_2, video for audio, frame_NNN for video frames). Extract ONLY literally visible/spoken text — do not paraphrase.
- entities: include ONLY entities explicitly present in the content. Omit any category with no entries (no empty arrays).
- Group all extracted entities strictly by category. Each category appears exactly once. All items for a category must be listed consecutively before moving to the next category.
- social_handles: skip any handle that belongs to a bot (contains "bot" in the name).
- tags.category: EXACTLY ONE from: #Travel #Books #AI #Fashion #Movies #Knitting #Food #Tech #LifeHack #Other
- tags.cta: zero or more from: #must_try #paid #free #warning #timely #local #tutorial #list #review
- tags.extra: lowercase hashtags, underscores not hyphens
- Return valid JSON only, no markdown fences."""


# ---------------------------------------------------------------------------
# Mistral API calls
# ---------------------------------------------------------------------------

async def _call_text(prompt: str) -> str:
    async with _semaphore:
        resp = await _client.chat.complete_async(
            model=TEXT_MODEL,
            messages=[{"role": "user", "content": prompt}],
        )
    return resp.choices[0].message.content.strip()


async def _call_vision(image_bytes: bytes, mime: str, prompt: str) -> str:
    # mistralai 1.0.0 SDK types don't include ImageURLChunk, so call the API directly.
    b64 = base64.b64encode(image_bytes).decode()
    data_url = f"data:{mime};base64,{b64}"
    payload = {
        "model": VISION_MODEL,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": data_url},
                ],
            }
        ],
    }
    async with _semaphore:
        async with httpx.AsyncClient(timeout=120.0) as http:
            resp = await http.post(
                "https://api.mistral.ai/v1/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {MISTRAL_API_KEY}"},
            )
            resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


async def _describe_image(image_bytes: bytes, mime: str = "image/jpeg") -> str:
    return await _call_vision(
        image_bytes,
        mime,
        "Extract ALL visible text from this image exactly as it appears, line by line. "
        "Then briefly note any key objects, people, places, or brands not captured by the text.",
    )


def _parse_analysis(raw: str) -> dict:
    text = raw.strip()
    if text.startswith("```"):
        parts = text.split("```")
        text = parts[1].lstrip("json").strip() if len(parts) > 1 else text
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        log.warning("Could not parse Mistral JSON response: %s", raw[:200])
        return {
            "transcription": {},
            "entities": {},
            "summary": {"what": raw[:200], "details": ""},
            "tags": {"category": "#Other", "cta": [], "extra": []},
            "fact_check": "Could not analyze",
            "folder": "Other",
        }


async def _analyze(content: str) -> dict:
    raw = await _call_text(_ANALYSIS_PROMPT.format(content=content))
    return _parse_analysis(raw)


# ---------------------------------------------------------------------------
# Video helpers
# ---------------------------------------------------------------------------

async def _transcribe_audio(video_bytes: bytes) -> str:
    tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
    try:
        tmp.write(video_bytes)
        tmp.close()
        with open(tmp.name, "rb") as f:
            transcript = await openai_client.audio.transcriptions.create(
                model="whisper-1",
                file=f,
                response_format="text",
            )
    finally:
        os.unlink(tmp.name)
    return transcript.strip() if isinstance(transcript, str) else str(transcript).strip()


def _extract_frames_sync(video_bytes: bytes, duration: int) -> list[tuple[bytes, int]]:
    """Extract frames at 0:03, 0:06, 0:09… using imageio-ffmpeg. Returns [(jpeg_bytes, seconds)]."""
    try:
        import imageio_ffmpeg
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        log.warning("imageio-ffmpeg not available — skipping frame extraction")
        return []

    interval = 3
    max_frames = 5
    effective_duration = max(duration, interval + 1)
    timestamps = [i * interval for i in range(1, max_frames + 1) if i * interval < effective_duration]
    if not timestamps:
        return []

    frames: list[tuple[bytes, int]] = []
    with tempfile.TemporaryDirectory() as tmpdir:
        video_path = os.path.join(tmpdir, "video.mp4")
        with open(video_path, "wb") as f:
            f.write(video_bytes)

        for ts in timestamps:
            frame_path = os.path.join(tmpdir, f"frame_{ts}.jpg")
            result = subprocess.run(
                [ffmpeg_exe, "-ss", str(ts), "-i", video_path,
                 "-vframes", "1", "-q:v", "2", "-y", frame_path],
                capture_output=True,
            )
            if result.returncode == 0 and os.path.exists(frame_path):
                with open(frame_path, "rb") as f:
                    frames.append((f.read(), ts))

    return frames


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _q(text: str) -> str:
    return quote_plus(text)


def _a(label: str, url: str) -> str:
    return f'<a href="{url}">{label}</a>'


def _fmt_tags(tags) -> str:
    if isinstance(tags, str):
        return tags
    parts = []
    cat = (tags.get("category") or "").strip()
    if cat:
        parts.append(cat if cat.startswith("#") else f"#{cat}")
    for tag in tags.get("cta") or []:
        t = tag.strip()
        if t:
            parts.append(t if t.startswith("#") else f"#{t}")
    for tag in tags.get("extra") or []:
        t = tag.strip().replace("-", "_").lower()
        if t:
            parts.append(t if t.startswith("#") else f"#{t}")
    return " ".join(parts)


def _transcription_label(key: str) -> str:
    if key.startswith("image_"):
        return f"Image {key.split('_', 1)[1]}"
    if key == "video":
        return "Audio transcript"
    if key.startswith("frame_"):
        try:
            secs = int(key.split("_", 1)[1])
            return f"Video at {secs // 60}:{secs % 60:02d}"
        except (ValueError, IndexError):
            pass
    return key.replace("_", " ").title()


def format_result(result: dict) -> str:
    lines = []

    # --- 1. Exact transcription (always first) ---
    transcription = result.get("transcription") or {}
    if transcription:
        lines.append("📝 Exact transcription")
        for key in sorted(transcription.keys()):
            text = (transcription[key] or "").strip()
            if not text:
                continue
            lines.append(f"-- {_transcription_label(key)} --")
            lines.append(html.escape(text))
        lines.append("")

    # --- 2. Extracted entities ---
    entities = result.get("entities") or {}
    entity_lines = []

    places = entities.get("places") or []
    if places:
        entity_lines.append("📍 Places")
        for p in places:
            name = p.get("name", "")
            typ = p.get("type", "")
            label = html.escape(f"{name} ({typ})" if typ else name)
            maps = _a("Maps", f"https://www.google.com/maps/search/{_q(name)}")
            google = _a("Google", f"https://www.google.com/search?q={_q(name)}")
            entity_lines.append(f"• {label} → {maps} | {google}")

    books = entities.get("books") or []
    if books:
        entity_lines.append("📚 Books")
        for b in books:
            title = b.get("title", "")
            author = b.get("author", "")
            raw_label = f"{title} by {author}" if author else title
            label = html.escape(raw_label)
            goodreads = _a("Goodreads", f"https://www.goodreads.com/search?q={_q(raw_label)}")
            google = _a("Google", f"https://www.google.com/search?q={_q(raw_label)}")
            entity_lines.append(f"• {label} → {goodreads} | {google}")

    movies_tv = entities.get("movies_tv") or []
    if movies_tv:
        entity_lines.append("🎬 Movies & TV")
        for m in movies_tv:
            title = m.get("title", "")
            label = html.escape(title)
            imdb = _a("IMDb", f"https://www.imdb.com/find?q={_q(title)}")
            google = _a("Google", f"https://www.google.com/search?q={_q(title)}")
            entity_lines.append(f"• {label} → {imdb} | {google}")

    fashion = entities.get("fashion") or []
    if fashion:
        entity_lines.append("🧥 Fashion")
        for f in fashion:
            brand = f.get("brand", "")
            google = _a("Google", f"https://www.google.com/search?q={_q(brand)}")
            entity_lines.append(f"• {html.escape(brand)} → {google}")

    beauty = entities.get("beauty_skincare") or []
    if beauty:
        entity_lines.append("💄 Beauty & Skincare")
        for b in beauty:
            product = b.get("product", "")
            brand = b.get("brand", "")
            raw_label = f"{product} by {brand}" if brand else product
            google = _a("Google", f"https://www.google.com/search?q={_q(raw_label)}")
            entity_lines.append(f"• {html.escape(raw_label)} → {google}")

    websites = entities.get("websites") or []
    if websites:
        entity_lines.append("🌐 Websites")
        for w in websites:
            name = w.get("name", "")
            url = w.get("url", "")
            label = html.escape(name)
            entity_lines.append(f"• {label} → {_a(url, url)}" if url else f"• {label}")

    ai_terms = entities.get("ai_terms") or []
    if ai_terms:
        entity_lines.append("🤖 AI terms & tips")
        for a in ai_terms:
            term = a.get("term", "")
            google = _a("Google", f"https://www.google.com/search?q={_q(term)}")
            entity_lines.append(f"• {html.escape(term)} → {google}")

    social = [s for s in (entities.get("social_handles") or [])
              if "bot" not in (s.get("handle") or "").lower()]
    if social:
        entity_lines.append("👤 Social handles")
        for s in social:
            h = s.get("handle", "")
            if h and not h.startswith("@"):
                h = f"@{h}"
            google = _a("Google", f"https://www.google.com/search?q={_q(h)}")
            entity_lines.append(f"• {html.escape(h)} → {google}")

    other = entities.get("other") or []
    if other:
        entity_lines.append("📦 Other")
        for o in other:
            entity = o.get("entity", "")
            google = _a("Google", f"https://www.google.com/search?q={_q(entity)}")
            entity_lines.append(f"• {html.escape(entity)} → {google}")

    if entity_lines:
        lines.append("🔍 Extracted")
        lines.extend(entity_lines)
        lines.append("")

    # --- 3. Summary ---
    summary = result.get("summary") or {}
    if isinstance(summary, dict):
        what = html.escape((summary.get("what") or "").strip())
        details = html.escape((summary.get("details") or "").strip())
    else:
        what, details = html.escape(str(summary).strip()), ""
    if what or details:
        lines.append("📋 Summary")
        if what:
            lines.append(f"<b>What:</b> {what}")
        if details:
            lines.append(f"<b>Details:</b> {details}")
        lines.append("")

    # --- 4. Tags ---
    tag_str = _fmt_tags(result.get("tags") or {})
    if tag_str:
        lines.append("🏷️ Tags")
        lines.append(html.escape(tag_str))

    return "\n".join(lines).strip()


def extract_db_fields(result: dict) -> dict:
    summary = result.get("summary") or {}
    if isinstance(summary, dict):
        summary_str = f"{summary.get('what', '')} {summary.get('details', '')}".strip()
    else:
        summary_str = str(summary)

    tags = result.get("tags") or {}
    tags_str = _fmt_tags(tags)
    cat = (tags.get("category") or "#Other").strip() if isinstance(tags, dict) else "#Other"
    folder = cat.lstrip("#")

    return {
        "summary": summary_str,
        "tags": tags_str,
        "folder": folder,
        "fact_check": result.get("fact_check", ""),
        "enrichment": json.dumps(result.get("entities") or {}),
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def process_images(image_list: list[tuple[bytes, str]], caption: str = "") -> dict:
    descriptions = []
    for i, (img, mime) in enumerate(image_list, 1):
        desc = await _describe_image(img, mime)
        descriptions.append(f"-- Image {i} --\n{desc}")
    content = "\n\n".join(descriptions)
    if caption:
        content = f"Caption: {caption}\n\n{content}"
    analysis = await _analyze(content)
    analysis["raw_content"] = content
    return analysis


async def process_text(text: str) -> dict:
    analysis = await _analyze(text)
    analysis.pop("transcription", None)  # don't echo the user's own text back
    analysis["raw_content"] = text
    return analysis


async def process_video(video_bytes: bytes, duration: int = 0) -> dict:
    # Run Whisper transcription (async) and frame extraction (blocking thread) in parallel
    transcript_task = _transcribe_audio(video_bytes)
    frames_task = asyncio.to_thread(_extract_frames_sync, video_bytes, duration)

    transcript, frames = await asyncio.gather(
        transcript_task, frames_task, return_exceptions=True
    )

    if isinstance(transcript, Exception):
        log.warning("Audio transcription failed: %s", transcript)
        transcript = ""
    if isinstance(frames, Exception):
        log.warning("Frame extraction failed: %s", frames)
        frames = []

    # Build labeled content
    content_parts = []
    if transcript:
        content_parts.append(f"-- video --\n{transcript}")

    for frame_bytes, ts_sec in frames:
        key = f"frame_{ts_sec:03d}"
        desc = await _describe_image(frame_bytes, "image/jpeg")
        content_parts.append(f"-- {key} --\n{desc}")

    content = "\n\n".join(content_parts) if content_parts else "No extractable content."
    analysis = await _analyze(content)
    analysis["raw_content"] = content
    return analysis


async def summarize_entries(entries: list[dict], period_label: str) -> str:
    if not entries:
        return ""
    items = "\n\n".join(
        f"[{e['created_at']}] [{e['folder']}] {e['summary']}" for e in entries
    )
    prompt = (
        f"Write a {period_label} digest for these saved items. "
        "Group by theme, highlight patterns and key insights, and suggest areas to explore further. "
        "Use clear English, plain text (no markdown).\n\nItems:\n" + items
    )
    return await _call_text(prompt)
