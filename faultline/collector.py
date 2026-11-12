"""Coordinate an unprivileged, incremental diagnostic scan."""
from __future__ import annotations

from .coredumps import list_coredump_events
from .diagnostics import classify
from .models import Event, Finding
from .shutdown import assess_shutdown
from .sources import SourceError, iter_boot_events, list_boots
from .storage import Database

BATCH_SIZE = 500


def _merge_findings(target: dict[str, Finding], batch: list[Event]) -> None:
    for finding in classify(batch):
        existing = target.get(finding.category)
        if existing is None:
            target[finding.category] = finding
            continue
        existing.evidence.extend(finding.evidence)
        existing.evidence = existing.evidence[:20]
        existing.confidence = "high"


def scan(database: Database | None = None) -> dict:
    own_database = database is None
    db = database or Database()
    summary = {"boots_seen": 0, "events_added": 0, "coredumps_seen": 0,
               "findings": 0, "source_errors": []}
    try:
        try:
            boots = list_boots()
            db.set_source_status("journal", True, "systemd journal is readable")
        except SourceError as exc:
            db.set_source_status("journal", False, str(exc))
            summary["source_errors"].append({"source": "journal", "error": str(exc)})
            return summary

        summary["boots_seen"] = len(boots)
        coredumps_by_boot: dict[str, list[Event]] = {}
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
            findings_by_category: dict[str, Finding] = {}
            batch: list[Event] = []
            journal_ok = True
            try:
                for event in iter_boot_events(boot.boot_id):
                    batch.append(event)
                    if len(batch) >= BATCH_SIZE:
                        summary["events_added"] += db.add_events(batch)
                        _merge_findings(findings_by_category, batch)
                        batch.clear()
                if batch:
                    summary["events_added"] += db.add_events(batch)
                    _merge_findings(findings_by_category, batch)
                    batch.clear()
            except SourceError as exc:
                journal_ok = False
                db.set_source_status(f"journal:{boot.boot_id}", False, str(exc))
                summary["source_errors"].append(
                    {"source": f"journal:{boot.boot_id}", "error": str(exc)}
                )

            if journal_ok:
                db.set_source_status(f"journal:{boot.boot_id}", True, "Journal records collected incrementally")

            coredump_events = coredumps_by_boot.get(boot.boot_id, [])
            if coredump_events:
                summary["events_added"] += db.add_events(coredump_events)
                _merge_findings(findings_by_category, coredump_events)

            boot.shutdown_status = assess_shutdown(
                [Event(boot_id=boot.boot_id, timestamp="", source="summary",
                       message=evidence)
                 for finding in findings_by_category.values()
                 for evidence in finding.evidence],
                current=boot.current,
            )
            db.upsert_boot(boot)
            findings = list(findings_by_category.values())
            db.add_findings(boot.boot_id, findings)
            summary["findings"] += len(findings)
        return summary
    finally:
        if own_database:
            db.close()
