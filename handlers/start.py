from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from database.db import get_language
from keyboards.language_kb import language_keyboard
from keyboards.menu_kb import menu_keyboard
from utils.i18n import t

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    lang = aw