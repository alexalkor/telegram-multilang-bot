from aiogram import Router, F
from aiogram.types import CallbackQuery

from database.db import get_language, get_latest_events, get_translation, save_translation
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
                # Successful translation — cache it
                translated = result
                await save_translation(event["id"], lang, translated)
            else:
                # Translation failed — use original Russian, don't cache
                translated = event["text"]

        date_range, items = _parse_events(translated)

        if date_range:
            header = f"📅 <b>Latest events in Warsaw:</b>\n{date_range}"
        else:
            header = "📅 <b>Latest events in Warsaw:</b>"
        await callback.message.answer(header)

        for i in range(0, len(items), BATCH_SIZE):
            batch = items[i : i + BATCH_SIZE]
            # Collapse internal double-newlines within each item (scraper uses \n\n
            # between title and description inside one event)
            text_out = "\n\n".join(batch)
            if len(text_out) > MAX_MSG:
                text_out = text_out[:MAX_MSG - 3] + "..."
            await callback.message.answer(text_out)


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
