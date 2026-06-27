import logging
from datetime import datetime, timedelta

from aiogram import Router
from aiogram.types import Message

from database.db import save_event

router = Router()
logger = logging.getLogger(__name__)

CHANNEL_USERNAME = "thewarsawevents"


def _current_week_year() -> tuple[int, int]:
    iso = datetime.now().isocalendar()
    return iso[1], iso[0]  # week, year


@router.channel_post()
async def handle_channel_post(message: Message) -> None:
    """Store every post from @thewarsawevents in the database."""
    if message.chat.username != CHANNEL_USERNAME:
        return

    text = message.text or message.caption or ""
    if not text.strip():
        return

    week, year = _current_week_year()
    event_id = await save_event(week, year, text)
    logger.info(f"Stored channel post as event #{event_id} (week {week}/{year})")
