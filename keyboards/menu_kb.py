from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from utils.i18n import t


def menu_keyboard(lang: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=t(lang, "btn_current_week"), callback_data="menu:current_week")
    builder.button(text=t(lang, "btn_prev_week"),    callback_data="menu:prev_week")
    builder.button(text=t(lang, "btn_change_lang"),  callback_data="menu:change_lang")
    builder.button(text=t(lang, "btn_stop"),         callback_data="menu:stop")
    builder.adjust(2, 2)
    return builder.as_markup()
