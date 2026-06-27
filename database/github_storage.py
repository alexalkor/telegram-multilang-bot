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


async def save_events(text: str) -> tuple[int, str]:
    """Commit updated events text to GitHub.
    Returns (http_status, message) for diagnostics."""
    pat = os.getenv("GITHUB_PAT", "")
    if not pat:
        logger.warning("GITHUB_PAT not set — skipping GitHub save")
        return 0, "GITHUB_PAT not set"
    try:
        encoded = base64.b64encode(text.encode("utf-8")).decode("ascii")
        h = _headers()
        async with aiohttp.ClientSession() as session:
            # Get current SHA
            sha: str | None = None
            async with session.get(_API_URL, headers=h) as r:
                if r.status == 200:
                    sha = (await r.json()).get("sha")
                else:
                    logger.warning("GitHub GET failed: %d", r.status)

            payload: dict = {
                "message":   "chore: update events [skip deploy]",
                "content":   encoded,
                "committer": {"name": "Warsaw Events Bot", "email": "bot@warsawevents.app"},
            }
            if sha:
                payload["sha"] = sha

            async with session.put(_API_URL, headers=h, json=payload) as r:
                body = await r.text()
                if r.status in (200, 201):
                    logger.info("Events saved to GitHub ✓ (status %d)", r.status)
                    return r.status, "ok"
                else:
                    logger.warning("GitHub PUT failed %d: %s", r.status, body[:300])
                    return r.status, body[:300]
    except Exception as e:
        logger.warning("GitHub save exception: %s", e)
        return -1, str(e)
