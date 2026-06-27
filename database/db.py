import aiosqlite
import os
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "bot.db")


async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id   INTEGER PRIMARY KEY,
                language  TEXT    NOT NULL DEFAULT 'en'
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                week       INTEGER NOT NULL,
                year       INTEGER NOT NULL,
                text       TEXT    NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS event_translations (
                event_id INTEGER NOT NULL,
                language TEXT    NOT NULL,
                text     TEXT    NOT NULL,
                PRIMARY KEY (event_id, language)
            )
            """
        )
        await db.commit()


async def get_language(user_id: int) -> str | None:
    """Returns user's language or None if user not in DB yet."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT language FROM users WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None


async def set_language(user_id: int, language: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO users (user_id, language)
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET language = excluded.language
            """,
            (user_id, language),
        )
        await db.commit()


def _week_year(offset_weeks: int = 0) -> tuple[int, int]:
    dt = datetime.now() - timedelta(weeks=offset_weeks)
    iso = dt.isocalendar()
    return iso[1], iso[0]


async def save_event(week: int, year: int, text: str) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO events (week, year, text) VALUES (?, ?, ?)",
            (week, year, text),
        )
        await db.commit()
        return cursor.lastrowid


async def get_events(week_offset: int = 0) -> list[dict]:
    week, year = _week_year(week_offset)
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT id, text FROM events WHERE week = ? AND year = ? ORDER BY id",
            (week, year),
        ) as cursor:
            rows = await cursor.fetchall()
            return [{"id": r[0], "text": r[1]} for r in rows]


async def get_translation(event_id: int, language: str) -> str | None:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT text FROM event_translations WHERE event_id = ? AND language = ?",
            (event_id, language),
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None


async def save_translation(event_id: int, language: str, text: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO event_translations (event_id, language, text)
            VALUES (?, ?, ?)
            ON CONFLICT(event_id, language) DO UPDATE SET text = excluded.text
            """,
            (event_id, language, text),
        )
        await db.commit()
