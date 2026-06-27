import asyncio
import logging
import os

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from config.settings import BOT_TOKEN, WEBHOOK_SECRET, PORT
from database.db import init_db, replace_current_week_events, append_to_week_events, get_latest_events
from database.github_storage import fetch_events, save_events
from handlers import start, help, language, menu, admin

logger = logging.getLogger(__name__)

VERSION = "v7-textpreview"


async def handle_post_events(request: web.Request) -> web.Response:
    secret = request.headers.get("X-Secret", "")
    if not WEBHOOK_SECRET or secret != WEBHOOK_SECRET:
        return web.Response(status=401, text="Unauthorized")
    try:
        data = await request.json()
        text = data.get("text", "").strip()
        if not text:
            return web.json_response({"ok": False, "error": "empty text"}, status=400)
        date_range = data.get("date_range", "").strip()
        stored_text = f"{date_range}\n\n{text}" if date_range else text
        mode = data.get("mode", "replace")
        if mode == "append":
            event_id = await append_to_week_events(stored_text)
            # Re-read the merged text to persist full blob to GitHub
            latest = await get_latest_events()
            full_text = latest[0]["text"] if latest else stored_text
            gh_status, gh_msg = await save_events(full_text)
        else:
            event_id = await replace_current_week_events(stored_text)
            gh_status, gh_msg = await save_events(stored_text)
        logger.info("Event #%d saved (mode=%s); GitHub: %d %s", event_id, mode, gh_status, gh_msg[:80])
        return web.json_response({"ok": True, "event_id": event_id, "mode": mode,
                                  "github_status": gh_status, "github_msg": gh_msg[:200]})
    except Exception as e:
        logger.exception("Error in /events endpoint")
        return web.json_response({"ok": False, "error": str(e)}, status=500)


async def handle_health(request: web.Request) -> web.Response:
    return web.Response(text=f"ok ({VERSION})")


async def handle_debug(request: web.Request) -> web.Response:
    pat = os.getenv("GITHUB_PAT", "")
    events = await get_latest_events()
    cyrillic_test = "1. 🎭 Тест\n📍 Варшава\n🕐 Сегодня\n💰 100 зл"
    gh_status, gh_msg = await save_events(cyrillic_test)
    return web.json_response({
        "version": VERSION,
        "GITHUB_PAT_set": bool(pat),
        "GITHUB_PAT_prefix": pat[:8] + "..." if pat else "(empty)",
        "events_in_db": len(events),
        "github_cyrillic_test": {"status": gh_status, "msg": gh_msg[:200]},
    })


async def main() -> None:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    await init_db()

    existing = await get_latest_events()
    if not existing:
        logger.info("DB empty — seeding from GitHub...")
        text = await fetch_events()
        if text:
            eid = await replace_current_week_events(text)
            logger.info("Seeded from GitHub — event #%d", eid)

    app = web.Application()
    app.router.add_get("/health", handle_health)
    app.router.add_get("/debug",  handle_debug)
    app.router.add_post("/events", handle_post_events)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logger.info("HTTP server on port %d (%s)", PORT, VERSION)

    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
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
