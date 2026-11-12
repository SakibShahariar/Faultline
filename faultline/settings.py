"""Per-user Faultline settings with safe defaults."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

DEFAULT_SETTINGS: dict[str, Any] = {
    "collect_coredumps": True,
    "collect_pstore": True,
    "correlate_extensions": True,
    "redact_reports": True,
    "retention_days": 90,
    "max_boots_per_scan": 10,
    "background_sampler": False,
    "sample_interval_seconds": 10,
    "sample_retention_hours": 24,
    "notify_new_incidents": True,
    "notification_min_severity": "low",
}
_BOOLEAN_SETTINGS = {
    "collect_coredumps", "collect_pstore", "correlate_extensions",
    "redact_reports", "background_sampler", "notify_new_incidents",
}
_NUMERIC_SETTINGS = {
    "retention_days": (90, 1, 3650),
    "max_boots_per_scan": (10, 1, 100),
    "sample_interval_seconds": (10, 2, 300),
    "sample_retention_hours": (24, 1, 720),
}


def settings_path() -> Path:
    config_home = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return config_home / "faultline" / "settings.json"


def _bounded_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    if isinstance(value, bool):
        return default
    try:
        number = int(value)
    except (TypeError, ValueError, OverflowError):
        return default
    return max(minimum, min(maximum, number))


def _normalize_settings(values: dict[str, Any] | None) -> dict[str, Any]:
    settings = DEFAULT_SETTINGS.copy()
    if isinstance(values, dict):
        settings.update({
            key: value for key, value in values.items()
            if key in DEFAULT_SETTINGS
        })
    for name in _BOOLEAN_SETTINGS:
        if not isinstance(settings[name], bool):
            settings[name] = DEFAULT_SETTINGS[name]
    for name, (default, minimum, maximum) in _NUMERIC_SETTINGS.items():
        settings[name] = _bounded_int(settings[name], default, minimum, maximum)
    if settings["notification_min_severity"] not in {"low", "medium", "high"}:
        settings["notification_min_severity"] = "low"
    return settings


def load_settings() -> dict[str, Any]:
    try:
        loaded = json.loads(settings_path().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        loaded = {}
    return _normalize_settings(loaded)


def save_settings(settings: dict[str, Any]) -> None:
    merged = _normalize_settings(settings)
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(merged, indent=2) + "\n", encoding="utf-8")
    try:
        temporary.chmod(0o600)
        temporary.replace(path)
        path.parent.chmod(0o700)
    finally:
        if temporary.exists():
            temporary.unlink()


def update_setting(name: str, value: Any) -> dict[str, Any]:
    if name not in DEFAULT_SETTINGS:
        raise KeyError(name)
    if name in _BOOLEAN_SETTINGS and not isinstance(value, bool):
        raise ValueError(f"{name} must be a boolean")
    if name == "notification_min_severity" and value not in {"low", "medium", "high"}:
        raise ValueError("notification_min_severity must be low, medium, or high")
    settings = load_settings()
    settings[name] = value
    save_settings(settings)
    return load_settings()
