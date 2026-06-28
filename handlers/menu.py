from aiogram import Router, F
from aiogram.types import CallbackQuery

import asyncio

from database.db import get_language, get_latest_events, get_translation, save_translation
from database.github_storage import fetch_events_data, save_events_data
from keyboards.language_kb import language_keyboard
from keyboards.menu_kb import menu_keyboard
from utils.i18n import t
from utils.translator import translate, SOURCE_LANG

router = Router()

BATCH_SIZE = 10
MAX_MSG    = 4090


def _parse_events(text: str) -> tuple[str | None, list[str]]:
    """Split blob into (date_range_or_None, [event_items]).
    Splits only on boundaries between numbered events (N. ...) so that
    internal blank lines within one event are preserved as single newlines.
    """
    import re
    # Detect date range: first paragraph if it does NOT start with "N. "
    first_split = text.split("\n\n", 1)
    if len(first_split) == 2 and not re.match(r"^\d+\.\s", first_split[0].strip()):
        date_range = first_split[0].strip()
        body = first_split[1]
    else:
        date_range = None
        body = text
    # Split body only where a new numbered event begins (\n\n followed by digit+dot)
    items = re.split(r"\n\n(?=\d+\.\s)", body)
    # Collapse any remaining internal double-newlines → single newline
    items = [item.replace("\n\n", "\n").strip() for item in items if item.strip()]
    return date_range, items


async def _persist_lang_to_github(lang: str, translated: str) -> None:
    """Add a lazily-computed translation to the GitHub JSON backup."""
    try:
        data = await fetch_events_data()
        if data:
            data["translations"][lang] = translated
            await save_events_data(data["raw"], data["translations"])
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("Failed to persist %s translation to GitHub: %s", lang, e)


async def send_latest_events(callback: CallbackQuery, lang: str) -> None:
    events = await get_latest_events()
    if not events:
        await callback.answer(t(lang, "no_events"), show_alert=True)
        return

    for event in events:
        # Try cached translation first
        translated = await get_translation(event["id"], lang)

        if translated is None:
            result = await translate(event["text"], lang)
            if result is not None:
                # Successful translation — cache in DB and persist to GitHub
                translated = result
                await save_translation(event["id"], lang, translated)
                asyncio.create_task(_persist_lang_to_github(lang, result))
            else:
                # Translation failed — use original Russian, don't cache
                translated = event["text"]

        date_range, items = _parse_events(translated)

        if date_range:
            header = f"📅 <b>Latest events in Warsaw:</b>\n{date_range}"
        else:
            header = "📅 <b>Latest events in Warsaw:</b>"
        await callback.message.answer(header)

        # Adaptive batching — accumulate items until next one won't fit, then send
        current: list[str] = []
        current_len = 0
        for item in items:
            added = (2 if current else 0) + len(item)
            if current and current_len + added > MAX_MSG:
                await callback.message.answer("\n\n".join(current))
                current = [item]
                current_len = len(item)
            else:
                current.append(item)
                current_len += added
        if current:
            await callback.message.answer("\n\n".join(current))


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
