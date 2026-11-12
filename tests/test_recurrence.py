import tempfile
import unittest
from pathlib import Path

from faultline.models import Boot, Event
from faultline.recurrence import find_recurring_events
from faultline.storage import Database


class RecurrenceTests(unittest.TestCase):
    def test_finds_same_signature_across_boots_only(self):
        with tempfile.TemporaryDirectory() as directory:
            db = Database(Path(directory) / "faultline.db")
            boots = ["a" * 32, "b" * 32, "c" * 32]
            for index, boot_id in enumerate(boots):
                db.upsert_boot(Boot(boot_id, index=index - 2))
            db.add_events([
                Event(boots[0], "2026-01-01", "kernel", "same warning", signature="repeat"),
                Event(boots[1], "2026-01-02", "kernel", "same warning", signature="repeat"),
                Event(boots[2], "2026-01-03", "kernel", "unique warning", signature="unique"),
            ])
            recurring = find_recurring_events(db)
            self.assertEqual(len(recurring), 1)
            self.assertEqual(recurring[0]["signature"], "repeat")
            self.assertEqual(recurring[0]["boot_count"], 2)
            self.assertEqual(len(recurring[0]["occurrences"]), 2)
            self.assertEqual(recurring[0]["first_seen"], "2026-01-01")
            self.assertEqual(recurring[0]["last_seen"], "2026-01-02")
            self.assertEqual(
                {item["boot_id"] for item in recurring[0]["occurrences"]},
                set(boots[:2]),
            )
            db.close()

    def test_occurrence_lists_are_bounded_and_report_truncation(self):
        with tempfile.TemporaryDirectory() as directory:
            db = Database(Path(directory) / "faultline.db")
            boots = ["d" * 32, "e" * 32, "f" * 32]
            for index, boot_id in enumerate(boots):
                db.upsert_boot(Boot(boot_id, index=index - 2))
            db.add_events([
                Event(boot_id, f"2026-02-0{index + 1}", "kernel", "repeated",
                      signature="repeat")
                for index, boot_id in enumerate(boots)
            ])
            recurring = find_recurring_events(db, max_occurrences=2)
            self.assertEqual(len(recurring[0]["occurrences"]), 2)
            self.assertTrue(recurring[0]["occurrences_truncated"])
            db.close()


if __name__ == "__main__":
    unittest.main()
