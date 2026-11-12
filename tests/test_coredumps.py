import json
import unittest
from pathlib import Path

from faultline.coredumps import parse_coredump_json


class CoredumpParserTests(unittest.TestCase):
    def test_parses_metadata_without_command_line(self):
        fixture = Path(__file__).parent / "fixtures" / "coredumpctl" / "application-crash.json"
        record = json.loads(fixture.read_text(encoding="utf-8"))[0]
        record["COREDUMP_CMDLINE"] = "example --token=secret --password secret2 --config=/home/alice/app.conf"
        events = parse_coredump_json(json.dumps([record]))
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].event_type, "coredump")
        self.assertEqual(events[0].metadata["executable"], "/usr/bin/example")
        self.assertNotIn("secret", str(events[0].metadata["command"]))
        self.assertIn("--token=<redacted>", events[0].metadata["command"])
        self.assertIn("--password <redacted>", events[0].metadata["command"])
        self.assertNotIn("secret2", events[0].metadata["command"])
        self.assertIn("/home/alice/app.conf", events[0].metadata["command"])
        self.assertEqual(events[0].metadata["uid"], None)
        self.assertIsNone(events[0].metadata["stack_summary"])
        self.assertFalse(events[0].metadata["stacktrace_available"])

    def test_captures_available_stack_summary_and_uid(self):
        record = {
            "COREDUMP_BOOT_ID": "c" * 32,
            "COREDUMP_EXE": "/usr/bin/example",
            "COREDUMP_UID": "1000",
            "COREDUMP_STACKTRACE": ["#0 frame_one", "#1 frame_two"],
        }
        event = parse_coredump_json(json.dumps([record]))[0]
        self.assertEqual(event.metadata["uid"], "1000")
        self.assertIn("frame_one", event.metadata["stack_summary"])
        self.assertTrue(event.metadata["stacktrace_available"])

    def test_ignores_records_without_valid_boot_id(self):
        self.assertEqual(parse_coredump_json(json.dumps([{"COREDUMP_EXE": "/bin/app"}])), [])

    def test_handles_line_delimited_json(self):
        row = {"_BOOT_ID": "b" * 32, "exe": "/usr/bin/app", "signal": "6"}
        events = parse_coredump_json(json.dumps(row) + "\n" + "invalid")
        self.assertEqual(len(events), 1)


if __name__ == "__main__":
    unittest.main()
