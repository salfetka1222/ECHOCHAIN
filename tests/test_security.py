import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from bot_rate_limit import TelegramRateLimitMiddleware
from database import database as db
from database.channel_posts import (
    claim_pending_channel_post,
    finish_channel_post,
    reject_pending_channel_post,
    release_channel_post,
)


class ChannelApprovalAtomicityTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.old_path = db.DB_PATH
        db.DB_PATH = str(Path(self.temp_dir.name) / "test.sqlite3")
        db.init_db()
        self.post_id = db.add_pending_channel_post("Test post", 123)

    def tearDown(self):
        db.DB_PATH = self.old_path
        self.temp_dir.cleanup()

    def test_only_one_claim_succeeds(self):
        first = claim_pending_channel_post(self.post_id)
        second = claim_pending_channel_post(self.post_id)
        self.assertIsNotNone(first)
        self.assertEqual(first["text"], "Test post")
        self.assertIsNone(second)

    def test_failed_publish_can_be_retried(self):
        self.assertIsNotNone(claim_pending_channel_post(self.post_id))
        self.assertTrue(release_channel_post(self.post_id))
        self.assertIsNotNone(claim_pending_channel_post(self.post_id))
        self.assertTrue(finish_channel_post(self.post_id))
        self.assertIsNone(claim_pending_channel_post(self.post_id))

    def test_reject_cannot_remove_claimed_post(self):
        self.assertIsNotNone(claim_pending_channel_post(self.post_id))
        self.assertFalse(reject_pending_channel_post(self.post_id))


class TelegramRateLimitTests(unittest.IsolatedAsyncioTestCase):
    async def test_blocks_eleventh_update_in_window(self):
        middleware = TelegramRateLimitMiddleware(limit=10, window_seconds=30)
        handler = AsyncMock(return_value="handled")
        event = SimpleNamespace(from_user=SimpleNamespace(id=42), answer=AsyncMock())
        data = {}

        for _ in range(10):
            self.assertEqual(await middleware(handler, event, data), "handled")
        self.assertIsNone(await middleware(handler, event, data))
        self.assertEqual(handler.await_count, 10)
        event.answer.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
