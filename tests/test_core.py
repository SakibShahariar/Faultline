import json
import tempfile
import unittest
from pathlib import Path

from faultline.diagnostics import classify
from faultline.models import Boot, Event
from faultline.signatures import normalize_message, signature_for
from faultline.sources import parse_boot_list, parse_journal_json
from faultline.storage import Database


class SignatureTests(unittest.TestCase):
    def test_pid_and_address_are_normalized(self):
        self.assertEqual(normalize_message("Killed process 1234 at 0xdeadbeef"),
                         normalize_message("Killed process 5678 at 0xcafebabe"))

    def test_signature_is_stable(self):
        self.assertEqual(signature_for("oom-kill pid=123"), signature_for("oom-kill pid=456"))


class JournalParserTests(unittest.TestCase):
    def test_parses_boot_history(self):
        lines = [
            "IDX BOOT ID FIRST ENTRY LAST ENTRY",
            "-1 " + "a" * 32 + " Mon 2026-11-10 08:00:00 Mon 2026-11-10 09:00:00",
            "0 " + "b" * 32 + " Tue 2026-11-11 08:00:00 Tue 2026-11-11 10:00:00",
        ]
        boots = parse_boot_list(lines)
        self.assertEqual(len(boots), 2)
        self.assertFalse(boots[0].current)
        self.assertTrue(boots[1].current)

    def test_parses_journal_json(self):
        row = {"MESSAGE": "Out of memory: Killed process 42", "__REALTIME_TIMESTAMP": "1000000",
               "SYSLOG_IDENTIFIER": "kernel", "PRIORITY": "3", "_SYSTEMD_UNIT": "systemd-oomd.service"}
        events = parse_journal_json([json.dumps(row)], "a" * 32)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].priority, 3)
        self.assertEqual(events[0].source, "kernel")

    def test_skips_malformed_and_empty_rows(self):
        events = parse_journal_json(["not json", json.dumps({"MESSAGE": ""})], "b" * 32)
        self.assertEqual(events, [])


class DiagnosisTests(unittest.TestCase):
    def test_detects_oom_without_claiming_shutdown_cause(self):
        event = Event("c" * 32, "now", "kernel", "Out of memory: Killed process 12")
        finding = classify([event])[0]
        self.assertEqual(finding.category, "oom")
        self.assertEqual(finding.confidence, "moderate")


class StorageTests(unittest.TestCase):
    def test_database_migrates_and_deduplicates(self):
        with tempfile.TemporaryDirectory() as directory:
            db = Database(Path(directory) / "faultline.db")
            boot = Boot("d" * 32, index=0, current=True)
            db.upsert_boot(boot)
            event = Event(boot.boot_id, "2026-01-01T00:00:00+00:00", "kernel",
                          "test", signature=signature_for("test"))
            self.assertEqual(db.add_events([event]), 1)
            self.assertEqual(db.add_events([event]), 0)
            self.assertEqual(db.connection.execute("PRAGMA user_version").fetchone()[0], 1)
            db.close()


if __name__ == "__main__":
    unittest.main()
