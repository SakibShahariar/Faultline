"""Desktop notification dispatch for newly discovered incidents."""
from __future__ import annotations

import shutil
import subprocess
import sys


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


def dispatch_notifications(findings: list[dict], settings: dict) -> int:
    if not shutil.which("notify-send"):
        return 0
    rank = {"low": 0, "medium": 1, "high": 2}
    threshold = rank.get(settings.get("notification_min_severity", "low"), 0)
    eligible = [
        finding for finding in findings
        if rank.get(SEVERITY.get(finding["category"], "low"), 0) >= threshold
    ]
    started = 0
    for finding in eligible[:5]:
        incident_id = f"FL-{int(finding['id']):04d}"
        title = "Faultline: " + finding["title"]
        body = finding["summary"][:300]
        try:
            subprocess.Popen(
                [
                    sys.executable, "-m", "faultline.notifications",
                    "--incident-id", incident_id,
                    "--title", title,
                    "--body", body,
                    "--severity", SEVERITY.get(finding["category"], "low"),
                ],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            started += 1
        except OSError:
            continue
    return started


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(prog="faultline-notification")
    parser.add_argument("--incident-id", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--body", default="")
    parser.add_argument("--severity", choices=("low", "medium", "high"), default="low")
    args = parser.parse_args()

    if not shutil.which("notify-send"):
        return 1
    urgency = "critical" if args.severity == "high" else (
        "normal" if args.severity == "medium" else "low"
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
                args.title,
                args.body,
            ],
            capture_output=True,
            text=True,
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired):
        return 1

    if result.returncode == 0 and result.stdout.strip() == "default":
        try:
            subprocess.Popen(
                ["faultline-gui", "--incident-id", args.incident_id],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except OSError:
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
