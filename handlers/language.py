from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery

from database.db import get_language, set_language
from keyboards.language_kb import language_keyboard
from keyboards.menu_kb import menu_keyboard
from utils.i18n import t

router = Router()


@router.message(Command("language"))
async def cmd_language(message: Message) -> None:
    await message.answer(
        "🌐 Choose your language:",
        reply_markup=language_keyboard(),
    )


@router.callback_query(F.data.startswith("lang:"))
async def cb_language(callback: CallbackQuery) -> None:
    lang = callback.data.split(":")[1]
    user_id = callback.from_user.id

    await set_language(user_id, lang)

    # Confirm in same message, then send menu
    await callback.message.edit_text(t(lang, "language_set"))
    await callback.message.answer(t(lang, "choose_action"), reply_markup=menu_keyboard(lang))
    await callback.answer()
