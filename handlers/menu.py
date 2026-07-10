from aiogram import Router, F
from aiogram.types import CallbackQuery

import asyncio
import logging

from database.db import get_language, get_latest_events, get_translation, save_translation
from database.github_storage import fetch_events_data, save_events_data
from keyboards.language_kb import language_keyboard
from keyboards.menu_kb import menu_keyboard
from utils.i18n import t
from utils.translator import translate, SOURCE_LANG

router = Router()
logger = logging.getLogger(__name__)

BATCH_SIZE = 10
MAX_MSG = 4090

def _parse_events(text: str) -> tuple[str | None, list[str]]:
    """Split blob into (date_range_or_None, [event_items]).
    Splits only on boundaries between numbered events (N. ...) so that
    internal blank lines within one event are preserved as single newlines.
    """
    import re
    first_split = text.split("\n\n", 1)
    if len(first_split) == 2 and not re.match(r"^\d+\.\s", first_split[0].strip()):
        date_range = first_split[0].strip()
        body = first_split[1]
    else:
        date_range = None
        body = text
    if date_range is None and "\n" in body:
        first_line_split = body.split("\n", 1)
        if len(first_line_split) == 2 and not re.match(r"^\d+\.\s", first_line_split[0].strip()):
            if len(first_line_split[0].strip()) < 30:
                date_range = first_line_split[0].strip()
                body = first_line_split[1].lstrip("\n")
    items = re.split(r"\n+(?=\d+\.\s)", body)
    items = [item.replace("\n\n", "\n").strip() for item in items if item.strip()]
    return date_range, items

def _chunk_items(items: list[str], max_len: int = MAX_MSG, max_count: int = BATCH_SIZE) -> list[str]:
    """Group items into messages of up to max_count items each, but never
    let a message exceed Telegram's character limit even if that means
    fewer than max_count items in a given message."""
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0
    for item in items:
        item_len = len(item) + 2  # account for the joiner
        would_overflow_len = current and current_len + item_len > max_len
        would_overflow_count = len(current) >= max_count
        if current and (would_overflow_len or would_overflow_count):
            chunks.append("\n\n".join(current))
            current = []
            current_len = 0
        current.append(item)
        current_len += item_len
    if current:
        chunks.append("\n\n".join(current))
    return chunks

async def _persist_lang_to_github(lang: str, translated: str) -> None:
    """Add a lazily-computed translation to the GitHub JSON backup."""
    try:
        data = await fetch_events_data()
        if data:
            data["translations"][lang] = translated
            await save_events_data(data["raw"], data["translations"])
    except Exception as e:
        logging.getLogger(__name__).warning("Failed to persist %s translation to GitHub: %s", lang, e)

async def send_latest_events(callback: CallbackQuery, lang: str) -> None:
    events = await get_latest_events()
    if not events:
        await callback.answer(t(lang, "no_events"), show_alert=True)
        return

    for event in events:
        translated = await get_translation(event["id"], lang)

        if translated is None:
            result = await translate(event["text"], lang)
            if result is not None:
                translated = result
                await save_translation(event["id"], lang, result)
                asyncio.create_task(_persist_lang_to_github(lang, result))
            else:
                translated = event["text"]

        date_range, items = _parse_events(translated)

        if date_range:
            header = f"📅 <b>Latest events in Warsaw:</b>\n{date_range}"
        else:
            header = "📅 <b>Latest events in Warsaw:</b>"
        try:
            await callback.message.answer(header)
        except Exception:
            logger.exception("Failed to send events header")

        if not items:
            logger.warning("No parsed items for event #%s (lang=%s)", event["id"], lang)

        # Batch by item count (BATCH_SIZE) capped by char length, so we
        # never exceed Telegram's message limit even on long events
        for chunk in _chunk_items(items, MAX_MSG, BATCH_SIZE):
            try:
                await callback.message.answer(chunk)
            except Exception:
                logger.exception("Failed to send an events batch for event #%s (lang=%s)", event["id"], lang)

        try:
            await callback.message.answer(t(lang, "events_footer"))
        except Exception:
            logger.exception("Failed to send events footer")

@router.callback_query(F.data == "menu:events")
async def cb_events(callback: CallbackQuery) -> None:
    lang = await get_language(callback.from_user.id) or "en"
    await send_latest_events(callback, lang)
    await callback.message.answer(t(lang, "choose_action"), reply_markup=menu_keyboard(lang))
    await callback.answer()

@router.callback_query(F.data == "menu:change_lang")
async def cb_change_lang(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        "🌐 Choose your language:",
        reply_markup=language_keyboard(),
    )
    await callback.answer()

@router.callback_query(F.data == "menu:stop")
async def cb_stop(callback: CallbackQuery) -> None:
    lang = await get_language(callback.from_user.id) or "en"
    await callback.message.edit_text(t(lang, "stopped"))
    await callback.answer()
