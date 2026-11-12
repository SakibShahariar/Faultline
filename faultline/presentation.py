"""Read-only view models shared by the GTK UI and integration tests."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from .storage import Database


def load_incidents(database: Database | None = None) -> list[dict]:
    """Convert stored findings and matching event evidence into UI-ready rows."""
    own_database = database is None
    db = database or Database()
    try:
        rows = db.connection.execute("""
            SELECT f.id, f.boot_id, f.category, f.title, f.summary,
                   f.confidence, f.contradicting_evidence_json,
                   b.boot_index, b.is_current, b.first_seen, b.last_seen
            FROM findings AS f
            LEFT JOIN boots AS b ON b.boot_id = f.boot_id
            ORDER BY COALESCE(b.last_seen, f.created_at) DESC, f.id DESC
        """).fetchall()
        incidents = []
        for row in rows:
            evidence_messages = set(json.loads(
                db.connection.execute(
                    "SELECT evidence_json FROM findings WHERE id = ?", (row["id"],)
                ).fetchone()["evidence_json"]
            ))
            events = db.connection.execute("""
                SELECT timestamp, source, message, signature, event_type, metadata_json FROM events
                WHERE boot_id = ? ORDER BY timestamp LIMIT 201
            """, (row["boot_id"],)).fetchall()
            grouped_events = {}
            for event in events:
                if event["message"] not in evidence_messages:
                    continue
                key = (event["timestamp"], event["signature"])
                if key not in grouped_events:
                    grouped_events[key] = {
                        **dict(event),
                        "sources": {event["source"]},
                    }
                else:
                    grouped_events[key]["sources"].add(event["source"])
                    if event["source"] == "systemd-coredump":
                        grouped_events[key]["metadata_json"] = event["metadata_json"]
                        grouped_events[key]["source"] = event["source"]
            all_events = list(grouped_events.values())
            evidence_count = db.connection.execute(
                "SELECT COUNT(DISTINCT timestamp || '|' || signature) FROM events "
                "WHERE boot_id = ? AND message IN (" +
                ",".join("?" for _ in evidence_messages) + ")",
                [row["boot_id"], *evidence_messages],
            ).fetchone()[0] if evidence_messages else 0
            events = all_events[:50]
            severity = {
                "kernel-panic": "High",
                "storage-error": "High",
                "pstore-crash": "High",
                "oom": "Medium",
                "gpu-reset": "Medium",
                "shell-crash": "Medium",
                "shell-restart": "Medium",
                "application-crash": "Medium",
                "coredump-crash": "Medium",
            }.get(row["category"], "Low")
            boot_label = "Current boot" if row["is_current"] else "Previous boot"
            when = row["last_seen"] or row["first_seen"] or "Time unavailable"
            incidents.append({
                "id": f"FL-{row['id']:04d}",
                "boot_id": row["boot_id"],
                "category": row["category"],
                "title": row["title"],
                "subtitle": f"{when} · {boot_label}",
                "severity": severity,
                "icon": "dialog-warning-symbolic",
                "detail": row["summary"],
                "confidence": row["confidence"].title(),
                "contradicting_evidence": json.loads(row["contradicting_evidence_json"]),
                "evidence": [
                    (
                        event["timestamp"],
                        ", ".join(sorted(event["sources"])),
                        event["message"] + (
                            "\nCommand: " + (json.loads(event["metadata_json"]).get("command") or "")
                            if json.loads(event["metadata_json"]).get("command") else ""
                        ),
                    )
                    for event in events
                ],
                "evidence_count": evidence_count,
                "evidence_truncated": evidence_count > len(events),
                "causes": [],
            })
        return incidents
    finally:
        if own_database:
            db.close()


def load_boot_summary(database: Database | None = None) -> dict:
    own_database = database is None
    db = database or Database()
    try:
        rows = db.connection.execute("""
            SELECT boot_id, first_seen, last_seen, boot_index, is_current, shutdown_status
            FROM boots ORDER BY boot_index DESC
        """).fetchall()
        current = next((row for row in rows if row["is_current"]), None)
        previous = next((row for row in rows if not row["is_current"]), None)
        return {
            "count": len(rows),
            "current_started": current["first_seen"] if current else None,
            "previous_status": previous["shutdown_status"] if previous else None,
        }
    finally:
        if own_database:
            db.close()


def load_source_status(database: Database | None = None) -> dict:
    own_database = database is None
    db = database or Database()
    try:
        statuses = {}
        for row in db.connection.execute(
            "SELECT source, available, detail, checked_at FROM source_status"
        ).fetchall():
            try:
                checked = datetime.fromisoformat(row["checked_at"].replace("Z", "+00:00"))
                if checked.tzinfo is None:
                    checked = checked.replace(tzinfo=timezone.utc)
                stale = datetime.now(timezone.utc) - checked > timedelta(hours=24)
            except (TypeError, ValueError):
                stale = True
            statuses[row["source"]] = {
                "available": bool(row["available"]),
                "detail": row["detail"],
                "checked_at": row["checked_at"],
                "stale": stale,
            }
        return statuses
    finally:
        if own_database:
            db.close()
