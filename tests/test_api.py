import hashlib
import hmac
import json
import time
import unittest
from urllib.parse import urlencode

from api import verify_init_data


class TelegramAuthTests(unittest.TestCase):
    def make_init_data(self, token="test-token", auth_date=None):
        values = {
            "auth_date": str(auth_date or int(time.time())),
            "query_id": "AAExample",
            "user": json.dumps({"id": 123456, "first_name": "Echo"}, separators=(",", ":")),
        }
        check_string = "\n".join(f"{key}={value}" for key, value in sorted(values.items()))
        secret_key = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
        values["hash"] = hmac.new(secret_key, check_string.encode(), hashlib.sha256).hexdigest()
        return urlencode(values)

    def test_accepts_valid_telegram_signature(self):
        user = verify_init_data(self.make_init_data(), "test-token")
        self.assertEqual(user["id"], 123456)
        self.assertEqual(user["first_name"], "Echo")

    def test_rejects_invalid_signature(self):
        with self.assertRaises(ValueError):
            verify_init_data(self.make_init_data(), "wrong-token")

    def test_rejects_expired_session(self):
        old_date = int(time.time()) - 90000
        with self.assertRaises(ValueError):
            verify_init_data(self.make_init_data(auth_date=old_date), "test-token")

    def test_rejects_missing_data(self):
        with self.assertRaises(ValueError):
            verify_init_data("", "test-token")

    def test_rejects_malformed_query_string(self):
        with self.assertRaises(ValueError):
            verify_init_data("not-a-query-string", "test-token")

    def test_rejects_duplicate_fields(self):
        with self.assertRaises(ValueError):
            verify_init_data("auth_date=1&auth_date=2&hash=abc", "test-token")


if __name__ == "__main__":
    unittest.main()
