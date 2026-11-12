import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from faultline.collector import scan
from faultline.models import Boot, Event
from faultline.sources import SourceError
from faultline.storage import Database


class CollectorTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.tempdir.name) / "faultline.db")
        self.boot = Boot("a" * 32, first_seen="today", last_seen="now",
                         index=0, current=True)

    def tearDown(self):
        self.db.close()
        self.tempdir.cleanup()

    def scan_with(self, journal_reader):
        with (
            patch("faultline.collector.list_boots", return_value=[self.boot]),
            patch("faultline.collector.list_coredump_events", return_value=[]),
            patch("faultline.collector.list_enabled_extensions", return_value=set()),
            patch("faultline.collector.iter_boot_events", side_effect=journal_reader),
            patch("faultline.collector.read_pstore", return_value=[]),
        ):
            return scan(self.db)

    def test_scan_persists_events_and_findings_without_duplicate_growth(self):
        event = Event(self.boot.boot_id, "2026-01-01T00:00:00+00:00",
                      "kernel", "Out of memory: Killed process 123")
        result = self.scan_with(lambda _boot_id: iter([event]))
        self.assertEqual(result["boots_seen"], 1)
        self.assertEqual(result["events_added"], 1)
        self.assertEqual(len(result["new_findings"]), 1)
        first_finding_id = result["new_findings"][0]["id"]
        self.assertEqual(self.db.connection.execute("SELECT COUNT(*) FROM events").fetchone()[0], 1)
        self.assertEqual(self.db.connection.execute("SELECT COUNT(*) FROM findings").fetchone()[0], 1)

        second = self.scan_with(lambda _boot_id: iter([event]))
        self.assertEqual(second["new_findings"], [])
        stored = self.db.connection.execute("SELECT id FROM findings").fetchone()
        self.assertEqual(stored["id"], first_finding_id)
        self.assertEqual(self.db.connection.execute("SELECT COUNT(*) FROM events").fetchone()[0], 1)
        self.assertEqual(self.db.connection.execute("SELECT COUNT(*) FROM findings").fetchone()[0], 1)

    def test_journal_failure_preserves_existing_findings(self):
        event = Event(self.boot.boot_id, "2026-01-01T00:00:00+00:00",
                      "kernel", "Out of memory: Killed process 123")
        self.scan_with(lambda _boot_id: iter([event]))
        before = self.db.connection.execute("SELECT COUNT(*) FROM findings").fetchone()[0]

        def fail(_boot_id):
            raise SourceError("permission denied")

        result = self.scan_with(fail)
        after = self.db.connection.execute("SELECT COUNT(*) FROM findings").fetchone()[0]
        self.assertEqual(before, after)
        self.assertTrue(result["source_errors"])

    def test_missing_journal_is_reported_without_crashing(self):
        with patch(
            "faultline.collector.list_boots",
            side_effect=SourceError("journal is not readable"),
        ):
            result = scan(self.db)
        self.assertEqual(result["boots_seen"], 0)
        self.assertEqual(result["source_errors"][0]["source"], "journal")
        status = self.db.connection.execute(
            "SELECT available, detail FROM source_status WHERE source = 'journal'"
        ).fetchone()
        self.assertFalse(status["available"])
        self.assertIn("not readable", status["detail"])

    def test_optional_source_failure_preserves_its_findings(self):
        from faultline.models import Finding

        self.db.upsert_boot(self.boot)
        self.db.add_findings(self.boot.boot_id, [
            Finding("coredump-crash", "Application coredump", "Previously recorded",
                    "moderate", ["coredump evidence"]),
        ])

        with (
            patch("faultline.collector.list_boots", return_value=[self.boot]),
            patch("faultline.collector.list_coredump_events",
                  side_effect=SourceError("coredumpctl unavailable")),
            patch("faultline.collector.list_enabled_extensions", return_value=set()),
            patch("faultline.collector.iter_boot_events", return_value=iter([])),
            patch("faultline.collector.read_pstore", return_value=[]),
        ):
            scan(self.db)

        row = self.db.connection.execute(
            "SELECT summary FROM findings WHERE boot_id = ? AND category = 'coredump-crash'",
            (self.boot.boot_id,),
        ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["summary"], "Previously recorded")


if __name__ == "__main__":
    unittest.main()
