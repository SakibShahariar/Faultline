"""Optional lightweight pre-incident resource sampler."""
from __future__ import annotations

import glob
import os
import re
import signal
import time
from datetime import datetime, timezone
from pathlib import Path

from .settings import load_settings
from .storage import Database

_BOOT_ID_RE = re.compile(r"^[0-9a-fA-F-]{32,36}$")


def _read_meminfo(path: Path) -> dict[str, int]:
    values = {}
    try:
        for line in path.read_text(encoding="ascii", errors="replace").splitlines():
            key, _, rest = line.partition(":")
            parts = rest.strip().split()
            if len(parts) >= 2 and parts[0].isdigit():
                values[key] = int(parts[0]) * 1024
    except OSError:
        pass
    return values


def _cpu_counters(path: Path) -> tuple[int, int] | None:
    try:
        line = path.read_text(encoding="ascii").splitlines()[0]
        parts = line.split()
        if not parts or parts[0] != "cpu":
            return None
        values = [int(value) for value in parts[1:]]
        if len(values) < 4:
            return None
        idle = values[3] + (values[4] if len(values) > 4 else 0)
        return sum(values), idle
    except (OSError, ValueError, IndexError):
        return None


def _read_temperature(sys_root: Path) -> tuple[float | None, list[str]]:
    readings = []
    sources = []
    for filename in glob.glob(str(sys_root / "class/thermal/thermal_zone*/temp")):
        path = Path(filename)
        try:
            raw = int(path.read_text().strip())
            value = raw / 1000.0 if raw > 1000 else float(raw)
            if -20 <= value <= 200:
                readings.append(value)
                sources.append(path.parent.name)
        except (OSError, ValueError):
            continue
    return (max(readings) if readings else None), sources


def _read_gpu_busy(sys_root: Path) -> tuple[float | None, int]:
    readings = []
    for filename in glob.glob(str(sys_root / "class/drm/card*/device/gpu_busy_percent")):
        try:
            value = float(Path(filename).read_text().strip())
            if 0 <= value <= 100:
                readings.append(value)
        except (OSError, ValueError):
            continue
    return (sum(readings) / len(readings) if readings else None), len(readings)


def _read_disk_counters(proc_root: Path, sys_root: Path) -> tuple[int | None, int | None, int]:
    read_bytes = 0
    written_bytes = 0
    io_time_ms = 0
    devices = 0
    try:
        lines = (proc_root / "diskstats").read_text(encoding="ascii").splitlines()
    except OSError:
        return None, None, 0
    for line in lines:
        parts = line.split()
        if len(parts) < 14:
            continue
        device = parts[2]
        if (sys_root / "class/block" / device / "partition").exists():
            continue
        try:
            read_bytes += int(parts[5]) * 512
            written_bytes += int(parts[9]) * 512
            io_time_ms += int(parts[12])
            devices += 1
        except (ValueError, IndexError):
            continue
    if not devices:
        return None, None, 0
    return read_bytes, written_bytes, devices


def collect_sample(
    previous_cpu: tuple[int, int] | None = None,
    proc_root: Path = Path("/proc"),
    sys_root: Path = Path("/sys"),
) -> tuple[dict, tuple[int, int] | None]:
    counters = _cpu_counters(proc_root / "stat")
    cpu_percent = None
    if counters and previous_cpu:
        total_delta = counters[0] - previous_cpu[0]
        idle_delta = counters[1] - previous_cpu[1]
        if total_delta > 0 and 0 <= idle_delta <= total_delta:
            cpu_percent = round(100.0 * (total_delta - idle_delta) / total_delta, 1)

    memory = _read_meminfo(proc_root / "meminfo")
    mem_total = memory.get("MemTotal")
    mem_available = memory.get("MemAvailable")
    mem_used = max(0, mem_total - mem_available) if mem_total is not None and mem_available is not None else None
    swap_total = memory.get("SwapTotal")
    swap_free = memory.get("SwapFree")
    swap_used = max(0, swap_total - swap_free) if swap_total is not None and swap_free is not None else None

    temperature, temperature_sources = _read_temperature(sys_root)
    gpu_busy, gpu_count = _read_gpu_busy(sys_root)
    disk_read_bytes, disk_write_bytes, disk_devices = _read_disk_counters(
        proc_root, sys_root
    )
    try:
        boot_id = (proc_root / "sys/kernel/random/boot_id").read_text().strip()
        if not _BOOT_ID_RE.fullmatch(boot_id):
            boot_id = "unknown"
    except OSError:
        boot_id = "unknown"

    sample = {
        "boot_id": boot_id,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "cpu_percent": cpu_percent,
        "memory_used_bytes": mem_used,
        "memory_total_bytes": mem_total,
        "swap_used_bytes": swap_used,
        "swap_total_bytes": swap_total,
        "temperature_c": temperature,
        "gpu_busy_percent": gpu_busy,
        "metadata": {
            "temperature_sensors": temperature_sources,
            "gpu_devices_sampled": gpu_count,
            "disk_read_bytes": disk_read_bytes,
            "disk_write_bytes": disk_write_bytes,
            "disk_io_time_ms": disk_io_time_ms if False else None,
            "disk_devices_sampled": disk_devices,
            "cpu_available": counters is not None and previous_cpu is not None,
            "memory_available": mem_total is not None and mem_available is not None,
            "swap_available": swap_total is not None and swap_free is not None,
        },
    }
    return sample, counters


def run_sampler() -> None:
    settings = load_settings()
    if not settings["background_sampler"]:
        raise RuntimeError(
            "Resource sampling is disabled. Enable it in Faultline Preferences first."
        )

    db = Database()
    previous_cpu = None
    samples_since_prune = 0
    stopped = False

    def stop(_signum, _frame):
        nonlocal stopped
        stopped = True

    old_term = signal.signal(signal.SIGTERM, stop)
    old_int = signal.signal(signal.SIGINT, stop)
    try:
        while not stopped:
            started = time.monotonic()
            settings = load_settings()
            if not settings["background_sampler"]:
                break
            sample, previous_cpu = collect_sample(previous_cpu)
            db.add_sample(sample)
            db.set_source_status("sampler", True, "Last sample at " + sample["captured_at"])
            samples_since_prune += 1
            if samples_since_prune >= 60:
                db.prune_samples(settings["sample_retention_hours"])
                samples_since_prune = 0
            interval = settings["sample_interval_seconds"]
            time.sleep(max(0.1, interval - (time.monotonic() - started)))
    finally:
        signal.signal(signal.SIGTERM, old_term)
        signal.signal(signal.SIGINT, old_int)
        db.set_source_status("sampler", False, "Background sampler stopped")
        db.close()
