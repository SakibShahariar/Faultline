import tempfile
import unittest
from pathlib import Path

from faultline.models import Boot, Event, Finding
from faultline.storage import Database


class ClearHistoryTests(unittest.TestCase):
    def test_clears_diagnostic_tables_transactionally(self):
        with tempfile.TemporaryDirectory() as directory:
            db = Database(Path(directory) / "faultline.db")
            boot = Boot("a" * 32, index=0, current=True)
            db.upsert_boot(boot)
            db.add_events([Event(boot.boot_id, "now", "kernel", "message")])
            db.add_findings(boot.boot_id, [Finding("oom", "OOM", "summary", "low")])
            db.add_sample({
                "boot_id": boot.boot_id, "captured_at": "2026-11-12T00:00:00+00:00",
                "metadata": {},
            })
            db.set_source_status("journal", True, "available")
            db.clear_history()
            for table in ("boots", "events", "findings", "samples", "source_status"):
                count = db.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                self.assertEqual(count, 0, table)
            db.close()


if __name__ == "__main__":
    unittest.main()
