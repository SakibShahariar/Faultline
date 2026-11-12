import tempfile
import unittest
from pathlib import Path
from shutil import copyfile
from unittest.mock import patch

from faultline.pstore import read_pstore


class PstoreTests(unittest.TestCase):
    def test_reads_bounded_text_and_marks_heuristic_association(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            copyfile(Path(__file__).parent / "fixtures" / "pstore" / "dmesg-ramoops-0", root / "dmesg-ramoops-0")
            with patch("faultline.pstore.PSTORE_PATHS", (root,)):
                events = read_pstore("a" * 32)
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0].event_type, "pstore")
            self.assertEqual(events[0].metadata["association"], "heuristic_previous_boot")
            self.assertIn("Kernel panic", events[0].message)

    def test_does_not_assign_records_without_boot_context(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "dmesg-ramoops-0").write_text("Kernel panic")
            with patch("faultline.pstore.PSTORE_PATHS", (root,)):
                self.assertEqual(read_pstore(None), [])

    def test_ignores_oversized_records(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "large").write_bytes(b"x" * (2 * 1024 * 1024 + 1))
            with patch("faultline.pstore.PSTORE_PATHS", (root,)):
                self.assertEqual(read_pstore("b" * 32), [])


if __name__ == "__main__":
    unittest.main()
