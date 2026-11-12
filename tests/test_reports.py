import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from faultline.models import Boot, Event, Finding
from faultline.reports import build_report, redact_text, render_markdown, write_report
from faultline.storage import Database


class ReportTests(unittest.TestCase):
    def test_redacts_common_sensitive_values(self):
        value = (
            "Path /home/alice/file, mail alice@example.com, IP 192.168.1.10, "
            "MAC aa:bb:cc:dd:ee:ff, Bearer secret-token "
            "--password secret --api-key=another-secret workstation"
        )
        with patch("faultline.reports.socket.gethostname", return_value="workstation"):
            redacted = redact_text(value)
        for secret in ("alice", "alice@example.com", "192.168.1.10",
                       "aa:bb:cc:dd:ee:ff", "secret-token", "secret",
                       "another-secret", "workstation"):
            self.assertNotIn(secret, redacted)
        self.assertIn("~", redacted)
        self.assertIn("<redacted-host>", redacted)

    def test_builds_redacted_json_and_markdown(self):
        with tempfile.TemporaryDirectory() as directory:
            db = Database(Path(directory) / "faultline.db")
            boot = Boot("a" * 32, first_seen="start", last_seen="end", index=-1)
            db.upsert_boot(boot)
            event = Event(
                boot.boot_id, "2026-01-01T00:00:00+00:00", "kernel",
                "Read /home/alice/log for alice@example.com",
                signature="abc123",
            )
            db.add_events([event])
            db.add_findings(boot.boot_id, [
                Finding("oom", "Out of memory", "See /home/alice/log",
                        "moderate", ["Killed process"]),
            ])
            report = build_report(db)
            self.assertTrue(report["privacy"]["redaction_enabled"])
            self.assertNotIn("alice", json.dumps(report))
            markdown = render_markdown(report)
            self.assertIn("Faultline diagnostic report", markdown)
            self.assertIn("Out of memory", markdown)
            json_path = write_report(Path(directory) / "report.json", report, "json")
            md_path = write_report(Path(directory) / "report.md", report, "markdown")
            self.assertTrue(json.loads(json_path.read_text())["boots"])
            self.assertIn("Out of memory", md_path.read_text())
            self.assertEqual(json_path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(md_path.stat().st_mode & 0o777, 0o600)
            unredacted = build_report(db, redact=False)
            self.assertIn("alice", json.dumps(unredacted))
            db.close()


if __name__ == "__main__":
    unittest.main()
