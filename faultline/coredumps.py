"""Metadata-only reader for systemd-coredump records."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

from .models import Event
from .signatures import signature_for
from .sources import SourceError, _run

_BOOT_ID = re.compile(r"^[0-9a-fA-F]{32}$")
_SECRET_ARGUMENT = re.compile(
    r"(?i)(--?(?:token|password|passwd|secret|api[-_]key)(?:=|\s+))([^\s]+)"
)


def _text(value: Any) -> str:
    if isinstance(value, list):
        return " ".join(
            item.decode("utf-8", errors="replace") if isinstance(item, bytes) else str(item)
            for item in value
        )
    return str(value)


def _safe_command(value: Any) -> str | None:
    if value in (None, ""):
        return None
    command = _text(value)[:2000]
    return _SECRET_ARGUMENT.sub(r"\1<redacted>", command)


def _first(record: dict[str, Any], *names: str) -> Any:
    for name in names:
        if record.get(name) not in (None, ""):
            return record[name]
    return None


def parse_coredump_json(payload: str) -> list[Event]:
    if not payload.strip():
        return []
    try:
        decoded = json.loads(payload)
        records = decoded if isinstance(decoded, list) else [decoded]
    except json.JSONDecodeError:
        records = []
        for line in payload.splitlines():
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            records.extend(item if isinstance(item, list) else [item])

    events: list[Event] = []
    for record in records:
        if not isinstance(record, dict):
            continue
        boot_id = str(_first(record, "COREDUMP_BOOT_ID", "_BOOT_ID", "boot_id") or "")
        if not _BOOT_ID.fullmatch(boot_id):
            continue
        executable = str(_first(record, "COREDUMP_EXE", "exe", "EXE") or "unknown executable")
        signal = str(_first(record, "COREDUMP_SIGNAL", "signal", "SIGNAL") or "unknown signal")
        pid = _first(record, "COREDUMP_PID", "pid", "PID")
        uid = _first(record, "COREDUMP_UID", "uid", "UID")
        command = _safe_command(_first(record, "COREDUMP_CMDLINE", "cmdline", "CMDLINE"))
        raw_stack = _first(record, "COREDUMP_STACKTRACE", "stacktrace", "STACKTRACE")
        stack_summary = _text(raw_stack)[:1500] if raw_stack else None
        raw_timestamp = _first(record, "COREDUMP_TIMESTAMP", "timestamp", "TIME")
        timestamp = "unknown"
        if raw_timestamp is not None:
            try:
                if isinstance(raw_timestamp, (int, float)) or str(raw_timestamp).isdigit():
                    timestamp = datetime.fromtimestamp(float(raw_timestamp), timezone.utc).isoformat()
                else:
                    timestamp = datetime.fromisoformat(str(raw_timestamp).replace("Z", "+00:00")).isoformat()
            except (ValueError, TypeError, OSError, OverflowError):
                timestamp = str(raw_timestamp)
        message = f"Process {executable} produced a coredump (signal {signal})"
        events.append(Event(
            boot_id=boot_id, timestamp=timestamp, source="systemd-coredump",
            message=message, event_type="coredump",
            signature=signature_for(f"{executable}:{signal}", "systemd-coredump"),
            metadata={
                "executable": executable,
                "signal": signal,
                "pid": str(pid) if pid is not None else None,
                "uid": str(uid) if uid is not None else None,
                "command": command,
                "stack_summary": stack_summary,
                "stacktrace_available": stack_summary is not None,
            },
        ))
    return events


def list_coredump_events() -> list[Event]:
    result = _run(["coredumpctl", "--json=short", "--no-pager", "list"], timeout=60)
    return parse_coredump_json(result.stdout)
