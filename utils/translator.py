import asyncio
import logging
from deep_translator import GoogleTranslator

logger = logging.getLogger(__name__)

# Languages the channel posts in (source)
SOURCE_LANG = "ru"

# Max chars per Google Translate request
CHUNK_SIZE = 4500


def _chunk(text: str) -> list[str]:
    """Split text into chunks that fit within Google Translate's limit."""
    chunks = []
    while len(text) > CHUNK_SIZE:
        # Try to split at a newline near the limit
        split_at = text.rfind("\n", 0, CHUNK_SIZE)
        if split_at == -1:
            split_at = CHUNK_SIZE
        chunks.append(text[:split_at])
        text = text[split_at:].lstrip("\n")
    if text:
        chunks.append(text)
    return chunks


def _translate_sync(text: str, target_lang: str) -> str:
    """Synchronous translation with chunking and fallback."""
    if target_lang == SOURCE_LANG or not text.strip():
        return text
    try:
        translator = GoogleTranslator(source=SOURCE_LANG, target=target_lang)
        chunks = _chunk(text)
        translated = [translator.translate(chunk) or chunk for chunk in chunks]
        return "\n".join(translated)
    except Exception as e:
        logger.warning(f"Translation to {target_lang} failed: {e}. Returning original.")
        return text


async def translate(text: str, target_lang: str) -> str:
    """Async wrapper around synchronous Google Translate call."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _translate_sync, text, target_lang)
