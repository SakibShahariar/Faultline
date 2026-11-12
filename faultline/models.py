"""Typed records shared by collectors, storage, and diagnosis."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class Boot:
    boot_id: str
    first_seen: str | None = None
    last_seen: str | None = None
    index: int | None = None
    current: bool = False
    shutdown_status: str = "unknown"


@dataclass(slots=True)
class Event:
    boot_id: str
    timestamp: str
    source: str
    message: str
    priority: int | None = None
    unit: str | None = None
    event_type: str = "log"
    signature: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class Finding:
    category: str
    title: str
    summary: str
    confidence: str
    evidence: list[str] = field(default_factory=list)
    contradicting_evidence: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class Sample:
    boot_id: str
    captured_at: str
    cpu_percent: float | None = None
    memory_used_bytes: int | None = None
    memory_total_bytes: int | None = None
    swap_used_bytes: int | None = None
    swap_total_bytes: int | None = None
    temperature_c: float | None = None
    gpu_busy_percent: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Incident:
    incident_id: str
    boot_id: str
    category: str
    title: str
    summary: str
    confidence: str
    first_seen: str | None = None
    last_seen: str | None = None
    evidence: list[Event] = field(default_factory=list)
