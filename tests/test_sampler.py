import tempfile
import unittest
from pathlib import Path

from faultline.sampler import collect_sample
from faultline.storage import Database


class SamplerTests(unittest.TestCase):
    def test_collects_available_metrics_and_keeps_missing_values_nullable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            proc = root / "proc"
            sys = root / "sys"
            (proc / "sys/kernel/random").mkdir(parents=True)
            (proc / "stat").write_text("cpu 100 0 20 60 10 0 0 10\n")
            (proc / "meminfo").write_text(
                "MemTotal: 1024 kB\nMemAvailable: 400 kB\n"
                "SwapTotal: 512 kB\nSwapFree: 256 kB\n"
            )
            (proc / "sys/kernel/random/boot_id").write_text("a" * 32)
            thermal = sys / "class/thermal/thermal_zone0"
            thermal.mkdir(parents=True)
            (thermal / "temp").write_text("45000")
            gpu = sys / "class/drm/card0/device"
            gpu.mkdir(parents=True)
            (gpu / "gpu_busy_percent").write_text("40")
            sample, counters = collect_sample(
                previous_cpu=(100, 50), proc_root=proc, sys_root=sys
            )
            self.assertEqual(sample["cpu_percent"], 80.0)
            self.assertEqual(sample["memory_used_bytes"], 624 * 1024)
            self.assertEqual(sample["swap_used_bytes"], 256 * 1024)
            self.assertEqual(sample["temperature_c"], 45.0)
            self.assertEqual(sample["gpu_busy_percent"], 40.0)
            self.assertEqual(sample["boot_id"], "a" * 32)
            self.assertEqual(counters, (200, 70))

    def test_samples_are_stored_and_retained(self):
        with tempfile.TemporaryDirectory() as directory:
            db = Database(Path(directory) / "faultline.db")
            sample = {
                "boot_id": "c" * 32,
                "captured_at": "2026-11-12T06:00:00+00:00",
                "cpu_percent": 20.0,
                "memory_used_bytes": 1024,
                "memory_total_bytes": 2048,
                "swap_used_bytes": None,
                "swap_total_bytes": None,
                "temperature_c": None,
                "gpu_busy_percent": None,
                "metadata": {"gpu_devices_sampled": 0},
            }
            db.add_sample(sample)
            rows = db.latest_samples(1)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["cpu_percent"], 20.0)
            self.assertIsNone(rows[0]["gpu_busy_percent"])
            self.assertEqual(db.connection.execute("PRAGMA user_version").fetchone()[0], 2)
            old_sample = sample.copy()
            old_sample["captured_at"] = "2000-01-01T00:00:00+00:00"
            db.add_sample(old_sample)
            self.assertEqual(db.prune_samples(24), 1)
            self.assertEqual(len(db.latest_samples(10)), 1)
            db.close()

    def test_unsupported_metrics_are_not_reported_as_zero(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            proc = root / "proc"
            sys = root / "sys"
            (proc / "sys/kernel/random").mkdir(parents=True)
            (proc / "sys/kernel/random/boot_id").write_text("b" * 32)
            sample, _ = collect_sample(proc_root=proc, sys_root=sys)
            self.assertIsNone(sample["cpu_percent"])
            self.assertIsNone(sample["memory_used_bytes"])
            self.assertIsNone(sample["temperature_c"])
            self.assertIsNone(sample["gpu_busy_percent"])


if __name__ == "__main__":
    unittest.main()
