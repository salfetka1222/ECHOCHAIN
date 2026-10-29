import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from database import database


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.temp_dir.name) / "test.sqlite3")
        self.path_patcher = patch.object(database, "DB_PATH", self.db_path)
        self.path_patcher.start()
        database.init_db()

    def tearDown(self):
        self.path_patcher.stop()
        self.temp_dir.cleanup()

    def test_artifact_creation_and_mutation_are_recorded(self):
        database.remember_user(123, "tester")
        database.create_artifact("EC-ABC123", 123, "Test Echo", {
            "stability": 50, "energy": 50, "resonance": 20,
            "adaptation": 25, "complexity": 10,
        })
        row = database.get_artifact("EC-ABC123")
        self.assertIsNotNone(row)
        self.assertEqual(row["name"], "Test Echo")

        result = database.mutate_artifact("EC-ABC123", {
            "stability": 55, "energy": 50, "resonance": 20,
            "adaptation": 25, "complexity": 10,
        }, 123)
        self.assertEqual(result, (1, "Test Echo"))
        self.assertEqual(database.get_artifact("EC-ABC123")["generation"], 1)
        self.assertEqual(database.stats()["events"], 2)

    def test_colony_creation_is_unique_and_adds_founder(self):
        database.remember_user(123, "tester")
        _, first_created = database.create_colony("First Colony", 123)
        _, second_created = database.create_colony("First Colony", 123)
        self.assertTrue(first_created)
        self.assertFalse(second_created)
        self.assertEqual(database.list_colonies()[0]["members"], 1)

    def test_artifact_can_be_settled_in_founders_colony(self):
        database.remember_user(123, "tester")
        database.create_colony("First Colony", 123)
        database.create_artifact("EC-SETTLE1", 123, "Settled Echo", {
            "stability": 50, "energy": 50, "resonance": 20,
            "adaptation": 25, "complexity": 10,
        })

        status, colony_name = database.settle_artifact(
            "EC-SETTLE1", "first colony", 123
        )
        self.assertEqual((status, colony_name), ("settled", "First Colony"))

        artifacts = database.list_colony_artifacts("FIRST COLONY")
        self.assertEqual(len(artifacts), 1)
        self.assertEqual(artifacts[0]["code"], "EC-SETTLE1")
        self.assertEqual(database.list_colonies()[0]["artifacts"], 1)

        duplicate_status, _ = database.settle_artifact(
            "EC-SETTLE1", "First Colony", 123
        )
        self.assertEqual(duplicate_status, "already_settled")

    def test_only_creator_can_settle_an_artifact(self):
        database.remember_user(123, "creator")
        database.remember_user(456, "other")
        database.create_colony("First Colony", 123)
        database.create_artifact("EC-OWNR001", 123, "Owned Echo", {
            "stability": 50, "energy": 50, "resonance": 20,
            "adaptation": 25, "complexity": 10,
        })

        status, _ = database.settle_artifact("EC-OWNR001", "First Colony", 456)
        self.assertEqual(status, "not_owner")

    def test_pending_channel_posts_survive_database_reconnect(self):
        post_id = database.add_pending_channel_post("Important update", 123)
        row = database.get_pending_channel_post(post_id)
        self.assertIsNotNone(row)
        self.assertEqual(row["text"], "Important update")
        self.assertEqual(row["created_by"], 123)

        database.delete_pending_channel_post(post_id)
        self.assertIsNone(database.get_pending_channel_post(post_id))

    def test_foreign_keys_require_known_creator(self):
        with self.assertRaises(Exception):
            database.create_artifact("EC-FAIL00", 999, "Invalid", {
                "stability": 50, "energy": 50, "resonance": 20,
                "adaptation": 25, "complexity": 10,
            })


if __name__ == "__main__":
    unittest.main()
