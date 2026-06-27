from aiogram import Router, F
from aiogram.types import CallbackQuery

from database.db import get_language, get_latest_events, get_translation, save_translation
from keyboards.language_kb import language_keyboard
from keyboards.menu_kb import menu_keyboard
from utils.i18n import t
from utils.translator import translate

router = Router()


async def send_latest_events(callback: CallbackQuery, lang: str) -> None:
    """Fetch and send the latest events in the user's language."""
    events = await get_latest_events()
    if not events:
        await callback.answer(t(lang, "no_events"), show_alert=True)
        return

    await callback.message.answer(t(lang, "events_header"))

    for event in events:
        text = await get_translation(event["id"], lang)
        if text is None:
            text = await translate(event["text"], lang)
            await save_translation(event["id"], lang, text)
        await callback.message.answer(text)


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
