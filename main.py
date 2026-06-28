import asyncio
import logging
import os

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from config.settings import BOT_TOKEN, WEBHOOK_SECRET, PORT
from database.db import init_db, replace_current_week_events, append_to_week_events, get_latest_events, clear_all_translations, save_translation
from database.github_storage import fetch_events, fetch_events_data, save_events_data
from handlers import start, help, language, menu, admin

logger = logging.getLogger(__name__)

VERSION = "v16-reorder-batch"


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
            latest = await get_latest_events()
            full_text = latest[0]["text"] if latest else stored_text
        else:
            event_id = await replace_current_week_events(stored_text)
            full_text = stored_text

        # Save raw to GitHub immediately (no translations yet)
        gh_status, gh_msg = await save_events_data(full_text, {})
        logger.info("Event #%d raw saved; GitHub: %d %s", event_id, gh_status, gh_msg[:80])

        # Translate all languages in the background (takes 30-60s, don't block response)
        import asyncio as _asyncio
        _asyncio.create_task(_bg_translate(event_id, full_text))

        return web.json_response({
            "ok": True, "event_id": event_id, "mode": mode,
            "github_status": gh_status,
            "note": "translation started in background",
        })
    except Exception as e:
        logger.exception("Error in /events endpoint")
        return web.json_response({"ok": False, "error": str(e)}, status=500)


async def handle_test_translate(request: web.Request) -> web.Response:
    """Translate the actual DB events to verify MyMemory works on real content."""
    from utils.translator import translate
    events = await get_latest_events()
    if not events:
        return web.json_response({"error": "no events in db"})
    text = events[0]["text"]
    results = {}
    for lang in ["en", "pl"]:
        res = await translate(text, lang)
        results[lang] = {
            "ok": res is not None and res != text,
            "preview": (res or "")[:200],
        }
    return web.json_response({
        "text_len": len(text),
        "text_preview": text[:300],
        "results": results,
    })


async def _bg_translate(event_id: int, text: str) -> None:
    """Background task: translate to all langs, cache in DB + GitHub."""
    import asyncio as _asyncio
    from utils.translator import translate
    langs = ["en", "pl", "de", "be", "uk"]
    translations: dict = {}
    for lang in langs:
        try:
            result = await translate(text, lang)
            if result and result != text:
                await save_translation(event_id, lang, result)
                translations[lang] = result
                logger.info("BG translated %s (%d chars)", lang, len(result))
            else:
                logger.warning("BG translation failed for %s", lang)
        except Exception as e:
            logger.warning("BG translation error for %s: %s", lang, e)
        await _asyncio.sleep(2)  # spread load, avoid rate limits
    # Persist all translations to GitHub
    events = await get_latest_events()
    if events and events[0]["id"] == event_id:
        await save_events_data(text, translations)
        logger.info("BG: saved %d translations to GitHub", len(translations))


async def handle_clear_cache(request: web.Request) -> web.Response:
    """Wipe all cached translations so they get re-fetched on next request."""
    secret = request.headers.get("X-Secret", "")
    if not WEBHOOK_SECRET or secret != WEBHOOK_SECRET:
        return web.Response(status=401, text="Unauthorized")
    count = await clear_all_translations()
    logger.info("Cleared %d cached translations via HTTP", count)
    return web.json_response({"ok": True, "cleared": count})


async def handle_health(request: web.Request) -> web.Response:
    return web.Response(text=f"ok ({VERSION})")


async def handle_debug(request: web.Request) -> web.Response:
    pat = os.getenv("GITHUB_PAT", "")
    events = await get_latest_events()
    cyrillic_test = "1. 🎭 Тест\n📍 Варшава\n🕐 Сегодня\n💰 100 зл"
    gh_status, gh_msg = await save_events_data(cyrillic_test, {})
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
        data = await fetch_events_data()
        if data:
            eid = await replace_current_week_events(data["raw"])
            for lang, txt in data.get("translations", {}).items():
                await save_translation(eid, lang, txt)
            logger.info("Seeded from GitHub — event #%d with %d translations",
                        eid, len(data.get("translations", {})))
        else:
            text = await fetch_events()
            if text:
                eid = await replace_current_week_events(text)
                logger.info("Seeded from GitHub legacy txt — event #%d", eid)

    app = web.Application()
    app.router.add_get("/health", handle_health)
    app.router.add_get("/debug",  handle_debug)
    app.router.add_post("/events", handle_post_events)
    app.router.add_post("/admin/clear-cache", handle_clear_cache)
    app.router.add_get("/test-translate", handle_test_translate)
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
