"""Coordinate an unprivileged, incremental diagnostic scan."""
from __future__ import annotations

from .coredumps import list_coredump_events
from .diagnostics import classify
from .extensions import (
    correlate_extension_events,
    describe_enabled_extensions,
    is_extension_error_candidate,
    is_shell_failure,
    list_enabled_extensions,
)
from .models import Event, Finding
from .pstore import read_pstore
from .settings import load_settings
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
        for evidence in finding.evidence:
            if evidence not in existing.evidence:
                existing.evidence.append(evidence)
        existing.evidence = existing.evidence[:20]
        for evidence in finding.contradicting_evidence:
            if evidence not in existing.contradicting_evidence:
                existing.contradicting_evidence.append(evidence)
        existing.contradicting_evidence = existing.contradicting_evidence[:20]
        existing.confidence = (
            "low" if existing.contradicting_evidence else
            ("high" if len(existing.evidence) > 1 else "moderate")
        )


def scan(database: Database | None = None, notify: bool = False) -> dict:
    own_database = database is None
    db = database or Database()
    summary = {"boots_seen": 0, "events_added": 0, "coredumps_seen": 0,
               "findings": 0, "new_findings": [], "source_errors": []}
    try:
        settings = load_settings()
        try:
            boots = list_boots()
            # Keep periodic scans bounded; older records remain available in SQLite.
            boots = boots[-settings["max_boots_per_scan"]:]
            db.set_source_status("journal", True, "systemd journal is readable")
        except SourceError as exc:
            db.set_source_status("journal", False, str(exc))
            summary["source_errors"].append({"source": "journal", "error": str(exc)})
            return summary

        summary["boots_seen"] = len(boots)
        coredumps_by_boot: dict[str, list[Event]] = {}
        coredump_ok = False
        if settings["collect_coredumps"]:
            try:
                coredumps = list_coredump_events()
                for event in coredumps:
                    coredumps_by_boot.setdefault(event.boot_id, []).append(event)
                summary["coredumps_seen"] = len(coredumps)
                coredump_ok = True
                db.set_source_status("coredumpctl", True, f"{len(coredumps)} metadata records read")
            except SourceError as exc:
                db.set_source_status("coredumpctl", False, str(exc))
                summary["source_errors"].append({"source": "coredumpctl", "error": str(exc)})
        else:
            db.set_source_status("coredumpctl", False, "Disabled in Faultline settings")

        enabled_extensions: set[str] = set()
        extensions_ok = False
        if settings["correlate_extensions"]:
            try:
                enabled_extensions = list_enabled_extensions()
                extensions_ok = True
                extension_details = describe_enabled_extensions(enabled_extensions)
                labels = [
                    item["name"] + (
                        f" v{item['version']}" if item.get("version") is not None else ""
                    )
                    for item in extension_details[:12]
                ]
                inventory = ", ".join(labels)
                if len(extension_details) > 12:
                    inventory += f", and {len(extension_details) - 12} more"
                db.set_source_status(
                    "gnome-extensions", True,
                    f"{len(enabled_extensions)} enabled extension(s)" +
                    (": " + inventory if inventory else "")
                )
            except SourceError as exc:
                db.set_source_status("gnome-extensions", False, str(exc))
                summary["source_errors"].append({"source": "gnome-extensions", "error": str(exc)})
        else:
            db.set_source_status("gnome-extensions", False, "Disabled in Faultline settings")

        previous_boot = next((boot for boot in boots if boot.index == -1), None)
        pstore_by_boot: dict[str, list[Event]] = {}
        pstore_ok = False
        if not settings["collect_pstore"]:
            db.set_source_status("pstore", False, "Disabled in Faultline settings")
        elif previous_boot:
            pstore_ok = True
            pstore_events = read_pstore(previous_boot.boot_id)
            pstore_by_boot[previous_boot.boot_id] = pstore_events
            db.set_source_status(
                "pstore", bool(pstore_events),
                f"{len(pstore_events)} retained record(s); associated with previous boot heuristically"
                if pstore_events else "No readable retained pstore records found"
            )
        else:
            db.set_source_status("pstore", False, "No previous boot is available for heuristic association")

        for boot in boots:
            db.upsert_boot(boot)
            findings_by_category: dict[str, Finding] = {}
            extension_findings: dict[str, Finding] = {}
            extension_candidates: list[Event] = []
            shell_failures: list[Event] = []
            shutdown_evidence: list[Event] = []
            batch: list[Event] = []
            journal_ok = True
            try:
                for event in iter_boot_events(boot.boot_id):
                    lowered = event.message.lower()
                    if any(marker in lowered for marker in (
                        "reached target system shutdown", "reached target system power-off",
                        "reached target system reboot", "systemd-shutdown",
                        "kernel panic", "oops:", "bug: unable to handle",
                        "general protection fault",
                    )):
                        shutdown_evidence.append(event)
                    if extensions_ok and is_extension_error_candidate(event):
                        extension_candidates.append(event)
                    if extensions_ok and is_shell_failure(event):
                        shell_failures.append(event)
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

            if extensions_ok and extension_candidates and shell_failures:
                correlated_events, correlated_findings = correlate_extension_events(
                    extension_candidates, enabled_extensions, shell_failures
                )
                for event in correlated_events:
                    db.update_event_metadata(event)
                for finding in correlated_findings:
                    extension_findings[finding.title] = finding

            coredump_events = coredumps_by_boot.get(boot.boot_id, [])
            if coredump_events:
                summary["events_added"] += db.add_events(coredump_events)
                _merge_findings(findings_by_category, coredump_events)

            pstore_events = pstore_by_boot.get(boot.boot_id, [])
            if pstore_events:
                summary["events_added"] += db.add_events(pstore_events)
                _merge_findings(findings_by_category, pstore_events)
                shutdown_evidence.extend(
                    event for event in pstore_events
                    if any(marker in event.message.lower() for marker in (
                        "kernel panic", "oops:", "watchdog:", "soft lockup",
                        "hard lockup", "bug: unable to handle",
                        "general protection fault",
                    ))
                )

            if journal_ok:
                boot.shutdown_status = assess_shutdown(shutdown_evidence, current=boot.current)
            else:
                stored = db.connection.execute(
                    "SELECT shutdown_status FROM boots WHERE boot_id = ?",
                    (boot.boot_id,),
                ).fetchone()
                if stored:
                    boot.shutdown_status = stored["shutdown_status"]
            db.upsert_boot(boot)
            findings = list(findings_by_category.values()) + list(extension_findings.values())
            if journal_ok:
                replace_categories = {
                    "oom", "kernel-panic", "gpu-reset", "storage-error",
                    "shell-crash", "application-crash",
                }
                if coredump_ok:
                    replace_categories.add("coredump-crash")
                if pstore_ok:
                    replace_categories.add("pstore-crash")
                if extensions_ok:
                    replace_categories.add("extension-error")
                newly_created = db.add_findings(
                    boot.boot_id, findings,
                    replace_categories=replace_categories,
                )
                summary["new_findings"].extend(newly_created)
                summary["findings"] += len(findings)
        db.set_source_status(
            "journal", True,
            f"Collection completed for {len(boots)} boot record(s)"
        )
        summary["boots_pruned"] = db.prune_old_boots(settings["retention_days"])
        if notify and settings["notify_new_incidents"] and summary["new_findings"]:
            from .notifications import dispatch_notifications
            summary["notifications_started"] = dispatch_notifications(
                summary["new_findings"], settings
            )
        return summary
    finally:
        if own_database:
            db.close()
