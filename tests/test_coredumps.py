import json
import unittest

from faultline.coredumps import parse_coredump_json


class CoredumpParserTests(unittest.TestCase):
    def test_parses_metadata_without_command_line(self):
        record = {
            "COREDUMP_BOOT_ID": "a" * 32,
            "COREDUMP_EXE": "/usr/bin/example",
            "COREDUMP_SIGNAL": "11",
            "COREDUMP_PID": "1234",
            "COREDUMP_TIMESTAMP": "2026-11-12T09:30:00+00:00",
            "COREDUMP_CMDLINE": "example --private-token secret",
        }
        events = parse_coredump_json(json.dumps([record]))
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].event_type, "coredump")
        self.assertEqual(events[0].metadata["executable"], "/usr/bin/example")
        self.assertNotIn("private-token", str(events[0].metadata))

    def test_ignores_records_without_valid_boot_id(self):
        self.assertEqual(parse_coredump_json(json.dumps([{"COREDUMP_EXE": "/bin/app"}])), [])

    def test_handles_line_delimited_json(self):
        row = {"_BOOT_ID": "b" * 32, "exe": "/usr/bin/app", "signal": "6"}
        events = parse_coredump_json(json.dumps(row) + "\n" + "invalid")
        self.assertEqual(len(events), 1)


if __name__ == "__main__":
    unittest.main()
