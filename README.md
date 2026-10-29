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
