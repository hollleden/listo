import asyncio
import base64
import json
import logging
import os
import tempfile

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
    "image_2": "all raw visible text from image 2 exactly as it appears, line by line",
    "video": "full speech transcript"
  }},
  "entities": {{
    "places": [{{"name": "...", "type": "restaurant/city/landmark/etc"}}],
    "books": [{{"title": "...", "author": "..."}}],
    "movies_tv": [{{"title": "..."}}],
    "fashion": [{{"brand": "..."}}],
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
- transcription: only include keys that appear in the content labels (image_1, image_2, video). Extract ONLY literally visible text — do not paraphrase or summarise.
- entities: include ONLY entities explicitly present in the content. Omit any category that has no entries (no empty arrays).
- tags.category: EXACTLY ONE from: #Travel #Books #AI #Fashion #Movies #Knitting #Food #Tech #LifeHack #Other
- tags.cta: zero or more from: #must_try #paid #free #warning #timely #local #tutorial #list #review
- tags.extra: additional lowercase hashtags, underscores not hyphens
- Return valid JSON only, no markdown fences."""


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
# Output formatting
# ---------------------------------------------------------------------------

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


def format_result(result: dict) -> str:
    lines = []

    # --- Transcription ---
    transcription = result.get("transcription") or {}
    if transcription:
        lines.append("📝 Exact transcription")
        for key in sorted(transcription.keys()):
            text = (transcription[key] or "").strip()
            if not text:
                continue
            if key.startswith("image_"):
                label = f"Image {key.split('_', 1)[1]}"
            elif key == "video":
                label = "Video"
            else:
                label = key.replace("_", " ").title()
            lines.append(f"-- {label} --")
            lines.append(text)
        lines.append("")

    # --- Extracted entities ---
    entities = result.get("entities") or {}
    entity_lines = []

    for place in entities.get("places") or []:
        if not entity_lines or entity_lines[-1] != "📍 Places":
            entity_lines.append("📍 Places")
        name = place.get("name", "")
        typ = place.get("type", "")
        label = f"{name} ({typ})" if typ else name
        entity_lines.append(f"- {label} → Maps | Google")

    for book in entities.get("books") or []:
        if not entity_lines or entity_lines[-1] != "📚 Books":
            entity_lines.append("📚 Books")
        title = book.get("title", "")
        author = book.get("author", "")
        label = f"{title} by {author}" if author else title
        entity_lines.append(f"- {label} → Goodreads | Google")

    for movie in entities.get("movies_tv") or []:
        if not entity_lines or entity_lines[-1] != "🎬 Movies & TV":
            entity_lines.append("🎬 Movies & TV")
        entity_lines.append(f"- {movie.get('title', '')} → IMDb | Google")

    for item in entities.get("fashion") or []:
        if not entity_lines or entity_lines[-1] != "🧥 Fashion":
            entity_lines.append("🧥 Fashion")
        entity_lines.append(f"- {item.get('brand', '')} → Store | Google")

    for site in entities.get("websites") or []:
        if not entity_lines or entity_lines[-1] != "🌐 Websites":
            entity_lines.append("🌐 Websites")
        name = site.get("name", "")
        url = site.get("url", "")
        entity_lines.append(f"- {name} → {url}" if url else f"- {name}")

    for term in entities.get("ai_terms") or []:
        if not entity_lines or entity_lines[-1] != "🤖 AI terms & tips":
            entity_lines.append("🤖 AI terms & tips")
        entity_lines.append(f"- {term.get('term', '')} → Explain | Google")

    for handle in entities.get("social_handles") or []:
        if not entity_lines or entity_lines[-1] != "👤 Social handles":
            entity_lines.append("👤 Social handles")
        h = handle.get("handle", "")
        if h and not h.startswith("@"):
            h = f"@{h}"
        entity_lines.append(f"- {h} → Google")

    for item in entities.get("other") or []:
        if not entity_lines or entity_lines[-1] != "📦 Other":
            entity_lines.append("📦 Other")
        entity_lines.append(f"- {item.get('entity', '')} → Google")

    if entity_lines:
        lines.append("🔍 Extracted")
        lines.extend(entity_lines)
        lines.append("")

    # --- Summary ---
    summary = result.get("summary") or {}
    if isinstance(summary, dict):
        what = (summary.get("what") or "").strip()
        details = (summary.get("details") or "").strip()
    else:
        what, details = str(summary).strip(), ""
    if what or details:
        lines.append("📋 Summary")
        if what:
            lines.append(f"*What:* {what}")
        if details:
            lines.append(f"*Details:* {details}")
        lines.append("")

    # --- Tags ---
    tag_str = _fmt_tags(result.get("tags") or {})
    if tag_str:
        lines.append("🏷️ Tags")
        lines.append(tag_str)

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


async def process_video(video_bytes: bytes, caption: str = "") -> dict:
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
    transcript = transcript.strip() if isinstance(transcript, str) else str(transcript).strip()
    content = f"-- Video --\n{transcript}"
    if caption:
        content = f"Caption: {caption}\n\n{content}"
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
