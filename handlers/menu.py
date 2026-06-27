from aiogram import Router, F
from aiogram.types import CallbackQuery

from database.db import get_language, get_events, get_translation, save_translation
from keyboards.language_kb import language_keyboard
from keyboards.menu_kb import menu_keyboard
from utils.i18n import t
from utils.translator import translate

router = Router()


async def _send_events(callback: CallbackQuery, week_offset: int) -> None:
    lang = await get_language(callback.from_user.id)
    events = await get_events(week_offset)

    if not events:
        key = "no_events_current" if week_offset == 0 else "no_events_prev"
        await callback.answer(t(lang, key), show_alert=True)
        return

    header_key = "events_header_current" if week_offset == 0 else "events_header_prev"
    await callback.message.answer(t(lang, header_key), parse_mode="HTML")

    for event in events:
        # Use cached translation if available
        text = await get_translation(event["id"], lang)
        if text is None:
            text = await translate(event["text"], lang)
            await save_translation(event["id"], lang, text)

        await callback.message.answer(text)

    await callback.answer()


@router.callback_query(F.data == "menu:current_week")
async def cb_current_week(callback: CallbackQuery) -> None:
    await _send_events(callback, week_offset=0)


@router.callback_query(F.data == "menu:prev_week")
async def cb_prev_week(callback: CallbackQuery) -> None:
    await _send_events(callback, week_offset=1)


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
