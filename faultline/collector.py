"""Coordinate a bounded, unprivileged diagnostic scan."""
from __future__ import annotations

from .coredumps import list_coredump_events
from .diagnostics import classify
from .shutdown import assess_shutdown
from .sources import SourceError, list_boots, read_boot_events
from .storage import Database


def scan(database: Database | None = None) -> dict:
    own_database = database is None
    db = database or Database()
    summary = {"boots_seen": 0, "events_added": 0, "coredumps_seen": 0, "findings": 0, "source_errors": []}
    try:
        try:
            boots = list_boots()
            db.set_source_status("journal", True, "systemd journal is readable")
        except SourceError as exc:
            db.set_source_status("journal", False, str(exc))
            summary["source_errors"].append({"source": "journal", "error": str(exc)})
            return summary

        summary["boots_seen"] = len(boots)
        coredumps_by_boot = {}
        try:
            coredumps = list_coredump_events()
            for event in coredumps:
                coredumps_by_boot.setdefault(event.boot_id, []).append(event)
            summary["coredumps_seen"] = len(coredumps)
            db.set_source_status("coredumpctl", True, f"{len(coredumps)} metadata records read")
        except SourceError as exc:
            db.set_source_status("coredumpctl", False, str(exc))
            summary["source_errors"].append({"source": "coredumpctl", "error": str(exc)})

        for boot in boots:
            db.upsert_boot(boot)
            try:
                events = read_boot_events(boot.boot_id)
            except SourceError as exc:
                db.set_source_status(f"journal:{boot.boot_id}", False, str(exc))
                summary["source_errors"].append({"source": f"journal:{boot.boot_id}", "error": str(exc)})
                continue
            boot.shutdown_status = assess_shutdown(events, current=boot.current)
            db.upsert_boot(boot)
            db.set_source_status(f"journal:{boot.boot_id}", True, f"{len(events)} records read")
            events.extend(coredumps_by_boot.get(boot.boot_id, []))
            summary["events_added"] += db.add_events(events)
            findings = classify(events)
            db.add_findings(boot.boot_id, findings)
            summary["findings"] += len(findings)
        return summary
    finally:
        if own_database:
            db.close()
