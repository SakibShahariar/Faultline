"""Conservative rule-based incident classification."""
from __future__ import annotations

import re
from collections import defaultdict

from .models import Event, Finding

RULES = [
    ("oom", "Out-of-memory activity", re.compile(
        r"out of memory|oom-kill|oom killer|killed process \d+", re.I),
     "The kernel recorded memory-pressure or OOM-killer activity."),
    ("kernel-panic", "Kernel panic or oops", re.compile(
        r"kernel panic|general protection fault|kernel oops|BUG: unable to handle", re.I),
     "The kernel logged a panic, oops, or fatal kernel fault."),
    ("gpu-reset", "GPU reset or hang", re.compile(
        r"gpu.*(hang|reset|timeout)|ring .* timeout|failed to.*(gpu|fence)|"
        r"amdgpu.*timeout|i915.*(hang|reset)|nouveau.*timeout", re.I),
     "Graphics-driver messages indicate a possible GPU hang or reset."),
    ("storage-error", "Storage or I/O errors", re.compile(
        r"I/O error|blk_update_request|buffer I/O error|nvme.*(timeout|reset|error)", re.I),
     "The kernel or storage stack reported an I/O or device error."),
    ("shell-restart", "GNOME Shell/Mutter restart", re.compile(
        r"(?:gnome-shell|mutter).*?(?:scheduled restart|restarting|restarted)", re.I),
     "The desktop session journal records a GNOME Shell or Mutter service restart."),
    ("shell-crash", "GNOME Shell failure", re.compile(
        r"gnome-shell.*(segfault|core dumped|terminated|code=dumped|status=11|signal 11)|"
        r"mutter.*(crash|segfault|code=dumped|status=11|signal 11)", re.I),
     "The session journal contains a GNOME Shell or Mutter failure indicator."),
    ("coredump-crash", "Application coredump", re.compile(
        r"produced a coredump", re.I),
     "systemd-coredump recorded a userspace process coredump."),
    ("application-crash", "Application crash", re.compile(
        r"segfault|core dumped|terminated by signal", re.I),
     "The journal contains a userspace process crash indicator."),
    ("pstore-crash", "Retained kernel crash record", re.compile(
        r"kernel panic|oops:|watchdog:|soft lockup|hard lockup|"
        r"BUG: unable to handle|general protection fault", re.I),
     "A retained pstore record contains kernel failure indicators."),
]


def classify(events: list[Event]) -> list[Finding]:
    grouped: dict[str, dict[tuple[str, str], str]] = defaultdict(dict)
    for event in events:
        for category, _title, pattern, _summary in RULES:
            if pattern.search(event.message):
                identity = event.signature or event.message.lower()
                grouped[category][(identity, event.timestamp)] = event.message[:500]
    findings: list[Finding] = []
    for category, title, _pattern, summary in RULES:
        records = grouped.get(category, {})
        evidence = list(records.values())
        if records:
            confidence = "high" if len(records) >= 2 else "moderate"
            findings.append(Finding(category, title, summary, confidence, evidence[:20]))
    return findings
