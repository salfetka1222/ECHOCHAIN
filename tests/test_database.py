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

    def test_foreign_keys_require_known_creator(self):
        with self.assertRaises(Exception):
            database.create_artifact("EC-FAIL00", 999, "Invalid", {
                "stability": 50, "energy": 50, "resonance": 20,
                "adaptation": 25, "complexity": 10,
            })


if __name__ == "__main__":
    unittest.main()
