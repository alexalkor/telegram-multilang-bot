import asyncio
import logging
from deep_translator import GoogleTranslator

logger = logging.getLogger(__name__)

SOURCE_LANG = "ru"
CHUNK_SIZE  = 4500


def _chunk(text: str) -> list[str]:
    chunks = []
    while len(text) > CHUNK_SIZE:
        split_at = text.rfind("\n", 0, CHUNK_SIZE)
        if split_at == -1:
            split_at = CHUNK_SIZE
        chunks.append(text[:split_at])
        text = text[split_at:].lstrip("\n")
    if text:
        chunks.append(text)
    return chunks


def _translate_sync(text: str, target_lang: str) -> str | None:
    """Translate text. Returns None on failure (caller decides fallback)."""
    if target_lang == SOURCE_LANG or not text.strip():
        return text
    try:
        translator = GoogleTranslator(source=SOURCE_LANG, target=target_lang)
        chunks = _chunk(text)
        translated = [translator.translate(chunk) or chunk for chunk in chunks]
        return "\n".join(translated)
    except Exception as e:
        logger.warning("Translation to %s failed: %s", target_lang, e)
        return None


async def translate(text: str, target_lang: str) -> str | None:
    """Async wrapper. Returns None if translation failed."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _translate_sync, text, target_lang)
