"""Coordinate a bounded, unprivileged diagnostic scan."""
from __future__ import annotations

from .diagnostics import classify
from .sources import SourceError, list_boots, read_boot_events
from .storage import Database


def scan(database: Database | None = None) -> dict:
    own_database = database is None
    db = database or Database()
    summary = {"boots_seen": 0, "events_added": 0, "findings": 0, "source_errors": []}
    try:
        try:
            boots = list_boots()
            db.set_source_status("journal", True, "systemd journal is readable")
        except SourceError as exc:
            db.set_source_status("journal", False, str(exc))
            summary["source_errors"].append({"source": "journal", "error": str(exc)})
            return summary

        summary["boots_seen"] = len(boots)
        for boot in boots:
            db.upsert_boot(boot)
            try:
                events = read_boot_events(boot.boot_id)
            except SourceError as exc:
                db.set_source_status(f"journal:{boot.boot_id}", False, str(exc))
                summary["source_errors"].append({"source": f"journal:{boot.boot_id}", "error": str(exc)})
                continue
            db.set_source_status(f"journal:{boot.boot_id}", True, f"{len(events)} records read")
            summary["events_added"] += db.add_events(events)
            findings = classify(events)
            db.add_findings(boot.boot_id, findings)
            summary["findings"] += len(findings)
        return summary
    finally:
        if own_database:
            db.close()
