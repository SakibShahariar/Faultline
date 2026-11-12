"""Conservative GNOME Shell extension error correlation."""
from __future__ import annotations

import re
from datetime import datetime

from .models import Event, Finding
from .sources import SourceError, _run

_EXTENSION_PATH = re.compile(
    r"(?:extensions|gnome-shell/extensions)/([A-Za-z0-9_.@-]+)(?:/|\b)",
    re.IGNORECASE,
)
_ERROR_MARKERS = re.compile(
    r"error|exception|failed|TypeError|ReferenceError|SyntaxError|"
    r"Stack trace|JS ERROR|extension.*(disabled|crash)",
    re.IGNORECASE,
)
_SHELL_FAILURE = re.compile(
    r"(?:gnome-shell|mutter).*(?:segfault|crash|core dumped|terminated|status=11)",
    re.IGNORECASE,
)


def list_enabled_extensions() -> set[str]:
    result = _run(["gnome-extensions", "list", "--enabled"], timeout=15)
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def is_extension_error_candidate(event: Event) -> bool:
    source = event.source.lower()
    if source not in {"gnome-shell", "gjs", "mutter"} and \
            "gnome-shell" not in event.message.lower():
        return False
    return bool(_EXTENSION_PATH.search(event.message) and _ERROR_MARKERS.search(event.message))


def is_shell_failure(event: Event) -> bool:
    return bool(_SHELL_FAILURE.search(event.message))


def _timestamp(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        return None
    return parsed


def correlate_extension_events(
    events: list[Event],
    enabled_extensions: set[str],
    shell_events: list[Event] | None = None,
    window_seconds: int = 300,
) -> tuple[list[Event], list[Finding]]:
    """Match explicit enabled-extension errors to nearby Shell/Mutter failures."""
    shell_events = shell_events or []
    correlated: dict[tuple[str, str], list[str]] = {}
    matched_events = []

    for event in events:
        if not is_extension_error_candidate(event):
            continue
        match = _EXTENSION_PATH.search(event.message)
        if not match:
            continue
        extension_id = match.group(1)
        if extension_id not in enabled_extensions:
            continue
        event_time = _timestamp(event.timestamp)
        if event_time is None:
            continue

        nearby_failures = []
        for shell_event in shell_events:
            if shell_event.boot_id != event.boot_id or not is_shell_failure(shell_event):
                continue
            shell_time = _timestamp(shell_event.timestamp)
            if shell_time is None:
                continue
            if abs((shell_time - event_time).total_seconds()) <= window_seconds:
                nearby_failures.append(shell_event)

        if not nearby_failures:
            continue
        event.event_type = "extension-error"
        event.metadata["extension_id"] = extension_id
        event.metadata["correlated_shell_failures"] = len(nearby_failures)
        matched_events.append(event)
        evidence = [event.message[:500]] + [
            failure.message[:500] for failure in nearby_failures[:5]
        ]
        correlated.setdefault((event.boot_id, extension_id), []).extend(evidence)

    findings = [
        Finding(
            category="extension-error",
            title=f"Extension error near a Shell/Mutter failure: {extension_id}",
            summary=(
                "An error record explicitly references this enabled extension within "
                "five minutes of a GNOME Shell or Mutter failure. This is temporal "
                "correlation only; it does not prove the extension caused the failure."
            ),
            confidence="moderate",
            evidence=messages[:20],
        )
        for (_boot_id, extension_id), messages in correlated.items()
    ]
    return matched_events, findings
