import logging
from datetime import datetime

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message

from config.settings import ADMIN_USER_ID
from database.db import save_event, get_language
from keyboards.menu_kb import menu_keyboard
from utils.i18n import t

router = Router()
logger = logging.getLogger(__name__)


def _current_week_year() -> tuple[int, int]:
    iso = datetime.now().isocalendar()
    return iso[1], iso[0]


@router.message(Command("myid"))
async def cmd_myid(message: Message) -> None:
    """Return the sender's Telegram user_id — useful for setting ADMIN_USER_ID."""
    await message.answer(f"Your Telegram user ID: <code>{message.from_user.id}</code>")


@router.message(F.text, F.from_user.id == ADMIN_USER_ID)
async def handle_admin_events(message: Message) -> None:
    """Any text message from the admin is saved as the current week's events."""
    if not message.text.strip():
        return

    week, year = _current_week_year()
    event_id = await save_event(week, year, message.text)
    logger.info(f"Admin saved event #{event_id} (week {week}/{year})")
    await message.reply(
        f"✅ Saved as event <b>#{event_id}</b> (week {week}/{year})\n"
        f"Users will now see this in their chosen language."
    )
