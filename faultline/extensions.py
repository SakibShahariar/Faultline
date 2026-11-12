"""Conservative GNOME Shell extension error correlation."""
from __future__ import annotations

import re

from .models import Event, Finding
from .sources import SourceError, _run

_EXTENSION_PATH = re.compile(
    r"(?:extensions|gnome-shell/extensions)/([A-Za-z0-9_.@-]+)(?:/|\\b)",
    re.IGNORECASE,
)
_ERROR_MARKERS = re.compile(
    r"error|exception|failed|TypeError|ReferenceError|SyntaxError|"
    r"Stack trace|JS ERROR|extension.*(disabled|crash)",
    re.IGNORECASE,
)


def list_enabled_extensions() -> set[str]:
    result = _run(["gnome-extensions", "list", "--enabled"], timeout=15)
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def correlate_extension_events(
    events: list[Event], enabled_extensions: set[str]
) -> tuple[list[Event], list[Finding]]:
    """Annotate only explicit extension-path matches; never assert causation."""
    correlated: dict[tuple[str, str], list[str]] = {}
    for event in events:
        if event.source.lower() not in {"gnome-shell", "gjs", "mutter"} and                 "gnome-shell" not in event.message.lower():
            continue
        match = _EXTENSION_PATH.search(event.message)
        if not match:
            continue
        extension_id = match.group(1)
        if extension_id not in enabled_extensions or not _ERROR_MARKERS.search(event.message):
            continue
        event.event_type = "extension-error"
        event.metadata["extension_id"] = extension_id
        correlated.setdefault((event.boot_id, extension_id), []).append(event.message[:500])

    findings = [
        Finding(
            category="extension-error",
            title=f"Enabled extension logged an error: {extension_id}",
            summary=(
                "An error record explicitly references this enabled extension. "
                "This is a correlation only; it does not prove the extension caused "
                "the desktop incident."
            ),
            confidence="moderate",
            evidence=messages[:20],
        )
        for (_boot_id, extension_id), messages in correlated.items()
    ]
    return events, findings
