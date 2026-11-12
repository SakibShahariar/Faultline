"""Local diagnostic report generation with privacy-first redaction."""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from .storage import Database

_HOME = re.compile(r"/home/[^/\s]+")
_EMAIL = re.compile(r"(?<![\w.+-])[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")
_IPV4 = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_MAC = re.compile(r"\b(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}\b")
_BEARER = re.compile(r"(?i)\b(bearer\s+)[A-Za-z0-9._~+/-]+=*")


def redact_text(value: str) -> str:
    value = _HOME.sub("~", value)
    value = _EMAIL.sub("<redacted-email>", value)
    value = _IPV4.sub("<redacted-ip>", value)
    value = _MAC.sub("<redacted-mac>", value)
    return _BEARER.sub(r"\1<redacted-token>", value)


def build_report(db: Database, boot_id: str | None = None, redact: bool = True) -> dict:
    if boot_id:
        boots = db.connection.execute(
            "SELECT * FROM boots WHERE boot_id = ?", (boot_id,)
        ).fetchall()
    else:
        boots = db.connection.execute(
            "SELECT * FROM boots ORDER BY boot_index DESC"
        ).fetchall()

    report = {
        "format_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "privacy": {"redaction_enabled": redact},
        "boots": [],
    }
    for boot in boots:
        events = db.connection.execute("""
            SELECT timestamp, source, unit, priority, event_type, message, signature,
                   metadata_json
            FROM events WHERE boot_id = ? ORDER BY timestamp
        """, (boot["boot_id"],)).fetchall()
        findings = db.connection.execute("""
            SELECT category, title, summary, confidence, evidence_json
            FROM findings WHERE boot_id = ? ORDER BY id
        """, (boot["boot_id"],)).fetchall()
        boot_data = {
            "boot_id": boot["boot_id"],
            "first_seen": boot["first_seen"],
            "last_seen": boot["last_seen"],
            "boot_index": boot["boot_index"],
            "current": bool(boot["is_current"]),
            "shutdown_status": boot["shutdown_status"],
            "findings": [
                {
                    "category": row["category"],
                    "title": row["title"],
                    "summary": row["summary"],
                    "confidence": row["confidence"],
                    "evidence": json.loads(row["evidence_json"]),
                }
                for row in findings
            ],
            "events": [
                {
                    "timestamp": row["timestamp"],
                    "source": row["source"],
                    "unit": row["unit"],
                    "priority": row["priority"],
                    "event_type": row["event_type"],
                    "message": row["message"],
                    "signature": row["signature"],
                    "metadata": json.loads(row["metadata_json"]),
                }
                for row in events
            ],
        }
        report["boots"].append(boot_data)

    if redact:
        def visit(value):
            if isinstance(value, str):
                return redact_text(value)
            if isinstance(value, list):
                return [visit(item) for item in value]
            if isinstance(value, dict):
                return {key: visit(item) for key, item in value.items()}
            return value
        report = visit(report)
    return report


def render_markdown(report: dict) -> str:
    lines = [
        "# Faultline diagnostic report",
        "",
        f"Generated: {report['generated_at']}",
        f"Privacy redaction: {'enabled' if report['privacy']['redaction_enabled'] else 'disabled'}",
        "",
        "> Findings are evidence-based observations, not guaranteed root-cause conclusions.",
        "",
    ]
    for boot in report["boots"]:
        lines.extend([
            f"## Boot {boot['boot_id']}",
            "",
            f"- Index: {boot['boot_index']}",
            f"- Started: {boot['first_seen'] or 'unknown'}",
            f"- Last recorded: {boot['last_seen'] or 'unknown'}",
            f"- Ending assessment: {boot['shutdown_status']}",
            "",
            "### Findings",
            "",
        ])
        if not boot["findings"]:
            lines.append("No findings recorded.")
        for finding in boot["findings"]:
            lines.extend([
                f"#### {finding['title']}",
                "",
                f"- Category: {finding['category']}",
                f"- Confidence: {finding['confidence']}",
                "",
                finding["summary"],
                "",
            ])
            for evidence in finding["evidence"]:
                lines.append(f"- Evidence: {evidence}")
        lines.extend(["", "### Event evidence", ""])
        for event in boot["events"]:
            lines.append(
                f"- {event['timestamp']} **{event['source']}** — {event['message']}"
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_report(path: str | Path, report: dict, format: str = "markdown") -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if format == "json":
        destination.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                               encoding="utf-8")
    elif format == "markdown":
        destination.write_text(render_markdown(report), encoding="utf-8")
    else:
        raise ValueError(f"Unsupported report format: {format}")
    try:
        os.chmod(destination, 0o600)
    except OSError:
        pass
    return destination
