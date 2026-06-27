# Telegram Multilang Bot

A Telegram bot built with Python and aiogram 3.x that supports 5 languages: English, Polish, Russian, Belarusian, and Ukrainian.

## Project structure

```
.
├── main.py
├── .env
├── requirements.txt
├── config/
│   └── settings.py       # Loads BOT_TOKEN from .env
├── database/
│   └── db.py             # SQLite helpers (get/set user language)
├── handlers/
│   ├── start.py          # /start command
│   ├── help.py           # /help command
│   └── language.py       # /language command + callback handler
├── keyboards/
│   └── language_kb.py    # Inline keyboard with language buttons
├── locales/
│   ├── en.json
│   ├── pl.json
│   ├── ru.json
│   ├── be.json
│   └── uk.json
└── utils/
    └── i18n.py           # Translation loader
```

## Setup

### 1. Prerequisites

- Python 3.10+

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure the token

The `.env` file already contains the token. If you need to change it:

```
BOT_TOKEN=your_token_here
```

### 4. Run the bot

```bash
python main.py
```

The bot will start and print log output. Press `Ctrl+C` to stop.

## Commands

| Command | Description |
|---------|-------------|
| `/start` | Shows the language selection keyboard |
| `/language` | Shows the language selection keyboard again |
| `/help` | Displays help text in the user's chosen language |

## How it works

- Language preference is stored per user in a local SQLite file (`bot.db`), created automatically on first run.
- When a language button is pressed, the message is edited in-place to confirm the selection.
- `/help` reads the user's stored language and responds using the matching locale JSON file.
- Unknown users default to English.
