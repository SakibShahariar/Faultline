import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from faultline.extensions import correlate_extension_events, describe_enabled_extensions
from faultline.models import Event
from faultline.sources import parse_journal_json


class ExtensionCorrelationTests(unittest.TestCase):
    def event(self, message, source="gnome-shell"):
        return Event("a" * 32, "2026-11-12T09:30:00+00:00", source, message)

    def test_extension_inventory_reads_name_and_version_from_metadata(self):
        extension = "blur-my-shell@aunetx"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            metadata_dir = root / extension
            metadata_dir.mkdir()
            (metadata_dir / "metadata.json").write_text(json.dumps({
                "uuid": extension,
                "name": "Blur my Shell",
                "version": 67,
            }))
            with patch("faultline.extensions.extension_metadata_roots", return_value=(root,)):
                inventory = describe_enabled_extensions({extension})
        self.assertEqual(inventory[0]["name"], "Blur my Shell")
        self.assertEqual(inventory[0]["version"], 67)
        self.assertEqual(inventory[0]["state"], "enabled")

    def test_parses_sanitized_gnome_journal_fixture(self):
        fixture = Path(__file__).parent / "fixtures" / "gnome-shell" / "extension-error.json"
        row = json.loads(fixture.read_text(encoding="utf-8"))
        events = parse_journal_json([json.dumps(row)], row["_BOOT_ID"])
        self.assertEqual(len(events), 1)
        self.assertIn("JS ERROR", events[0].message)
        self.assertEqual(events[0].source, "gnome-shell")

    def test_matches_only_enabled_extension_error_paths(self):
        extension = "blur-my-shell@aunetx"
        events = [self.event(
            "JS ERROR: TypeError: bad value at "
            "/home/user/.local/share/gnome-shell/extensions/blur-my-shell@aunetx/extension.js:20"
        )]
        shell_failure = self.event(
            "gnome-shell.service: Main process exited, code=dumped, status=11/SEGV",
            source="systemd",
        )
        shell_failure.timestamp = "2026-11-12T09:31:00+00:00"
        correlated, findings = correlate_extension_events(
            events, {extension}, [shell_failure]
        )
        self.assertEqual(correlated[0].event_type, "extension-error")
        self.assertEqual(correlated[0].metadata["extension_id"], extension)
        self.assertEqual(len(findings), 1)
        self.assertIn("does not prove", findings[0].summary)
        self.assertEqual(events[0].metadata["correlated_shell_failures"], 1)

    def test_repeated_extension_errors_group_nearby_shell_failures(self):
        extension = "blur-my-shell@aunetx"
        first = self.event(
            "JS ERROR: TypeError at /extensions/blur-my-shell@aunetx/extension.js"
        )
        second = self.event(
            "JS ERROR: ReferenceError at /extensions/blur-my-shell@aunetx/extension.js"
        )
        second.timestamp = "2026-11-12T09:31:00+00:00"
        first_shell = self.event(
            "gnome-shell.service: Main process exited, code=dumped, status=11/SEGV",
            source="systemd",
        )
        first_shell.timestamp = "2026-11-12T09:32:00+00:00"
        second_shell = self.event(
            "mutter: gnome-shell crashed with signal 11",
            source="mutter",
        )
        second_shell.timestamp = "2026-11-12T09:33:00+00:00"

        correlated, findings = correlate_extension_events(
            [first, second], {extension}, [first_shell, second_shell]
        )
        self.assertEqual(len(correlated), 2)
        self.assertEqual(len(findings), 2)
        self.assertTrue(all(item.confidence == "moderate" for item in findings))
        self.assertTrue(all(len(item.evidence) == 3 for item in findings))
        self.assertNotEqual(findings[0].title, findings[1].title)

    def test_extension_error_without_nearby_shell_failure_is_not_a_suspect(self):
        message = "JS ERROR: TypeError at /extensions/blur-my-shell@aunetx/extension.js"
        _events, findings = correlate_extension_events(
            [self.event(message)], {"blur-my-shell@aunetx"}, []
        )
        self.assertEqual(findings, [])

    def test_does_not_correlate_failures_outside_the_time_window(self):
        message = "JS ERROR: TypeError at /extensions/blur-my-shell@aunetx/extension.js"
        shell = self.event(
            "gnome-shell segfaulted", source="gnome-shell"
        )
        shell.timestamp = "2026-11-12T10:00:00+00:00"
        _events, findings = correlate_extension_events(
            [self.event(message)], {"blur-my-shell@aunetx"}, [shell]
        )
        self.assertEqual(findings, [])

    def test_does_not_blame_disabled_or_unmatched_extensions(self):
        message = "JS ERROR: TypeError at /extensions/some-extension@sample/extension.js"
        _events, findings = correlate_extension_events(
            [self.event(message)], {"different-extension@sample"}
        )
        self.assertEqual(findings, [])

    def test_ignores_non_error_extension_mentions(self):
        message = "Loaded /extensions/blur-my-shell@aunetx/extension.js"
        _events, findings = correlate_extension_events(
            [self.event(message)], {"blur-my-shell@aunetx"}
        )
        self.assertEqual(findings, [])


if __name__ == "__main__":
    unittest.main()
