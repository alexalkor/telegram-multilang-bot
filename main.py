import asyncio
import logging
import os

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from config.settings import BOT_TOKEN, WEBHOOK_SECRET, PORT
from database.db import init_db, replace_current_week_events, get_latest_events
from database.github_storage import fetch_events, save_events
from handlers import start, help, language, menu, admin

logger = logging.getLogger(__name__)


async def handle_post_events(request: web.Request) -> web.Response:
    """HTTP endpoint for the scraper to upload fresh events."""
    secret = request.headers.get("X-Secret", "")
    if not WEBHOOK_SECRET or secret != WEBHOOK_SECRET:
        return web.Response(status=401, text="Unauthorized")
    try:
        data = await request.json()
        text = data.get("text", "").strip()
        if not text:
            return web.json_response({"ok": False, "error": "empty text"}, status=400)
        event_id = await replace_current_week_events(text)
        logger.info("Events replaced via HTTP — new event #%d", event_id)
        # Persist to GitHub — await ensures save completes before responding
        await save_events(text)
        return web.json_response({"ok": True, "event_id": event_id})
    except Exception as e:
        logger.exception("Error in /events endpoint")
        return web.json_response({"ok": False, "error": str(e)}, status=500)


async def handle_health(request: web.Request) -> web.Response:
    return web.Response(text="ok")


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    await init_db()

    # Seed DB from GitHub if empty (e.g. after a redeploy)
    existing = await get_latest_events()
    if not existing:
        logger.info("DB empty — attempting to seed from GitHub...")
        text = await fetch_events()
        if text:
            eid = await replace_current_week_events(text)
            logger.info("Seeded DB from GitHub — event #%d", eid)
        else:
            logger.info("No events in GitHub storage yet")

    # ── HTTP server ──────────────────────────────────────────────────────────
    app = web.Application()
    app.router.add_get("/health", handle_health)
    app.router.add_post("/events", handle_post_events)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logger.info("HTTP server listening on port %d", PORT)

    # ── Telegram bot ─────────────────────────────────────────────────────────
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()

    dp.include_router(start.router)
    dp.include_router(language.router)
    dp.include_router(menu.router)
    dp.include_router(help.router)
    dp.include_router(admin.router)

    try:
        await dp.start_polling(bot, allowed_updates=["message", "callback_query"])
    finally:
        await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
