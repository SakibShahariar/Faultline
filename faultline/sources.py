"""Unprivileged systemd journal and boot-history readers."""
from __future__ import annotations

import json
import selectors
import shutil
import subprocess
import time
from datetime import datetime, timezone
from typing import Iterable

from .models import Boot, Event
from .signatures import signature_for


class SourceError(RuntimeError):
    pass


def _run(command: list[str], timeout: int = 30) -> subprocess.CompletedProcess[str]:
    if not shutil.which(command[0]):
        raise SourceError(f"Required command not found: {command[0]}")
    try:
        result = subprocess.run(command, check=False, capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise SourceError(f"Command timed out: {command[0]}") from exc
    if result.returncode:
        detail = result.stderr.strip() or f"exit status {result.returncode}"
        raise SourceError(detail)
    return result


def parse_boot_list(lines: Iterable[str]) -> list[Boot]:
    boots: list[Boot] = []
    for line in lines:
        parts = line.split()
        if len(parts) < 5:
            continue
        try:
            index = int(parts[0])
        except ValueError:
            continue
        boot_id = parts[1]
        if len(boot_id) != 32:
            continue
        boots.append(Boot(boot_id=boot_id, first_seen=" ".join(parts[2:-2]) or None,
                          last_seen=" ".join(parts[-2:]) or None,
                          index=index, current=index == 0))
    return boots


def list_boots() -> list[Boot]:
    result = _run(["journalctl", "--list-boots", "--no-pager"])
    return parse_boot_list(result.stdout.splitlines())


def parse_journal_json(lines: Iterable[str], boot_id: str) -> list[Event]:
    events: list[Event] = []
    for line in lines:
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        message_value = item.get("MESSAGE", "")
        if isinstance(message_value, list):
            message = bytes(message_value).decode("utf-8", errors="replace")
        else:
            message = str(message_value)
        if not message:
            continue
        raw_ts = item.get("__REALTIME_TIMESTAMP")
        try:
            timestamp = datetime.fromtimestamp(int(raw_ts) / 1_000_000,
                                               tz=timezone.utc).isoformat()
        except (TypeError, ValueError, OSError):
            timestamp = str(item.get("_SOURCE_REALTIME_TIMESTAMP", "unknown"))
        source = str(item.get("SYSLOG_IDENTIFIER") or item.get("_COMM") or
                     item.get("_SYSTEMD_UNIT") or "journal")
        priority_raw = item.get("PRIORITY")
        try:
            priority = int(priority_raw) if priority_raw is not None else None
        except (TypeError, ValueError):
            priority = None
        unit = item.get("_SYSTEMD_UNIT")
        events.append(Event(
            boot_id=boot_id, timestamp=timestamp, source=source, unit=unit,
            priority=priority, message=message,
            event_type="journal", signature=signature_for(message, source),
            metadata={"transport": item.get("_TRANSPORT", "unknown")},
        ))
    return events


def read_boot_events(boot_id: str, since: str | None = None) -> list[Event]:
    command = ["journalctl", f"--boot={boot_id}", "--output=json", "--no-pager",
               "--quiet"]
    if since:
        command.append(f"--since={since}")
    result = _run(command, timeout=90)
    return parse_journal_json(result.stdout.splitlines(), boot_id)



def iter_boot_events(boot_id: str, timeout: int = 90):
    """Yield journal events one JSON record at a time with a bounded idle timeout."""
    command = ["journalctl", f"--boot={boot_id}", "--output=json", "--no-pager", "--quiet"]
    if not shutil.which(command[0]):
        raise SourceError(f"Required command not found: {command[0]}")
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                               text=True, encoding="utf-8", errors="replace", bufsize=1)
    assert process.stdout is not None
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ)
    last_activity = time.monotonic()
    try:
        while True:
            ready = selector.select(timeout=max(0.1, timeout - (time.monotonic() - last_activity)))
            if not ready:
                process.kill()
                process.wait()
                raise SourceError("journalctl timed out while reading boot records")
            line = process.stdout.readline()
            if line == "":
                break
            last_activity = time.monotonic()
            yield from parse_journal_json([line], boot_id)
        return_code = process.wait(timeout=5)
        if return_code:
            raise SourceError(f"journalctl exited with status {return_code}")
    except Exception:
        if process.poll() is None:
            process.kill()
            process.wait()
        raise
    finally:
        selector.close()
        process.stdout.close()
