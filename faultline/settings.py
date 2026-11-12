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
}


def settings_path() -> Path:
    config_home = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return config_home / "faultline" / "settings.json"


def load_settings() -> dict[str, Any]:
    path = settings_path()
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        loaded = {}
    settings = DEFAULT_SETTINGS.copy()
    if isinstance(loaded, dict):
        settings.update({key: value for key, value in loaded.items()
                         if key in DEFAULT_SETTINGS})
    settings["retention_days"] = _bounded_int(settings["retention_days"], 90, 1, 3650)
    settings["max_boots_per_scan"] = _bounded_int(settings["max_boots_per_scan"], 10, 1, 100)
    settings["sample_interval_seconds"] = _bounded_int(
        settings["sample_interval_seconds"], 10, 2, 300
    )
    settings["sample_retention_hours"] = _bounded_int(
        settings["sample_retention_hours"], 24, 1, 720
    )
    return settings


def _bounded_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, number))


def save_settings(settings: dict[str, Any]) -> None:
    merged = DEFAULT_SETTINGS.copy()
    merged.update({key: value for key, value in settings.items()
                   if key in DEFAULT_SETTINGS})
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
    settings = load_settings()
    settings[name] = value
    save_settings(settings)
    return load_settings()
