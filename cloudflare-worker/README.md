# Cloudflare Worker — Warsaw Events Bot

This is a second, independent implementation of the same Telegram bot that
lives in the rest of this repo (Python, `main.py`, meant for Railway). It
used to exist only pasted into the Cloudflare dashboard's "Quick edit" box —
not tracked anywhere, not backed up, not reviewable. This folder is that
code, cleaned up and version-controlled.

## What's a "Cloudflare Worker", in plain terms?

A Worker is a small piece of JavaScript that Cloudflare runs for you, on
demand, in whichever of their ~300 data centers is closest to whoever's
making the request. There's no server to keep running and no monthly bill
for idle time — you're charged (or stay on the free tier) only for requests
that actually happen. The tradeoffs versus a normal server like Railway:

- **No persistent process.** The Worker only runs while it's handling one
  request; it can't sit there "polling" Telegram for updates the way the
  Python bot does. That's why this version uses a **webhook** instead —
  Telegram calls `/webhook` on the Worker whenever something happens,
  rather than the bot repeatedly asking Telegram "anything new?".
- **No local disk / SQLite.** Instead of a database file, it uses
  **Workers KV** — Cloudflare's own simple key-value store (`env.EVENTS_KV`
  in the code). That's the `current_event` and `lang:<chat_id>` keys you'll
  see in the code.
- **Short-lived execution.** Each request gets a small CPU budget. Slow
  work (like saving to GitHub) is kicked off with `ctx.waitUntil(...)` so it
  finishes in the background without delaying the reply to the user.

## Why did both a Python/Railway version and this Worker exist?

Best read of the evidence: this Worker was a part-way migration attempt off
Railway (probably to stop paying for / depending on an always-on server).
It's a line-for-line port of the Python bot's core logic — same emoji
rules, same GitHub backup file, even the same commit message
(`chore: update events [skip railway]`) — but the migration was never
finished:

- It was missing the **admin broadcast** feature (`handlers/admin.py`) and
  **auto-ingest from the `@thewarsawevents` channel** (`handlers/channel_post.py`).
  Both have been added back into `worker.js` in this commit.
- It had **no translation engine of its own** — it only accepted
  pre-translated text pushed in via `POST /translate`. The Python bot calls
  the MyMemory API itself on demand. `worker.js` now does the same.
- Its webhook secret was a **plaintext string baked into the source code**
  (`WEBHOOK_SECRET_VALUE = '...'`), instead of a Cloudflare "secret" —
  visible to anyone with dashboard access, and would have leaked into this
  repo's history the moment it was committed (this repo is **public**).
  Fixed: the Worker now reads `env.WEBHOOK_SECRET`, like everything else.

Both versions write to the exact same file in this repo
(`data/events.json`) and both can only talk to the *same* Telegram bot —
and Telegram will only deliver updates to **one** of "webhook" or
"long-polling" at a time, never both. So right now, only one of these two
implementations is actually answering real users; the other is a dead copy
quietly doing nothing except occasionally still writing to GitHub if its
`/events` endpoint gets hit.

## Checking which one is currently live (safe, read-only)

Open this in a browser, with your real bot token in place of `<TOKEN>`:

```
https://api.telegram.org/bot<TOKEN>/getWebhookInfo
```

- If `"url"` is empty/missing → **no webhook is set** → Telegram is
  delivering updates via long-polling → the **Railway/Python bot** is live
  (assuming it's actually deployed and running).
- If `"url"` is set to something ending in `/webhook` on a
  `*.workers.dev` or custom domain → the **Cloudflare Worker** is live.

This only reads Telegram's own records; it can't change anything.

## Deploying this Worker (once you're ready to make it the live one)

You'll need the [`wrangler` CLI](https://developers.cloudflare.com/workers/wrangler/)
(Cloudflare's deploy tool) or the dashboard's own editor.

1. Fill in the KV namespace id in `wrangler.toml` (find it under
   Workers & Pages → KV in the dashboard, or `wrangler kv namespace list`).
2. Set the secrets — **never put these in a file that gets committed**:
   ```bash
   wrangler secret put BOT_TOKEN
   wrangler secret put GITHUB_PAT
   wrangler secret put WEBHOOK_SECRET
   wrangler secret put ADMIN_USER_ID
   ```
   (`CHANNEL_USERNAME` is optional — defaults to `thewarsawevents` if unset.)
3. Deploy: `wrangler deploy` from inside this folder.
4. **Only when you're ready to cut over**, point Telegram's webhook at the
   deployed URL:
   ```
   https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://<your-worker>.workers.dev/webhook
   ```
   This is the one step that actually flips which system answers users —
   do it deliberately, not as part of routine deploys.

## Files here

- `worker.js` — the Worker source (this is what gets deployed).
- `wrangler.toml` — deploy config. No secrets in it, ever.
