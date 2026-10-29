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
The project runs as an always-on Python process using Telegram long polling and an aiohttp HTTP server. The HTTP server provides the health endpoint and serves the Mini App.

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

Use `/release TEXT` in a private chat with the bot to publish a routine development update immediately. Use `/announce TEXT` to create an important announcement that requires owner approval. Pending important posts are stored in SQLite. Gameplay activity is not automatically sent to the news channel, keeping the feed focused on development news.

Useful owner commands:
- `/channel_status` — check whether channel settings are present.
- `/announce TEXT` — submit an important announcement for approval.

The bot needs channel administrator permission to post messages. No paid service or external AI is required.


## Telegram Mini App (first version)

The Mini App adds four sections: Universe, Artifacts, Colonies, and Chronicle. It uses the same SQLite database as the bot and authenticates requests with Telegram WebApp `initData` signature validation.

### Hosting layout

- The Telegram bot, HTTP API, and persistent SQLite database stay on Altare.
- The static Mini App is hosted separately on Vercel with HTTPS.
- `vercel.json` serves the static files from `webapp/` and proxies `/api/*` requests to the Altare API. API responses are not configured for CDN caching.
- The Vercel URL is the URL to set as `WEBAPP_URL` on Altare, after the preview has been verified.

### Deployment checklist

1. Import this repository into Vercel and select the `feature/mini-app-mvp` branch for the first preview.
2. Keep the project root at the repository root. The `vercel.json` file sets `webapp` as the static output directory.
3. Open the Vercel preview URL and check `/health`. It should return JSON with service `ECHOCHAIN` and status `ok`.
4. Open the Mini App from Telegram only after the health check and API connection have been verified.
5. Only then set `WEBAPP_URL` on Altare to the Vercel HTTPS URL and restart the bot.

The Altare API must be reachable at the origin configured in `vercel.json` on the allocated port. If `/health` does not respond, do not change the live bot or database; first verify the Altare port mapping and the HTTP server's `PORT` setting.

Until `WEBAPP_URL` is configured, the bot continues to work with its existing commands and does not show the Mini App launch button. Never replace the existing `.env` or `data/echochain.sqlite3` when updating code.
