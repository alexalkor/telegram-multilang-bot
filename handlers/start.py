from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from keyboards.language_kb import language_keyboard

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await message.answer(
        "👋 Please choose your language:",
        reply_markup=language_keyboard(),
    )
