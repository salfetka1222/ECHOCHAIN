# ECHOCHAIN

**A shared evolving digital civilization inside Telegram.**

ECHOCHAIN is a persistent shared universe where artifacts evolve, colonies form, and discoveries emerge from deterministic system rules.

## Current foundation
- Telegram bot built with Python and aiogram 3
- SQLite persistence
- Deterministic genome mutations
- Artifact lineage and append-only event history
- Initial commands: `/start`, `/help`, `/universe`, `/create`, `/artifact CODE`, `/mutate CODE`, `/colony`

## Run locally or on a Python host
1. Install Python 3.11 or newer.
2. Install dependencies: `pip install -r requirements.txt`
3. Set the environment variable `BOT_TOKEN` to your Telegram bot token.
4. Run: `python main.py`

The database is stored at `data/echochain.sqlite3` by default. Set `ECHOCHAIN_DB_PATH` to change the location.

## Hosting
The project is designed to run as an always-on Python process using Telegram long polling. No public HTTP port is required for the initial bot.

## Safety and operations
- Never commit a real bot token.
- Keep the SQLite database file persistent on the hosting volume.
- Back up the database before deploying changes that alter its schema.
- This first version does not use external AI or paid APIs.


## Official news channel

The bot can publish project updates to the **ECHOCHAIN | Хроники** Telegram channel.

1. Create the channel in Telegram.
2. Add the ECHOCHAIN bot as an administrator with permission to post messages.
3. Set `CHANNEL_CHAT_ID` to the channel's public username (for example, `@echochain_chronicles`) or numeric chat ID.
4. Set `OWNER_ID` to the Telegram numeric user ID allowed to approve important posts.
5. Start a private chat with the bot once so it can send approval requests to you.
6. Set both values as host environment variables. Never commit real tokens or private credentials.

New artifact and colony announcements are posted automatically. Every tenth-generation milestone and manual `/announce TEXT` announcement requires approval using the buttons sent to the owner. Pending posts are stored in SQLite.

Useful owner commands:
- `/channel_status` — check whether channel settings are present.
- `/announce TEXT` — submit an important announcement for approval.

The bot needs channel administrator permission to post messages. No paid service or external AI is required.
