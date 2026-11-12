import sqlite3
import tempfile
import unittest
from pathlib import Path

from faultline.models import Boot, Event
from faultline.signatures import signature_for
from faultline.storage import Database


class StorageMigrationTests(unittest.TestCase):
    def test_database_and_parent_directory_are_user_only(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "private" / "faultline.db"
            db = Database(path)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(path.parent.stat().st_mode & 0o777, 0o700)
            db.close()

    def test_migrates_existing_version_one_database(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "faultline.db"
            db = Database(path)
            boot_id = "d" * 32
            db.upsert_boot(Boot(boot_id))
            db.add_events([Event(
                boot_id, "2026-01-01", "kernel", "Legacy OOM message",
                signature="legacy-source-prefixed-signature",
            )])
            db.connection.execute("DROP TABLE samples")
            db.connection.execute("PRAGMA user_version = 1")
            db.close()

            migrated = Database(path)
            version = migrated.connection.execute("PRAGMA user_version").fetchone()[0]
            tables = {
                row["name"] for row in migrated.connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            self.assertEqual(version, 3)
            self.assertIn("samples", tables)
            stored_signature = migrated.connection.execute(
                "SELECT signature FROM events WHERE boot_id = ?", (boot_id,)
            ).fetchone()["signature"]
            self.assertEqual(stored_signature, signature_for("Legacy OOM message", "kernel"))
            migrated.close()

    def test_failed_event_batch_rolls_back_all_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            db = Database(Path(directory) / "faultline.db")
            boot_id = "a" * 32
            db.upsert_boot(Boot(boot_id))
            events = [
                Event(boot_id, "now", "kernel", "valid", signature="valid"),
                Event("b" * 32, "now", "kernel", "missing boot", signature="invalid"),
            ]
            with self.assertRaises(sqlite3.IntegrityError):
                db.add_events(events)
            count = db.connection.execute("SELECT COUNT(*) FROM events").fetchone()[0]
            self.assertEqual(count, 0)
            db.close()


if __name__ == "__main__":
    unittest.main()
