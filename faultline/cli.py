"""Command-line entry point for Faultline diagnostics."""
from __future__ import annotations

import argparse
import json

from .collector import scan
from .recurrence import find_recurring_events
from .reports import build_report, write_report
from .sampler import run_sampler
from .storage import Database


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="faultline", description="Local Linux crash diagnostics"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("scan", help="collect available boot journal evidence")
    sub.add_parser("boots", help="list stored boot records")
    sub.add_parser("recurrences", help="list event signatures seen across multiple boots")
    sub.add_parser("sampler", help="run the optional background resource sampler")
    report_parser = sub.add_parser("report", help="export a local diagnostic report")
    report_parser.add_argument("--output", required=True, help="destination file")
    report_parser.add_argument("--format", choices=("markdown", "json"),
                               default="markdown")
    report_parser.add_argument("--boot-id", help="limit report to one boot ID")
    report_parser.add_argument(
        "--include-sensitive", action="store_true",
        help="disable default redaction (review the report before sharing)",
    )
    args = parser.parse_args()

    if args.command == "scan":
        print(json.dumps(scan(), indent=2))
        return 0
    if args.command == "sampler":
        try:
            run_sampler()
        except RuntimeError as exc:
            parser.error(str(exc))
        return 0

    db = Database()
    try:
        if args.command == "recurrences":
            print(json.dumps(find_recurring_events(db), indent=2))
            return 0

        if args.command == "report":
            report = build_report(
                db, boot_id=args.boot_id, redact=not args.include_sensitive
            )
            destination = write_report(args.output, report, args.format)
            print(destination)
            return 0

        rows = db.connection.execute(
            "SELECT boot_id, first_seen, last_seen, boot_index, is_current, shutdown_status "
            "FROM boots ORDER BY boot_index"
        ).fetchall()
        print(json.dumps([dict(row) for row in rows], indent=2))
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
