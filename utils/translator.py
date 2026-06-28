import logging
import aiohttp

logger = logging.getLogger(__name__)

SOURCE_LANG = "ru"
CHUNK_SIZE  = 2000   # Google Translate handles up to ~5000 chars comfortably

# Google Translate lang codes (mostly the same as ISO 639-1)
_GT_CODES = {
    "ru": "ru",
    "en": "en",
    "pl": "pl",
    "de": "de",
    "be": "be",
    "uk": "uk",
}


def _chunk(text: str, size: int = CHUNK_SIZE) -> list[str]:
    chunks = []
    while len(text) > size:
        split_at = text.rfind("\n", 0, size)
        if split_at == -1:
            split_at = size
        chunks.append(text[:split_at])
        text = text[split_at:].lstrip("\n")
    if text:
        chunks.append(text)
    return chunks


async def _translate_chunk(session: aiohttp.ClientSession, chunk: str, src: str, tgt: str) -> str:
    """Translate a single chunk via Google Translate unofficial API."""
    url = (
        f"https://translate.googleapis.com/translate_a/single"
        f"?client=gtx&sl={src}&tl={tgt}&dt=t&q={aiohttp.helpers.requote_uri(chunk)}"
    )
    async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
        if resp.status != 200:
            logger.warning("Google Translate chunk failed: HTTP %s", resp.status)
            return ""
        data = await resp.json(content_type=None)
    # data[0] is list of [translated, original, ...] pairs
    if not data or not data[0]:
        return ""
    return "".join(item[0] for item in data[0] if item and item[0])


async def translate(text: str, target_lang: str) -> str | None:
    """Translate text from Russian to target_lang.
    Returns translated string on success, None on failure (caller must not cache None)."""
    if target_lang == SOURCE_LANG or not text.strip():
        return text

    src = _GT_CODES.get(SOURCE_LANG, SOURCE_LANG)
    tgt = _GT_CODES.get(target_lang, target_lang)
    chunks = _chunk(text)

    try:
        import asyncio as _asyncio
        async with aiohttp.ClientSession() as session:
            results = []
            for i, chunk in enumerate(chunks):
                if i > 0:
                    await _asyncio.sleep(0.3)
                translated = await _translate_chunk(session, chunk, src, tgt)
                if not translated:
                    logger.warning("Google Translate: empty chunk result, aborting %s->%s", src, tgt)
                    return None
                results.append(translated)
        result = "\n".join(results)
        logger.info("Google Translate OK: %s->%s (%d->%d chars)", src, tgt, len(text), len(result))
        return result
    except Exception as e:
        logger.warning("Google Translate failed (%s->%s): %s", src, tgt, e)
        return None
