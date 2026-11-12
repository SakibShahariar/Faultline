"""Desktop notification dispatch for newly discovered incidents."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


SEVERITY = {
    "kernel-panic": "high",
    "pstore-crash": "high",
    "storage-error": "high",
    "oom": "medium",
    "gpu-reset": "medium",
    "shell-crash": "medium",
    "application-crash": "medium",
    "coredump-crash": "medium",
    "extension-error": "low",
}


def _gui_command() -> str:
    return shutil.which("faultline-gui") or str(
        Path.home() / ".local" / "bin" / "faultline-gui"
    )


def _launch_incident(incident_id: str) -> bool:
    gui = _gui_command()
    if shutil.which("systemd-run"):
        unit_name = "faultline-open-" + incident_id.lower().replace("-", "")
        try:
            result = subprocess.run(
                [
                    "systemd-run", "--user", f"--unit={unit_name}",
                    "--collect", "--no-block", gui, "--incident-id", incident_id,
                ],
                capture_output=True, text=True, timeout=10,
            )
            return result.returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            return False

    try:
        subprocess.Popen(
            [gui, "--incident-id", incident_id],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        return True
    except OSError:
        return False


def _show_notification(incident_id: str, title: str, body: str, severity: str) -> bool:
    if not shutil.which("notify-send"):
        return False
    urgency = "critical" if severity == "high" else (
        "normal" if severity == "medium" else "low"
    )
    try:
        result = subprocess.run(
            [
                "notify-send",
                "--app-name=Faultline",
                "--icon=dialog-warning-symbolic",
                f"--urgency={urgency}",
                "--expire-time=10000",
                "--action=default=Open Faultline",
                "--wait",
                title,
                body[:300],
            ],
            capture_output=True,
            text=True,
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False

    if result.returncode == 0 and result.stdout.strip() == "default":
        _launch_incident(incident_id)
    return result.returncode == 0


def dispatch_notifications(findings: list[dict], settings: dict) -> int:
    if not settings.get("notify_new_incidents", True) or not shutil.which("notify-send"):
        return 0
    rank = {"low": 0, "medium": 1, "high": 2}
    threshold = rank.get(settings.get("notification_min_severity", "low"), 0)
    eligible = [
        finding for finding in findings
        if rank.get(SEVERITY.get(finding["category"], "low"), 0) >= threshold
    ]
    sent = 0
    # Keep a large batch from blocking a login for an extended period.
    for finding in eligible[:3]:
        incident_id = f"FL-{int(finding['id']):04d}"
        if _show_notification(
            incident_id,
            "Faultline: " + finding["title"],
            finding["summary"],
            SEVERITY.get(finding["category"], "low"),
        ):
            sent += 1
    return sent


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(prog="faultline-notification")
    parser.add_argument("--incident-id", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--body", default="")
    parser.add_argument("--severity", choices=("low", "medium", "high"), default="low")
    args = parser.parse_args()
    return 0 if _show_notification(
        args.incident_id, args.title, args.body, args.severity
    ) else 1


if __name__ == "__main__":
    raise SystemExit(main())
