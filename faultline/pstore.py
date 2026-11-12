"""Read retained kernel crash records from pstore locations."""
from __future__ import annotations

from pathlib import Path

from .models import Event
from .signatures import signature_for

PSTORE_PATHS = (Path("/sys/fs/pstore"), Path("/var/lib/systemd/pstore"))
MAX_RECORD_BYTES = 2 * 1024 * 1024
MAX_TOTAL_BYTES = 16 * 1024 * 1024


def read_pstore(associated_boot_id: str | None) -> list[Event]:
    """Read bounded text records; association to a boot is explicitly heuristic."""
    if not associated_boot_id:
        return []
    events: list[Event] = []
    total = 0
    seen: set[Path] = set()
    for directory in PSTORE_PATHS:
        try:
            candidates = sorted(directory.iterdir())
        except (OSError, PermissionError):
            continue
        for path in candidates:
            if path in seen or not path.is_file():
                continue
            seen.add(path)
            try:
                size = path.stat().st_size
                if size <= 0 or size > MAX_RECORD_BYTES or total + size > MAX_TOTAL_BYTES:
                    continue
                payload = path.read_bytes()
            except OSError:
                continue
            total += len(payload)
            message = payload.decode("utf-8", errors="replace").strip()
            if not message:
                continue
            events.append(Event(
                boot_id=associated_boot_id,
                timestamp="unknown",
                source="pstore",
                message=message[:MAX_RECORD_BYTES],
                event_type="pstore",
                signature=signature_for(message, "pstore"),
                metadata={
                    "filename": path.name,
                    "association": "heuristic_previous_boot",
                    "original_size": size,
                },
            ))
    return events
