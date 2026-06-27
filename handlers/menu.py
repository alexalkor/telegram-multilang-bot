from aiogram import Router, F
from aiogram.types import CallbackQuery

from database.db import get_language, get_latest_events, get_translation, save_translation
from keyboards.language_kb import language_keyboard
from keyboards.menu_kb import menu_keyboard
from utils.i18n import t
from utils.translator import translate

router = Router()

BATCH_SIZE = 10
MAX_MSG    = 4090


def _parse_events(text: str) -> tuple[str | None, list[str]]:
    """Split stored events blob into (date_range_or_None, [event_items]).

    The first paragraph is treated as a date range if it does NOT start
    with a digit (i.e. it's not a numbered event like '1. 🎭 ...').
    """
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if not paragraphs:
        return None, []
    if paragraphs[0][:1].isdigit():
        return None, paragraphs          # no date-range prefix
    return paragraphs[0], paragraphs[1:] # first block is date range


async def send_latest_events(callback: CallbackQuery, lang: str) -> None:
    """Fetch and send the latest events in the user's language."""
    events = await get_latest_events()
    if not events:
        await callback.answer(t(lang, "no_events"), show_alert=True)
        return

    for event in events:
        # Get or build the translated blob
        translated = await get_translation(event["id"], lang)
        if translated is None:
            translated = await translate(event["text"], lang)
            await save_translation(event["id"], lang, translated)

        date_range, items = _parse_events(translated)

        # Message 1 — header with date range
        if date_range:
            header = f"📅 <b>Latest events in Warsaw:</b>\n{date_range}"
        else:
            header = "📅 <b>Latest events in Warsaw:</b>"
        await callback.message.answer(header)

        # Messages 2+ — batches of up to 10 events joined by double newline
        for i in range(0, len(items), BATCH_SIZE):
            batch = items[i : i + BATCH_SIZE]
            text_out = "\n\n".join(batch)
            if len(text_out) > MAX_MSG:
                text_out = text_out[:MAX_MSG - 3] + "..."
            await callback.message.answer(text_out)


@router.callback_query(F.data == "menu:events")
async def cb_events(callback: CallbackQuery) -> None:
    lang = await get_language(callback.from_user.id) or "en"
    await send_latest_events(callback, lang)
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
