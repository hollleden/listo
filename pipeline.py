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

_semaphore = asyncio.Semaphore(1)

log = logging.getLogger(__name__)

DIVIDER = "━━━━━━━━━━━━━━━━"

_ANALYSIS_PROMPT = """Analyze the following content and return ONLY a valid JSON object.

Content:
{content}

Return this exact structure:
{{
  "transcription": {{
    "image_1": "all raw visible text from image 1 exactly as it appears, line by line",
    "image_2": "all raw visible text from image 2, line by line",
    "video": "full audio transcript",
    "3": "all on-screen text visible at second 3",
    "6": "all on-screen text visible at second 6"
  }},
  "entities": {{
    "places": [{{"name": "...", "type": "restaurant/city/landmark/etc"}}],
    "books": [{{"title": "...", "author": "..."}}],
    "movies_tv": [{{"title": "..."}}],
    "fashion": [{{"brand": "..."}}],
    "knitting": [{{"pattern": "...", "creator": "..."}}],
    "beauty_skincare": [{{"product": "...", "brand": "..."}}],
    "health_products": [{{"name": "...", "type": "supplement/medication/skincare/device", "price": "..."}}],
    "websites": [{{"name": "...", "url": "..."}}],
    "ai_terms": [{{"term": "...", "explanation": "one-line explanation"}}],
    "social_handles": [{{"handle": "@username"}}],
    "other": [{{"entity": "..."}}]
  }},
  "summary": {{
    "what": "one clear sentence: what question does this content answer",
    "details": "key specifics: prices, steps, warnings, measurements, location"
  }},
  "tags": {{
    "category": "#Tech",
    "extra": ["#python", "#tutorial", "#must_try", "#local"]
  }},
  "fact_check": "any verifiable claims or concerns, or No concerns",
  "title": "short 3-6 word title describing the specific content",
  "folder": "single category label"
}}

Rules:

TRANSCRIPTION:
- Extract ALL visible text from every image completely, word for word: titles, descriptions, captions, reviews, body text, small print, labels, prices, usernames — everything.
- Never stop after the first line or title. Capture the full text as it appears, line by line.
- Only include keys present in the content labels. Images use image_1, image_2. Audio uses video. Video frames use the integer second as key (3, 6, 9). Do not paraphrase.

ENTITY CATEGORY SELECTION:
- CRITICAL RULE: Only add an entity to Movies & TV if the post LITERALLY SHOWS movie footage, a film poster, a trailer, or a TV episode. A comic book cover is NOT a movie. A book cover is NOT a movie. If you see a drawn/illustrated image, it is Books, not Movies & TV. When in doubt, omit Movies & TV entirely.
- A post can appear in multiple categories ONLY if it genuinely contains content from multiple forms (e.g. shows both a book cover and a movie trailer).
- Omit any category with no entries (no empty arrays).
- Group all extracted entities strictly by category. Each category appears exactly once.

BOOKS:
- For books, always include the author field if the author name is visible anywhere in the content. Never leave author blank if the name appears in the transcription.

OTHER:
- CRITICAL RULE: This section is FORBIDDEN from containing any visual descriptions, artistic elements, or scene descriptions. FORBIDDEN examples: "golden robot head", "large eye", "masked figure", "hand holding gun", "futuristic weapon", any color+object combination.
- ALLOWED examples: a named product like "Nike Air Max", or an actionable tip like "freeze grapes to chill wine".
- If you cannot think of a named product or actionable tip from the content, omit OTHER entirely.
- Maximum 3 items.

TAGS — from two sources:
- Source A: words explicitly visible in the image or spoken aloud in audio.
- Source B: genre, format, and subject tags based on what the content IS (e.g. #comics, #graphic_novel, #noir, #barcelona, #recipe, #tutorial). Do NOT infer abstract themes or concepts (e.g. do not add #privacy, #freedom, #identity unless those exact words appear in the content).
- Always generate at least 2-3 tags. Never leave tags.extra empty.
- tags.category: EXACTLY ONE from this list:
  #Travel = destinations, places to visit, city guides, restaurants, hotels, tourism
  #Books = books, graphic novels, comics, reading, literature, authors
  #AI = artificial intelligence, machine learning, LLMs, AI tools, prompting, chatbots
  #Fashion = clothing, style, accessories, outfits, streetwear, designers
  #Beauty = skincare, makeup, cosmetics, haircare, SPF, serums, beauty tools, beauty routines
  #Movies = films, movie trailers, TV series, episodes, cinema, streaming
  #Knitting = knitting, crochet, yarn, patterns, needlework, fiber arts
  #Food = recipes, restaurants, cooking, drinks, cuisine, food reviews
  #Tech = software, apps, gadgets, programming, digital tools, coding, hardware. NOT urban planning, NOT city design
  #LifeHack = practical tips, productivity, life improvements, urban design, smart everyday solutions
  #Psychology = mental health, emotions, behavior, relationships, self-awareness, emotional intelligence, mindset
  #Health = fitness, nutrition, medical, wellness, physical health, exercise, body
  #Finance = money, investing, budgeting, economics, personal finance, crypto
  #Design = graphic design, UX/UI, architecture, interior design, visual arts, branding
  #Language = language learning, Spanish, vocabulary, grammar, linguistics, translation
  #Nature = plants, animals, outdoors, hiking, ecology, gardening, environment
  #Music = songs, artists, albums, playlists, concerts, music theory, instruments
  #Photography = photos, cameras, editing, visual composition, lighting
  #Parenting = kids, family, education, child development, parenting tips
  #Other = anything that does not fit the above categories
- tags.extra: lowercase hashtags with underscores not hyphens.

NOISE FILTER:
- The content may contain website UI text mixed with actual content.
- Treat as signal: product names, prices, spoken words, headlines, descriptions.
- Treat as noise and IGNORE: "Añadir al carrito", "Add to cart", "Te gustaría", navigation arrows, star ratings like ★★★★★, "Búsqueda", search bars, pagination, social media buttons, cookie notices, any repeated boilerplate.
- The audio transcript (key "video") is ALWAYS the primary source of truth.
- Frame text (integer keys) provides supplementary product/price data only.

HEALTH PRODUCTS:
- Extract named medications, supplements, vitamins, pharmacy products, and medical devices into health_products.
- Include price if visible. Include type (supplement/medication/skincare/device).
- Examples: Fisiogen Ferro Forte, VITALDIN Melatonin, Cristalmina Spray, magnesium citrate.
- These should NEVER go in Other.

TITLE:
- Generate a short specific 3-6 word title capturing what THIS content is about.
- Not generic. Not the category name. The actual subject.
- Examples: "The Private Eye graphic novel", "Romantic spots in Barcelona", "Korean retinol skincare routine".

SOCIAL HANDLES:
- Skip any handle containing "bot" (case insensitive).
- Skip @SaveAsBot and any download/utility/service bots.

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
        "Extract all visible text from this image exactly as written, line by line.\n"
        "After the text, on a new line write 'VISUAL:' followed by a single line noting "
        "only named brands, products, or people visible but not captured in text.\n"
        "Do not describe UI elements, buttons, icons, decorative elements, or generic objects.",
    )


async def _describe_frame(image_bytes: bytes) -> str:
    return await _call_vision(
        image_bytes,
        "image/jpeg",
        "Extract only meaningful text from this video frame.\n"
        "INCLUDE: product names, brand names, prices, headlines, subtitles, key labels.\n"
        "EXCLUDE: buttons (Add to cart, Buy now, etc.), navigation menus, star ratings, "
        "search bars, social media UI (likes, shares, arrows), website logos, "
        "cookie banners, any repeated UI chrome.\n"
        "Output only the included text, one item per line. If nothing meaningful, return empty.",
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
            "tags": {"category": "#Other", "extra": []},
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


def _fmt_folder(tags) -> str:
    """Returns the single category tag, e.g. '#Travel'."""
    if not isinstance(tags, dict):
        return "#Other"
    cat = (tags.get("category") or "").strip()
    if not cat:
        return "#Other"
    return cat if cat.startswith("#") else f"#{cat}"


def _fmt_tags(tags) -> str:
    """Returns space-joined extra tags only (no category)."""
    if not isinstance(tags, dict):
        return ""
    parts = []
    for tag in tags.get("extra") or []:
        t = tag.strip().replace("-", "_").lower()
        if t:
            parts.append(t if t.startswith("#") else f"#{t}")
    return " ".join(parts)


def _transcription_sort_key(k: str) -> tuple:
    if k.startswith("image_"):
        try:
            return (0, int(k.split("_", 1)[1]), "")
        except (ValueError, IndexError):
            return (0, 999, k)
    if k == "video":
        return (1, 0, "")
    try:
        return (2, int(k), "")
    except ValueError:
        return (3, 0, k)


CATEGORY_EMOJI = {
    "#Travel": "🌍", "#Books": "📚", "#AI": "🤖", "#Fashion": "🧥",
    "#Beauty": "💄", "#Movies": "🎬", "#Knitting": "🧶", "#Food": "🍽️",
    "#Tech": "💻", "#LifeHack": "💡", "#Psychology": "🧠", "#Health": "💪",
    "#Finance": "💰", "#Design": "🎨", "#Language": "💬", "#Nature": "🌿",
    "#Music": "🎵", "#Photography": "📷", "#Parenting": "👶", "#Other": "📌",
}


def _section(header: str, body_lines: list[str]) -> str:
    return "\n".join([DIVIDER, header] + body_lines)


def format_result(result: dict) -> str:
    sections = []

    # --- Bold header ---
    tags = result.get("tags") or {}
    folder_str = _fmt_folder(tags)
    emoji = CATEGORY_EMOJI.get(folder_str, "📌")
    category_label = folder_str.lstrip("#").upper()
    title = html.escape((result.get("title") or "").strip())
    if title:
        sections.append(f"<b>{emoji} {category_label} · {title}</b>")
    else:
        sections.append(f"<b>{emoji} {category_label}</b>")

    # --- 1. SUMMARY ---
    summary = result.get("summary") or {}
    if isinstance(summary, dict):
        what = html.escape((summary.get("what") or "").strip())
        details = html.escape((summary.get("details") or "").strip())
    else:
        what, details = html.escape(str(summary).strip()), ""
    if what or details:
        body = []
        if what:
            body.append(f"▪ {what}")
        if details:
            body.append(f"▪ {details}")
        sections.append(_section("📋 SUMMARY", body))

    # --- 2. TRANSCRIPTION ---
    transcription = result.get("transcription") or {}
    t_body = []
    for key in sorted(transcription.keys(), key=_transcription_sort_key):
        text = (transcription[key] or "").strip()
        if not text:
            continue
        if key.startswith("image_"):
            n = key.split("_", 1)[1]
            t_body.append(f"┆ -- Image {n} --")
            for line in text.split("\n"):
                if line.strip():
                    t_body.append(f"┆ {html.escape(line.strip())}")
        elif key == "video":
            for line in text.split("\n"):
                if line.strip():
                    t_body.append(f"┆ {html.escape(line.strip())}")
        else:
            try:
                secs = int(key)
                timestamp = f"{secs // 60}:{secs % 60:02d}"
                frame_text = " ".join(ln.strip() for ln in text.split("\n") if ln.strip())
                t_body.append(f"┆ {timestamp} -- {html.escape(frame_text)}")
            except ValueError:
                t_body.append(f"┆ {html.escape(text)}")
    if t_body:
        sections.append(_section("📝 TRANSCRIPTION", t_body))

    # --- 3. EXTRACTED ---
    entities = result.get("entities") or {}
    cat_blocks: list[str] = []

    def _cat(header: str, items: list[str]) -> None:
        if items:
            cat_blocks.append(f"▪ {header}\n" + "\n".join(f"  {i}" for i in items))

    places = entities.get("places") or []
    if places:
        rows = []
        for p in places:
            name = p.get("name", "")
            typ = p.get("type", "")
            ctx = f" – {html.escape(typ)}" if typ else ""
            maps = _a("Maps", f"https://www.google.com/maps/search/{_q(name)}")
            google = _a("Google", f"https://www.google.com/search?q={_q(name)}")
            rows.append(f"• <i>{html.escape(name)}</i>{ctx} → {maps} | {google}")
        _cat("PLACES", rows)

    books = entities.get("books") or []
    if books:
        rows = []
        for b in books:
            title = b.get("title", "")
            author = b.get("author", "")
            raw_q = f"{title} by {author}" if author else title
            ctx = f" by {html.escape(author)}" if author else ""
            goodreads = _a("Goodreads", f"https://www.goodreads.com/search?q={_q(title)}")
            google = _a("Google", f"https://www.google.com/search?q={_q(raw_q)}")
            rows.append(f"• <i>{html.escape(title)}</i>{ctx} → {goodreads} | {google}")
        _cat("BOOKS", rows)

    movies_tv = entities.get("movies_tv") or []
    if movies_tv:
        rows = []
        for m in movies_tv:
            title = m.get("title", "")
            imdb = _a("IMDb", f"https://www.imdb.com/find?q={_q(title)}")
            google = _a("Google", f"https://www.google.com/search?q={_q(title)}")
            rows.append(f"• <i>{html.escape(title)}</i> → {imdb} | {google}")
        _cat("MOVIES & TV", rows)

    fashion = entities.get("fashion") or []
    if fashion:
        rows = []
        for f in fashion:
            brand = f.get("brand", "")
            google = _a("Google", f"https://www.google.com/search?q={_q(brand)}")
            rows.append(f"• <i>{html.escape(brand)}</i> → {google}")
        _cat("FASHION", rows)

    knitting = entities.get("knitting") or []
    if knitting:
        rows = []
        for k in knitting:
            pattern = k.get("pattern", "")
            creator = k.get("creator", "")
            ctx = f" by {html.escape(creator)}" if creator else ""
            ravelry = _a("Ravelry", f"https://www.ravelry.com/search#query={_q(pattern)}")
            google = _a("Google", f"https://www.google.com/search?q={_q(pattern)}")
            rows.append(f"• <i>{html.escape(pattern)}</i>{ctx} → {ravelry} | {google}")
        _cat("KNITTING", rows)

    beauty = entities.get("beauty_skincare") or []
    if beauty:
        rows = []
        for b in beauty:
            product = b.get("product", "")
            brand = b.get("brand", "")
            ctx = f" by {html.escape(brand)}" if brand else ""
            raw_q = f"{product} by {brand}" if brand else product
            google = _a("Google", f"https://www.google.com/search?q={_q(raw_q)}")
            rows.append(f"• <i>{html.escape(product)}</i>{ctx} → {google}")
        _cat("BEAUTY & SKINCARE", rows)

    health_products = entities.get("health_products") or []
    if health_products:
        rows = []
        for h in health_products:
            name = h.get("name", "")
            typ = h.get("type", "")
            price = h.get("price", "")
            ctx_parts = []
            if typ:
                ctx_parts.append(html.escape(typ))
            if price:
                ctx_parts.append(html.escape(price))
            ctx = " – " + ", ".join(ctx_parts) if ctx_parts else ""
            google = _a("Google", f"https://www.google.com/search?q={_q(name)}")
            rows.append(f"• <i>{html.escape(name)}</i>{ctx} → {google}")
        _cat("💊 HEALTH PRODUCTS", rows)

    websites = entities.get("websites") or []
    if websites:
        rows = []
        for w in websites:
            name = w.get("name", "")
            url = w.get("url", "")
            if url:
                rows.append(f"• <i>{html.escape(name)}</i> → {_a(url, url)}")
            else:
                rows.append(f"• <i>{html.escape(name)}</i>")
        _cat("WEBSITES", rows)

    ai_terms = entities.get("ai_terms") or []
    if ai_terms:
        rows = []
        for a in ai_terms:
            term = a.get("term", "")
            explanation = a.get("explanation", "")
            ctx = f" – {html.escape(explanation)}" if explanation else ""
            google = _a("Google", f"https://www.google.com/search?q={_q(term)}")
            rows.append(f"• <i>{html.escape(term)}</i>{ctx} → {google}")
        _cat("AI TERMS", rows)

    social = [s for s in (entities.get("social_handles") or [])
              if "bot" not in (s.get("handle") or "").lower()]
    if social:
        rows = []
        for s in social:
            h = s.get("handle", "")
            if h and not h.startswith("@"):
                h = f"@{h}"
            google = _a("Google", f"https://www.google.com/search?q={_q(h)}")
            rows.append(f"• <i>{html.escape(h)}</i> → {google}")
        _cat("SOCIAL HANDLES", rows)

    other = (entities.get("other") or [])[:3]
    if other:
        rows = []
        for o in other:
            entity = o.get("entity", "")
            google = _a("Google", f"https://www.google.com/search?q={_q(entity)}")
            rows.append(f"• <i>{html.escape(entity)}</i> → {google}")
        _cat("OTHER", rows)

    if cat_blocks:
        sections.append(_section("🔍 EXTRACTED", ["\n\n".join(cat_blocks)]))

    # --- 4. FOLDER & TAGS ---
    extra_tags = [
        t.strip().replace("-", "_").lower()
        for t in (tags.get("extra") or [])
        if t.strip()
    ]
    extra_tags = [t if t.startswith("#") else f"#{t}" for t in extra_tags]

    ft_body = [html.escape(folder_str)]
    for i, tag in enumerate(extra_tags):
        connector = "└─" if i == len(extra_tags) - 1 else "├─"
        ft_body.append(f"{connector} {html.escape(tag)}")
    sections.append(_section("📁 FOLDER & TAGS", ft_body))

    return "\n\n".join(sections).strip()


def extract_db_fields(result: dict) -> dict:
    summary = result.get("summary") or {}
    if isinstance(summary, dict):
        summary_str = f"{summary.get('what', '')} {summary.get('details', '')}".strip()
    else:
        summary_str = str(summary)

    tags = result.get("tags") or {}
    folder = _fmt_folder(tags).lstrip("#")
    tags_str = _fmt_tags(tags)  # extra only, no category

    return {
        "summary": summary_str,
        "tags": tags_str,
        "folder": folder,
        "fact_check": result.get("fact_check", ""),
        "enrichment": json.dumps(result.get("entities") or {}),
        "title": result.get("title", ""),
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def process_images(image_list: list[tuple[bytes, str]], caption: str = "") -> dict:
    raw_descs = []
    for img, mime in image_list:
        raw_descs.append(await _describe_image(img, mime))

    # Deduplicate repeated lines when 3+ images (same product appearing in every shot)
    if len(raw_descs) >= 3:
        line_counts: dict[str, int] = {}
        for desc in raw_descs:
            seen = set()
            for line in desc.split("\n"):
                key = line.strip().lower()
                if key and key not in seen:
                    line_counts[key] = line_counts.get(key, 0) + 1
                    seen.add(key)
        repeated = {k for k, v in line_counts.items() if v >= 3}
        if repeated:
            seen_repeated: set[str] = set()
            deduped = []
            for desc in raw_descs:
                lines = []
                for line in desc.split("\n"):
                    key = line.strip().lower()
                    if key in repeated:
                        if key not in seen_repeated:
                            lines.append(line)
                            seen_repeated.add(key)
                    else:
                        lines.append(line)
                deduped.append("\n".join(lines))
            raw_descs = deduped

    descriptions = [f"-- image_{i} --\n{desc}" for i, desc in enumerate(raw_descs, 1)]
    content = "\n\n".join(descriptions)
    if caption:
        content = f"Caption: {caption}\n\n{content}"
    analysis = await _analyze(content)
    analysis["raw_content"] = content
    return analysis


async def process_text(text: str) -> dict:
    analysis = await _analyze(text)
    analysis.pop("transcription", None)
    analysis["raw_content"] = text
    return analysis


async def process_video(video_bytes: bytes, duration: int = 0) -> dict:
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

    content_parts = []
    if transcript:
        content_parts.append(f"-- video --\n{transcript}")
    for frame_bytes, ts_sec in frames:
        desc = await _describe_frame(frame_bytes)
        if len(desc.strip()) >= 10:  # skip empty / UI-only frames
            content_parts.append(f"-- {ts_sec} --\n{desc}")

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
