import subprocess
import sys
import unittest
from unittest.mock import patch

from faultline.notifications import dispatch_notifications, main


class NotificationTests(unittest.TestCase):
    def test_dispatch_respects_minimum_severity_and_uses_stable_incident_id(self):
        findings = [
            {"id": 1, "category": "extension-error", "title": "Extension warning",
             "summary": "Low severity"},
            {"id": 2, "category": "kernel-panic", "title": "Kernel panic",
             "summary": "High severity"},
        ]
        with (
            patch("faultline.notifications.shutil.which", return_value="/usr/bin/notify-send"),
            patch("faultline.notifications.subprocess.Popen") as spawn,
        ):
            count = dispatch_notifications(
                findings, {"notification_min_severity": "high"}
            )
        self.assertEqual(count, 1)
        command = spawn.call_args.args[0]
        self.assertIn("FL-0002", command)
        self.assertEqual(command[2], "-m")

    def test_clicking_notification_launches_matching_incident(self):
        argv = [
            "faultline-notification", "--incident-id", "FL-0007",
            "--title", "Faultline incident", "--body", "Review evidence",
            "--severity", "high",
        ]
        with (
            patch.object(sys, "argv", argv),
            patch("faultline.notifications.shutil.which", return_value="/usr/bin/notify-send"),
            patch("faultline.notifications.subprocess.run",
                  return_value=subprocess.CompletedProcess([], 0, stdout="default\n", stderr="")),
            patch("faultline.notifications.subprocess.Popen") as spawn,
        ):
            self.assertEqual(main(), 0)
        command = spawn.call_args.args[0]
        self.assertIn("--incident-id", command)
        self.assertIn("FL-0007", command)


if __name__ == "__main__":
    unittest.main()
