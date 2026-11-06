import aiosqlite
import os
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "bot.db")


async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id  INTEGER PRIMARY KEY,
                language TEXT NOT NULL DEFAULT 'en'
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                week       INTEGER NOT NULL,
                year       INTEGER NOT NULL,
                text       TEXT    NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS event_translations (
                event_id INTEGER NOT NULL,
                language TEXT    NOT NULL,
                text     TEXT    NOT NULL,
                PRIMARY KEY (event_id, language)
            )
        """)
        await db.commit()


# ── Users ───────────────────────────────────────────────────────────────────

async def get_language(user_id: int) -> str | None:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT language FROM users WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None


async def set_language(user_id: int, language: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO users (user_id, language) VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET language = excluded.language
        """, (user_id, language))
        await db.commit()


# ── Events ──────────────────────────────────────────────────────────────────

def _week_year() -> tuple[int, int]:
    iso = datetime.now().isocalendar()
    return iso[1], iso[0]  # week, year


async def replace_current_week_events(text: str) -> int:
    """Delete this week's events + cached translations, then insert fresh text.
    Returns the new event id."""
    week, year = _week_year()
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT id FROM events WHERE week=? AND year=?", (week, year)
        ) as cur:
            old_ids = [r[0] for r in await cur.fetchall()]
        for eid in old_ids:
            await db.execute(
                "DELETE FROM event_translations WHERE event_id=?", (eid,)
            )
        await db.execute(
            "DELETE FROM events WHERE week=? AND year=?", (week, year)
        )
        cursor = await db.execute(
            "INSERT INTO events (week, year, text) VALUES (?, ?, ?)",
            (week, year, text),
        )
        await db.commit()
        return cursor.lastrowid


async def append_to_week_events(new_text: str) -> int:
    """Append new_text to this week's existing event blob (merges into one row)."""
    week, year = _week_year()
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT id, text FROM events WHERE week=? AND year=? ORDER BY id LIMIT 1",
            (week, year)
        ) as cur:
            row = await cur.fetchone()
        if row:
            existing_id, existing_text = row
            # Invalidate cached translations so they get re-translated
            await db.execute("DELETE FROM event_translations WHERE event_id=?", (existing_id,))
            combined = existing_text.rstrip() + "\n\n" + new_text.strip()
            await db.execute("UPDATE events SET text=? WHERE id=?", (combined, existing_id))
            await db.commit()
            return existing_id
        else:
            cursor = await db.execute(
                "INSERT INTO events (week, year, text) VALUES (?, ?, ?)",
                (week, year, new_text)
            )
            await db.commit()
            return cursor.lastrowid


async def save_event(week: int, year: int, text: str) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO events (week, year, text) VALUES (?, ?, ?)",
            (week, year, text),
        )
        await db.commit()
        return cursor.lastrowid


async def get_latest_events() -> list[dict]:
    """Return events from the most recent week in DB."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT year, week FROM events ORDER BY year DESC, week DESC LIMIT 1"
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return []
            year, week = row[0], row[1]
        async with db.execute(
            "SELECT id, text FROM events WHERE year=? AND week=? ORDER BY id",
            (year, week),
        ) as cursor:
            rows = await cursor.fetchall()
            return [{"id": r[0], "text": r[1]} for r in rows]


# ── Translations ─────────────────────────────────────────────────────────────

async def clear_all_translations() -> int:
    """Delete all cached translations. Returns number of rows deleted."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM event_translations") as cur:
            count = (await cur.fetchone())[0]
        await db.execute("DELETE FROM event_translations")
        await db.commit()
        return count

async def get_translation(event_id: int, language: str) -> str | None:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT text FROM event_translations WHERE event_id=? AND language=?",
            (event_id, language),
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None


async def save_translation(event_id: int, language: str, text: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO event_translations (event_id, language, text) VALUES (?, ?, ?)
            ON CONFLICT(event_id, language) DO UPDATE SET text = excluded.text
        """, (event_id, language, text))
        await db.commit()
