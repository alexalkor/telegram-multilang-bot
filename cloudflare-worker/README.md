# Cloudflare Worker — Warsaw Events Bot

This is the **live, production bot** (confirmed via Telegram's
`getWebhookInfo`, Nov 2026 — webhook points at
`warsaw-events-worker.alexandr130514.workers.dev/webhook`). It used to exist
only pasted into the Cloudflare dashboard's "Quick edit" box — not tracked
anywhere, not backed up, not reviewable. This folder is that code, cleaned
up and version-controlled.

A second, older implementation of the same bot lives at the repo root
(`main.py`, Python, talks to Telegram via long-polling instead of a
webhook). Telegram only delivers updates to one of the two at a time, and
it's this Worker — the Python one is retired.

## What's a "Cloudflare Worker", in plain terms?

A Worker is a small piece of JavaScript that Cloudflare runs for you, on
demand, in whichever of their ~300 data centers is closest to whoever's
making the request. There's no server to keep running and no monthly bill
for idle time — you're charged (or stay on the free tier) only for requests
that actually happen. Tradeoffs versus a normal always-on server:

- **No persistent process.** The Worker only runs while it's handling one
  request; it can't sit there "polling" Telegram for updates. That's why it
  uses a **webhook** instead — Telegram calls `/webhook` on the Worker
  whenever something happens, rather than the bot repeatedly asking
  Telegram "anything new?".
- **No local disk / SQLite.** Instead of a database file, it uses
  **Workers KV** — Cloudflare's own simple key-value store (`env.EVENTS_KV`
  in the code). That's the `current_event` and `lang:<chat_id>` keys you'll
  see in the code.
- **Short-lived execution.** Each request gets a small CPU budget. Slow
  work (like saving to GitHub) is kicked off with `ctx.waitUntil(...)` so it
  finishes in the background without delaying the reply to the user.

## What was wrong with the version that was live before this cleanup

It's a line-for-line port of the older Python bot's core logic — same
emoji rules, same GitHub backup file, even the same commit message — but
the port was never finished:

- Missing the **admin broadcast** feature and **auto-ingest from the
  `@thewarsawevents` channel**. Both are now in `worker.js`.
- **No translation engine of its own** — it only accepted pre-translated
  text pushed in via `POST /translate`. `worker.js` now calls the
  MyMemory API itself, on demand, same as the Python bot did.
- Its webhook secret was a **plaintext string baked into the source code**
  — visible to anyone with dashboard access, and would have leaked into
  this repo's history the moment it was committed (this repo is
  **public**). Fixed: it now reads `env.WEBHOOK_SECRET`.
- Telegram's webhook registration didn't include `channel_post` in
  `allowed_updates`, so even once channel auto-ingest was added, Telegram
  wouldn't actually deliver those updates — see the fix below.

## Checking which system is currently live (safe, read-only)

Open this in a browser, with your real bot token in place of `<TOKEN>`:

```
https://api.telegram.org/bot<TOKEN>/getWebhookInfo
```

- Empty/missing `"url"` → no webhook set → the old Python bot would be live
  (if it's even still running).
- `"url"` set to a `*.workers.dev` or custom-domain address → this Worker is
  live.

This only reads Telegram's own records; it can't change anything.

## Fixing the `allowed_updates` gap (adds channel auto-ingest)

Telegram was only forwarding `message` and `callback_query` updates, not
`channel_post`. Re-registering the webhook with the full list turns on
channel auto-ingest without changing the webhook URL itself. Open this in a
browser, with your real bot token in place of `<TOKEN>`:

```
https://api.telegram.org/bot<TOKEN>/setWebhook?url=https%3A%2F%2Fwarsaw-events-worker.alexandr130514.workers.dev%2Fwebhook&allowed_updates=%5B%22message%22%2C%22callback_query%22%2C%22channel_post%22%5D
```

A successful response looks like `{"ok":true,"result":true,"description":"Webhook was set"}`.
This does **not** change which system is live — it only widens what Telegram
sends to the same URL that's already registered.

## Deploying the cleaned-up `worker.js` (replacing what's live now)

**Copy first, then deploy** — the currently-live script reads two things
from env that the new one still needs, plus one new thing it didn't need
before:

1. In the Cloudflare dashboard → Workers & Pages → your worker → Settings →
   Variables, check what's already set. `BOT_TOKEN` and `GITHUB_PAT` should
   already be there (the old code used them too) — leave them as-is.
2. `WEBHOOK_SECRET` was **not** an env var before (it was hardcoded in the
   source as `WEBHOOK_SECRET_VALUE`). Add it now as a secret, set to that
   exact same value, so whatever currently POSTs events to `/events` keeps
   working without changes on its end.
3. `ADMIN_USER_ID` is brand new (the old code had no admin feature at all).
   Add it as a secret if you want admin broadcast to work — if you skip it,
   the rest of the bot still runs fine, that one feature just stays off.
4. `CHANNEL_USERNAME` is optional, defaults to `thewarsawevents` if unset.

Then deploy the new code. Easiest path (same place you copied the old code
from): dashboard → your worker → **Edit code** → select all → paste in the
full contents of `worker.js` from this folder → **Save and deploy**.

(Alternative, if you ever want a non-dashboard path: the
[`wrangler` CLI](https://developers.cloudflare.com/workers/wrangler/) with
`wrangler secret put <NAME>` for each secret above and `wrangler deploy`
from inside this folder — `wrangler.toml` is already set up for it, you'd
just need to fill in the KV namespace id.)

## Files here

- `worker.js` — the Worker source (this is what gets deployed).
- `wrangler.toml` — deploy config, for the CLI path. No secrets in it, ever.
