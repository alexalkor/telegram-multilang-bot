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
3. **Storage**: the event text + its per-language translations live in
   Cloudflare Workers KV, backed up to this repo at `data/events.json` via
   the GitHub API, so nothing is lost if the Worker's KV ever needs clearing.
4. **Translation**: MyMemory API (free), called on demand per language,
   cached afterwards so it's only paid for once per language per event.
5. **Delivery**: user presses "Warsaw weekend events" in Telegram → bot reads
   the cached event, translates if needed, sends it in chunks (Telegram has
   a ~4096-char message limit), re-attaches the menu keyboard.

## Current production system: the Cloudflare Worker
`cloudflare-worker/worker.js` is the live bot — confirmed via Telegram's
`getWebhookInfo` (Nov 2026): the webhook points at
`warsaw-events-worker.alexandr130514.workers.dev/webhook`. See
`cloudflare-worker/README.md` for what it is, how it's deployed, and the
read-only way to re-check this if it's ever in doubt.

A second, older implementation (everything under `legacy/`: `main.py`,
`handlers/`, `database/`, `keyboards/`, `utils/`, `locales/`) talks to Telegram via
long-polling instead of a webhook. Telegram only delivers to one of the two
at a time, so **this Python implementation is retired / not currently
serving users** — it's kept in the repo for reference only until a decision
is made on whether to delete it outright (see "To confirm later").

## Where things live
- `cloudflare-worker/` — the live implementation (`worker.js`) + its own README.
- `wrangler.toml`, `package.json` (repo root) — Worker deploy config and the
  pinned `wrangler` version (`npm run dev` / `deploy` / `tail`). The KV
  namespace id in `wrangler.toml` is still a placeholder — `npm run deploy`
  won't work until the real id is filled in.
- `legacy/` — the retired long-polling implementation (`main.py`, `handlers/`,
  `database/`, `keyboards/`, `utils/`, `locales/`, `requirements.txt`). Kept in
  its own folder so a root-level `requirements.txt` can't trigger a Python
  `pip install` in Cloudflare Workers Builds. Run it from inside `legacy/`.
- `LICENSE` — MIT.
- `data/events.json` — GitHub-backed cache the live Worker reads and writes.
  `data/events.txt` is an older legacy fallback, no longer used.

## Rules for every session
1. This repo is **public** on GitHub. Never commit a real token, API key, or
   webhook secret — not in code, not in `wrangler.toml`, not in a config
   file. Secrets are Cloudflare "secret" bindings (`wrangler secret put`, or
   the dashboard's Settings → Variables with "Encrypt" on) — never plain
   `[vars]` or a literal in `worker.js`.
2. Don't assume which system is live without checking — see
   `cloudflare-worker/README.md`'s `getWebhookInfo` instructions.
3. A change that could affect real users right now (setWebhook, deploying
   over the live Worker, clearing KV/GitHub cache, changing the bot token)
   needs an explicit go-ahead first, even if a prior message approved
   something similar.
4. Keep this file and `cloudflare-worker/README.md` in sync with reality —
   don't let documentation describe a system that's no longer true, the way
   the original undocumented Worker drifted from the Python bot.

## To confirm later
- Whether to delete the retired long-polling implementation outright, or
  keep it around as reference/fallback.
- Where the weekly Russian source text should come from going forward once
  the scheduled task replaces the old claude.ai Project task.
- Whether this bot becomes an alkor.dev module (see `alexalkor/alkordev`
  repo's `modules/registry.md` — it's currently listed inconsistently there,
  once as "The-Warsaw Weekend Events Bot" (live) and once as "Telegram
  Multilang Bot" (backlog) — same project, needs cleanup).
