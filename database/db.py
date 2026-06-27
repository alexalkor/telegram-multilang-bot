import aiosqlite
import os

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
        await db.commit()


async def get_language(user_id: int) -> str:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT language FROM users WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else "en"


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
