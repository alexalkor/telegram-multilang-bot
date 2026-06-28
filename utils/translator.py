import logging
import aiohttp

logger = logging.getLogger(__name__)

SOURCE_LANG = "ru"
CHUNK_SIZE  = 1500   # MyMemory actually truncates large outputs; 1500 keeps ~4 events per call
MYMEMORY_EMAIL = "bot@thewarsawevents.com"

_MYMEMORY_CODES = {
    "ru": "ru-RU",
    "en": "en-GB",
    "pl": "pl-PL",
    "de": "de-DE",
    "be": "be-BY",
    "uk": "uk-UA",
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


async def _translate_chunk(session: aiohttp.ClientSession, chunk: str, langpair: str) -> str:
    """Translate a single chunk via MyMemory API. Returns empty string on failure."""
    # Use POST to avoid URL length limit (Cyrillic text encodes to ~6x chars in URL)
    async with session.post(
        "https://api.mymemory.translated.net/get",
        data={"q": chunk, "langpair": langpair, "de": MYMEMORY_EMAIL},
        timeout=aiohttp.ClientTimeout(total=15),
    ) as resp:
        data = await resp.json(content_type=None)
    status = data.get("responseStatus", 0)
    result = data.get("responseData", {}).get("translatedText", "")
    if status == 200 and result:
        return result
    logger.warning("MyMemory chunk failed: status=%s result=%r", status, result[:80])
    return ""


async def translate(text: str, target_lang: str) -> str | None:
    """Translate text from Russian to target_lang.
    Returns translated string on success, None on failure (caller must not cache None)."""
    if target_lang == SOURCE_LANG or not text.strip():
        return text

    src = _MYMEMORY_CODES.get(SOURCE_LANG, SOURCE_LANG)
    tgt = _MYMEMORY_CODES.get(target_lang, target_lang)
    langpair = f"{src}|{tgt}"
    chunks = _chunk(text)

    try:
        import asyncio as _asyncio
        async with aiohttp.ClientSession() as session:
            results = []
            for i, chunk in enumerate(chunks):
                if i > 0:
                    await _asyncio.sleep(1)  # avoid rate-limiting between chunks
                translated = await _translate_chunk(session, chunk, langpair)
                if not translated:
                    logger.warning("MyMemory: empty chunk result, aborting %s->%s", SOURCE_LANG, target_lang)
                    return None
                results.append(translated)
        result = "\n".join(results)
        logger.info("MyMemory OK: %s->%s (%d->%d chars)", SOURCE_LANG, target_lang, len(text), len(result))
        return result
    except Exception as e:
        logger.warning("MyMemory failed (%s->%s): %s", SOURCE_LANG, target_lang, e)
        return None
