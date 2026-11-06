# Warsaw Events Bot: read me first

## What this is
A Telegram bot (`@thewarsaweventsbot`, public channel `@thewarsawevents`) that
sends a weekly list of Warsaw weekend events in 6 languages: Russian (source
language), English, Polish, Belarusian, Ukrainian, German. Alex (owner) is
not a developer — explain things in plain language, don't assume git/hosting
knowledge, and confirm before any action that touches the live, user-facing
bot.

## The pipeline, end to end
1. **Source text** (Russian) for the week's events comes from `@thewarsawevents`
   — either a channel post (auto-ingested) or pasted directly by the admin.
2. **Ingestion** happens at a `POST /events` endpoint, protected by an
   `X-Secret` header. Historically a scheduled task inside a regular
   claude.ai Project did this (visiting a source and POSTing the result) —
   being replaced with a Claude Code scheduled task, still controllable from
   the Claude app or phone.
3. **Storage**: the event text + its per-language translations are cached
   (SQLite on Railway / KV on Cloudflare) and backed up to this repo at
   `data/events.json` via the GitHub API, so a redeploy doesn't lose data.
4. **Translation**: MyMemory API (free), called on demand per language,
   cached afterwards so it's only paid for once per language per event.
5. **Delivery**: user presses "Warsaw weekend events" in Telegram → bot reads
   the cached event, translates if needed, sends it in chunks (Telegram has
   a ~4096-char message limit), re-attaches the menu keyboard.

## Two implementations exist — know which is live before changing either
- **`main.py` + friends (root of repo)** — Python/aiogram, meant for Railway,
  talks to Telegram via **long-polling**. Full feature set: admin broadcast,
  auto-ingest from the channel, on-demand translation.
- **`cloudflare-worker/worker.js`** — JavaScript, meant for Cloudflare
  Workers, talks to Telegram via a **webhook**. Was a part-finished migration
  off Railway; now has feature parity after this repo was cleaned up (see
  `cloudflare-worker/README.md` for the full history and a safe, read-only
  way to check which one Telegram is actually delivering updates to).
- Telegram only delivers to **one** of long-polling or webhook at a time —
  never both. Before changing deploy/webhook config, check `getWebhookInfo`
  (see `cloudflare-worker/README.md`) rather than assuming.
- Current direction (per Alex, Nov 2026): consolidate onto Cloudflare +
  git, retire Railway. Don't flip the live webhook or decommission Railway
  without an explicit go-ahead in the moment — it's user-facing.

## Where things live
- `main.py`, `handlers/`, `database/`, `keyboards/`, `utils/`, `locales/` —
  the Python/Railway implementation.
- `cloudflare-worker/` — the Cloudflare Worker implementation + its own README.
- `data/events.json` — shared GitHub-backed cache both implementations read
  and write. `data/events.txt` is a legacy fallback, no longer primary.
- `config/settings.py` — env vars the Python bot needs (`BOT_TOKEN`,
  `WEBHOOK_SECRET`, `GITHUB_PAT`, `ADMIN_USER_ID`, `GITHUB_REPO`).

## Rules for every session
1. This repo is **public** on GitHub. Never commit a real token, API key, or
   webhook secret — not in code, not in `wrangler.toml`, not in a config
   file. Secrets are env vars (`.env`, gitignored) on Railway, or Cloudflare
   "secret" bindings (`wrangler secret put`) — never plain `[vars]`.
2. Don't guess which deployment (Railway vs Cloudflare) is currently live —
   check `getWebhookInfo`, or ask.
3. A change that could affect real users right now (setWebhook, stopping
   Railway, clearing the KV/GitHub cache, changing the bot token) needs an
   explicit go-ahead first, even if a prior message approved something
   similar.
4. When porting a feature between the two implementations, update both this
   file's "Two implementations exist" section and `cloudflare-worker/README.md`
   if the facts changed (which one has parity, which is live, etc.) — don't
   let them drift out of sync again like the original Worker did.

## To confirm later
- Final call: Cloudflare-only, or keep Railway too? (leaning Cloudflare + git,
  not decided as of Nov 2026)
- Where the weekly Russian source text should come from going forward once
  the scheduled task replaces the old claude.ai Project task
- Whether this bot becomes an alkor.dev module (see `alexalkor/alkordev`
  repo's `modules/registry.md` — it's currently listed inconsistently there,
  once as "The-Warsaw Weekend Events Bot" (live) and once as "Telegram
  Multilang Bot" (backlog) — same project, needs cleanup)
