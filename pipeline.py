import asyncio
import base64
import json
import logging
import os

import httpx
from mistralai import Mistral

MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
_client = Mistral(api_key=MISTRAL_API_KEY)

VISION_MODEL = "pixtral-12b-2409"
TEXT_MODEL = "mistral-small-latest"

# Serialize all Mistral calls to avoid rate-limit errors
_semaphore = asyncio.Semaphore(1)

log = logging.getLogger(__name__)

_ANALYSIS_PROMPT = """Analyze the following content and return ONLY a JSON object with these exact keys:
- "summary": concise 2-3 sentence summary
- "tags": comma-separated list of up to 5 relevant tags
- "folder": single category label (e.g. "Tech", "Health", "Finance", "Science", "Culture", "Personal", "News", "Food", "Travel", "Other")
- "fact_check": note any verifiable claims or factual concerns, or write "No concerns"
- "enrichment": helpful background context, related concepts, or interesting facts

Content:
{content}

Return valid JSON only, no markdown fences."""


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
        "Describe this image in detail. Extract all visible text verbatim, identify objects, "
        "people, places, brands, and key concepts shown.",
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
            "summary": raw[:300],
            "tags": "",
            "folder": "Other",
            "fact_check": "Could not analyze",
            "enrichment": "",
        }


async def _analyze(content: str) -> dict:
    raw = await _call_text(_ANALYSIS_PROMPT.format(content=content))
    return _parse_analysis(raw)


async def process_images(image_list: list[tuple[bytes, str]], caption: str = "") -> dict:
    """image_list: list of (bytes, mime_type)"""
    descriptions = await asyncio.gather(
        *[_describe_image(img, mime) for img, mime in image_list]
    )
    combined = "\n\n---\n\n".join(descriptions)
    if caption:
        combined = f"Caption: {caption}\n\n{combined}"
    analysis = await _analyze(combined)
    analysis["raw_content"] = combined
    return analysis


async def process_text(text: str) -> dict:
    analysis = await _analyze(text)
    analysis["raw_content"] = text
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
