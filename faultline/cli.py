"""Command-line entry point for Faultline diagnostics."""
from __future__ import annotations

import argparse
import json

from .collector import scan
from .storage import Database


def main() -> int:
    parser = argparse.ArgumentParser(prog="faultline", description="Local Linux crash diagnostics")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("scan", help="collect available boot journal evidence")
    sub.add_parser("boots", help="list stored boot records")
    args = parser.parse_args()

    if args.command == "scan":
        print(json.dumps(scan(), indent=2))
        return 0
    db = Database()
    try:
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
