from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

LANGUAGES = [
    ("🇺🇸 English", "en"),
    ("🇵🇱 Polski", "pl"),
    ("🇷🇺 Русский", "ru"),
    ("🇧🇾 Беларуская", "be"),
    ("🇺🇦 Українська", "uk"),
]


def language_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for label, code in LANGUAGES:
        builder.button(text=label, callback_data=f"lang:{code}")
    builder.adjust(2, 2, 1)  # 2 buttons / 2 buttons / 1 button
    return builder.as_markup()
