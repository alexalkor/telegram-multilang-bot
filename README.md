# Warsaw Events Bot

A Telegram bot (`@thewarsaweventsbot`, channel `@thewarsawevents`) that sends a
weekly list of Warsaw weekend events in 6 languages: Russian (source),
English, Polish, Belarusian, Ukrainian and German.

> **Start with [`CLAUDE.md`](CLAUDE.md)** for the current state of this
> project. The live, production bot is the Cloudflare Worker in
> [`cloudflare-worker/`](cloudflare-worker/README.md). The Python
> implementation under [`legacy/`](legacy/) is **retired** — it talked to
> Telegram via long-polling, is not deployed anywhere, and is kept for
> reference only.

## Repository layout

```
.
├── wrangler.toml            # Worker config (name, entry point, KV binding) — no secrets
├── package.json             # pins the wrangler version; dev / deploy / tail scripts
├── LICENSE                  # MIT
├── cloudflare-worker/
│   ├── worker.js            # the live Worker source (what gets deployed)
│   └── README.md            # how the Worker works, how to deploy / verify it
├── data/
│   ├── events.json          # LIVE — GitHub-backed cache written by the Worker
│   └── events.txt           # old plain-text fallback, no longer used
└── legacy/                  # RETIRED long-polling aiogram bot — not deployed
    ├── main.py
    ├── .env.example         # only relevant if main.py is ever run again
    ├── requirements.txt
    ├── config/settings.py   # loads env vars (BOT_TOKEN, ...)
    ├── database/            # SQLite helpers + GitHub JSON backup
    ├── handlers/            # /start, /help, /language, menu, admin, channel posts
    ├── keyboards/
    ├── locales/             # en / pl / ru / be / uk / de JSON
    └── utils/               # i18n loader, MyMemory translator
```

The legacy code lives in its own folder, away from the repo root, so that
Cloudflare Workers Builds doesn't auto-detect a root-level `requirements.txt`
and try to `pip install` it before every deploy.

## Running the live Worker (Cloudflare)

Secrets (`BOT_TOKEN`, `GITHUB_PAT`, `WEBHOOK_SECRET`, `ADMIN_USER_ID`) are never
stored in this repo — they are set in the Cloudflare dashboard (Settings →
Variables, "Encrypt" on) or with `npx wrangler secret put <NAME>`. Full
details, including how to deploy safely over the live Worker, are in
[`cloudflare-worker/README.md`](cloudflare-worker/README.md).

```bash
npm install          # installs the pinned wrangler
npm run dev          # local dev server
npm run deploy       # deploys to Cloudflare — this updates the LIVE bot
npm run tail         # live logs from the deployed Worker
```

`wrangler.toml` still has a placeholder KV namespace id — replace it with the
real one (`npx wrangler kv namespace list`) before using `npm run deploy`.

## Running the legacy Python bot (retired — reference only)

Requires Python 3.10+. Everything is run from inside `legacy/`:

```bash
cd legacy
pip install -r requirements.txt
cp .env.example .env     # then fill in BOT_TOKEN etc. — .env is git-ignored
python main.py
```

Telegram delivers updates to only one place at a time (the Worker's webhook
*or* a polling bot), so don't run this while the Worker's webhook is
registered unless you mean to take over.

Legacy commands: `/start` and `/language` (language keyboard), `/help`,
`/myid`. Language preference is stored per user in a local SQLite file
(`legacy/bot.db`, git-ignored, created on first run); unknown users default
to English.

## License

[MIT](LICENSE)
