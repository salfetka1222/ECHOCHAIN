"""Per-user rate limiting for Telegram messages and callback queries."""
import time
from collections import defaultdict, deque

from aiogram import BaseMiddleware


class TelegramRateLimitMiddleware(BaseMiddleware):
    """Allow at most 10 Telegram updates per user in a rolling 30-second window."""

    def __init__(self, limit: int = 10, window_seconds: int = 30):
        self.limit = limit
        self.window_seconds = window_seconds
        self.windows = defaultdict(deque)

    async def __call__(self, handler, event, data):
        user = getattr(event, "from_user", None)
        if user is None:
            return await handler(event, data)

        now = time.monotonic()
        window = self.windows[user.id]
        while window and now - window[0] >= self.window_seconds:
            window.popleft()

        if len(window) >= self.limit:
            try:
                await event.answer(
                    "Слишком много действий. Подожди немного и попробуй снова."
                )
            except Exception:
                pass
            return None

        window.append(now)
        return await handler(event, data)
