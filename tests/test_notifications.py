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
            patch("faultline.notifications.shutil.which",
                  side_effect=lambda name: "/usr/bin/" + name if name == "notify-send" else None),
            patch("faultline.notifications.subprocess.run",
                  return_value=subprocess.CompletedProcess([], 0, stdout="", stderr="")) as run,
        ):
            count = dispatch_notifications(
                findings, {"notify_new_incidents": True, "notification_min_severity": "high"}
            )
        self.assertEqual(count, 1)
        command = run.call_args.args[0]
        self.assertEqual(command[0], "notify-send")
        self.assertIn("Faultline: Kernel panic", command)

    def test_clicking_notification_launches_matching_incident_in_user_scope(self):
        argv = [
            "faultline-notification", "--incident-id", "FL-0007",
            "--title", "Faultline incident", "--body", "Review evidence",
            "--severity", "high",
        ]
        which = {
            "notify-send": "/usr/bin/notify-send",
            "systemd-run": "/usr/bin/systemd-run",
            "faultline-gui": "/home/test/.local/bin/faultline-gui",
        }
        responses = [
            subprocess.CompletedProcess([], 0, stdout="default\n", stderr=""),
            subprocess.CompletedProcess([], 0, stdout="", stderr=""),
        ]
        with (
            patch.object(sys, "argv", argv),
            patch("faultline.notifications.shutil.which", side_effect=lambda name: which.get(name)),
            patch("faultline.notifications.subprocess.run", side_effect=responses) as run,
        ):
            self.assertEqual(main(), 0)
        command = run.call_args_list[1].args[0]
        self.assertEqual(command[0], "systemd-run")
        self.assertIn("--incident-id", command)
        self.assertIn("FL-0007", command)

    def test_missing_desktop_notification_service_does_not_break_collection(self):
        finding = {"id": 1, "category": "oom", "title": "OOM", "summary": "evidence"}
        with patch("faultline.notifications.shutil.which", return_value=None), \
             patch("faultline.notifications.subprocess.run") as run:
            self.assertEqual(
                dispatch_notifications(
                    [finding],
                    {"notify_new_incidents": True, "notification_min_severity": "low"},
                ),
                0,
            )
        run.assert_not_called()

    def test_notifications_can_be_disabled(self):
        with patch("faultline.notifications.subprocess.run") as run:
            self.assertEqual(
                dispatch_notifications(
                    [{"id": 1, "category": "oom", "title": "OOM", "summary": "evidence"}],
                    {"notify_new_incidents": False, "notification_min_severity": "low"},
                ),
                0,
            )
        run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
