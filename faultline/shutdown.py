"""Evidence-based boot ending assessment.

An abrupt journal ending is not proof of a crash: power loss, hard lockups,
journal retention, and permission gaps can all produce incomplete records.
"""
from __future__ import annotations

import re

from .models import Event

_CLEAN_END = re.compile(
    r"Reached target (System Shutdown|System Power-Off|System Reboot)|"
    r"systemd-shutdown.*(powering off|rebooting)|"
    r"systemd\[1\]: Stopped target (System Shutdown|System Power-Off)",
    re.IGNORECASE,
)
_FATAL_KERNEL = re.compile(
    r"Kernel panic|Oops:|BUG: unable to handle|general protection fault",
    re.IGNORECASE,
)


def assess_shutdown(events: list[Event], current: bool = False) -> str:
    if current:
        return "current"
    if any(_CLEAN_END.search(event.message) for event in events):
        return "clean"
    if any(_FATAL_KERNEL.search(event.message) for event in events):
        return "likely_crash"
    return "unknown"
