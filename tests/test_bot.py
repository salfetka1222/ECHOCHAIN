import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from aiogram.types import InlineKeyboardMarkup

from main import start


class MiniAppLaunchTests(unittest.IsolatedAsyncioTestCase):
    async def test_start_uses_inline_web_app_button(self):
        message = SimpleNamespace(
            from_user=SimpleNamespace(id=123, username="tester"),
            answer=self._answer,
        )
        self.answer_kwargs = {}

        with patch.dict(os.environ, {"WEBAPP_URL": "https://example.trycloudflare.com"}), \
             patch("main.remember_user"), patch("main.add_event"):
            await start(message)

        keyboard = self.answer_kwargs["reply_markup"]
        self.assertIsInstance(keyboard, InlineKeyboardMarkup)
        button = keyboard.inline_keyboard[0][0]
        self.assertEqual(button.text, "🚀 Открыть ECHOCHAIN")
        self.assertEqual(button.web_app.url, "https://example.trycloudflare.com")

    async def _answer(self, text, **kwargs):
        self.answer_kwargs = kwargs


if __name__ == "__main__":
    unittest.main()
