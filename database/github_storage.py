"""Persist events to a GitHub file so they survive Railway redeploys."""
import base64
import logging
import os

import aiohttp

logger = logging.getLogger(__name__)

_REPO      = "alexalkor/telegram-multilang-bot"
_FILE_PATH = "data/events.txt"
_RAW_URL   = f"https://raw.githubusercontent.com/{_REPO}/main/{_FILE_PATH}"
_API_URL   = f"https://api.github.com/repos/{_REPO}/contents/{_FILE_PATH}"


def _headers() -> dict:
    """Build auth headers fresh each call so GITHUB_PAT is always current."""
    pat = os.getenv("GITHUB_PAT", "")
    return {
        "Authorization": f"token {pat}",
        "Accept":        "application/vnd.github+json",
    }


async def fetch_events() -> str | None:
    """Return the events text stored on GitHub, or None if empty/unavailable."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(_RAW_URL) as r:
                if r.status == 200:
                    text = (await r.text(encoding="utf-8")).strip()
                    if text and text != "(empty)":
                        return text
    except Exception as e:
        logger.warning("GitHub fetch failed: %s", e)
    return None


async def save_events(text: str) -> None:
    """Commit updated events text to GitHub (fire-and-forget is fine)."""
    pat = os.getenv("GITHUB_PAT", "")
    if not pat:
        logger.warning("GITHUB_PAT not set — skipping GitHub save")
        return
    try:
        # Python's str.encode() → bytes is UTF-8 by default; b64encode handles it correctly
        encoded = base64.b64encode(text.encode("utf-8")).decode("ascii")
        h = _headers()
        async with aiohttp.ClientSession() as session:
            # Get current SHA (needed to update an existing file)
            sha: str | None = None
            async with session.get(_API_URL, headers=h) as r:
                if r.status == 200:
                    sha = (await r.json()).get("sha")

            payload: dict = {
                "message":   "chore: update events [skip deploy]",
                "content":   encoded,
                "committer": {"name": "Warsaw Events Bot", "email": "bot@warsawevents.app"},
            }
            if sha:
                payload["sha"] = sha

            async with session.put(_API_URL, headers=h, json=payload) as r:
                if r.status in (200, 201):
                    logger.info("Events saved to GitHub ✓")
                else:
                    body = await r.text()
                    logger.warning("GitHub save failed %d: %s", r.status, body[:300])
    except Exception as e:
        logger.warning("GitHub save exception: %s", e)
