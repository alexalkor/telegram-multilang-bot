import asyncio
import logging
import re
from deep_translator import MyMemoryTranslator, GoogleTranslator

logger = logging.getLogger(__name__)

SOURCE_LANG = "ru"
CHUNK_SIZE  = 4500   # MyMemory limit is 5000; stay safe

# MyMemory uses different lang codes for some languages
_MYMEMORY_CODES = {
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


def _translate_sync(text: str, target_lang: str) -> str | None:
    """Translate text. Returns None on total failure."""
    if target_lang == SOURCE_LANG or not text.strip():
        return text

    src = _MYMEMORY_CODES.get(SOURCE_LANG, SOURCE_LANG)
    tgt = _MYMEMORY_CODES.get(target_lang, target_lang)

    # Primary: MyMemory (works on server IPs, free, no key needed)
    try:
        translator = MyMemoryTranslator(source=src, target=tgt)
        chunks = _chunk(text)
        translated = [translator.translate(c) or c for c in chunks]
        result = "\n".join(translated)
        logger.info("MyMemory: %s→%s (%d chars)", SOURCE_LANG, target_lang, len(text))
        return result
    except Exception as e:
        logger.warning("MyMemory failed (%s→%s): %s", SOURCE_LANG, target_lang, e)

    # Fallback: Google Translate
    try:
        translator = GoogleTranslator(source=SOURCE_LANG, target=target_lang)
        chunks = _chunk(text)
        translated = [translator.translate(c) or c for c in chunks]
        result = "\n".join(translated)
        logger.info("GoogleTranslator fallback: %s→%s", SOURCE_LANG, target_lang)
        return result
    except Exception as e:
        logger.warning("GoogleTranslator also failed (%s→%s): %s", SOURCE_LANG, target_lang, e)

    return None


async def translate(text: str, target_lang: str) -> str | None:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _translate_sync, text, target_lang)
