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

VERSION = "v31-emoji-only-house"



def _assign_emojis(text: str) -> str:
    """Replace generic 🏠 with content-appropriate emoji per event, based on Russian keywords."""
    import re
    # Ordered: first match wins. Keywords are lowercase substrings of the event title line.
    RULES = [
        (["стендап", "stand-up", "standup", "стэнд-ап", "stand up"],          "🎤"),
        (["свидани", "blind date"],                                             "💘"),
        (["варушняк", "varušniak", "kupalle", "купалье"],                      "🔥"),
        (["ночь купал", "купала на пляж"],                                     "🌊"),
        (["парусн", "регат", "флот wiślanej"],                                 "⛵"),
        (["wianki", "wianek", "gocławianki"],                                  "🌿"),
        (["nightskating", "найтскейтинг"],                                     "🛼"),
        (["indian summer"],                                                     "🪘"),
        (["итальянской кухн", "итальянск"],                                    "🍕"),
        (["стритфуда", "стритфуд", "street food"],                             "🍔"),
        (["антикварн"],                                                        "🏺"),
        (["танц"],                                                             "💃"),
        (["бассейн"],                                                          "🏊"),
        (["кино под открытым небом", "кинотеатр под"],                        "🎬"),
        (["vintage market", "винтаж маркет"],                                  "👗"),
        (["гаражная распродаж"],                                               "🛒"),
        (["ярмарка растений"],                                                 "🌱"),
        (["ярмарка завтрак"],                                                  "☕"),
        (["nocny market", "ночной маркет"],                                    "🌙"),
        (["прогулка по саду", "сад библиотек", "buw"],                        "🌸"),
        (["туристическ линии", "туристические лини"],                          "🚃"),
        (["фонтан", "wielkie serca"],                                          "⛲"),
        (["body worlds"],                                                      "🧠"),
        (["пикник"],                                                           "🧺"),
        (["уличного искусства", "стрит-арт"],                                 "🎨"),
        (["пивоварн", "browar"],                                               "🍺"),
        (["иммерсивн", "immersive", "lightshow", "light show", "genesis"],    "✨"),
        (["мультимедийн"],                                                     "🎭"),
        (["выставка", "экспозиц"],                                            "🖼"),
    ]

    def _pick_emoji(title_lower: str) -> str:
        for keywords, emoji in RULES:
            if any(kw in title_lower for kw in keywords):
                return emoji
        return "🏠"

    def _fix_line(m: "re.Match") -> str:
        num = m.group(1)
        title_lower = m.group(3).lower()
        emoji = _pick_emoji(title_lower)
        return f"{num}. {emoji} {m.group(3)}"

    # Match lines like "N. 🏠 Title..." — replace the emoji, keep title
    # Only replace generic 🏠 — leave scraper-assigned emojis untouched
    import re as _re
    def _fix(m):
        return f"{m.group(1)}. {_pick_emoji(m.group(2).lower())} {m.group(2)}"
    return _re.sub(r"^(\d+)\.\s+🏠\s+(.+)$", _fix, text, flags=_re.MULTILINE)

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

        # Apply content-appropriate emojis (replaces generic 🏠)
        full_text = _assign_emojis(full_text)

        # Preserve translations when same events re-posted; clear only on new content
        _existing = await fetch_events_data()
        if _existing and _existing.get("raw", "")[:100] == full_text[:100]:
            _keep_trans = _existing.get("translations", {})
        else:
            _keep_trans = {}
        gh_status, gh_msg = await save_events_data(full_text, _keep_trans)
        logger.info("Event #%d raw saved; GitHub: %d %s (kept %d translations)",
                    event_id, gh_status, gh_msg[:80], len(_keep_trans))

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
    langs = ["en", "pl", "be", "uk", "de"]  # ru is source, no translation needed
    translations: dict = {}

    # Fast path: seed DB from any existing GitHub translations first
    try:
        existing = await fetch_events_data()
        if existing:
            for lang, txt in existing.get("translations", {}).items():
                if txt and lang in langs:
                    await save_translation(event_id, lang, txt)
                    translations[lang] = txt
                    logger.info("BG seeded %s from GitHub cache (%d chars)", lang, len(txt))
    except Exception as e:
        logger.warning("BG seed from GitHub failed: %s", e)

    # Slow path: translate any langs still missing
    newly_translated = False
    for lang in langs:
        if lang in translations:
            continue  # already seeded from GitHub
        try:
            result = await translate(text, lang)
            if result and result != text:
                await save_translation(event_id, lang, result)
                # Only update GitHub if new translation is better than existing
                existing_len = len(translations.get(lang, ""))
                if len(result) > existing_len:
                    translations[lang] = result
                    newly_translated = True
                    logger.info("BG translated %s (%d chars)", lang, len(result))
                else:
                    logger.info("BG skipped overwrite of %s (existing better: %d > %d)", lang, existing_len, len(result))
            else:
                logger.warning("BG translation failed for %s", lang)
        except Exception as e:
            logger.warning("BG translation error for %s: %s", lang, e)
        await _asyncio.sleep(2)
    if newly_translated:
        await save_events_data(text, translations)
    logger.info("BG: done — %d/%d translations in DB", len(translations), len(langs))


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
    # Count cached translations
    from database.db import get_translation
    trans_count = 0
    trans_langs = []
    if events:
        for lang in ["en", "pl", "be", "uk", "de"]:
            t = await get_translation(events[0]["id"], lang)
            if t:
                trans_count += 1
                trans_langs.append(lang)
    return web.json_response({
        "version": VERSION,
        "GITHUB_PAT_set": bool(pat),
        "GITHUB_PAT_prefix": pat[:8] + "..." if pat else "(empty)",
        "events_in_db": len(events),
        "events_text_len": len(events[0]["text"]) if events else 0,
        "cached_translations": trans_count,
        "cached_langs": trans_langs,
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
