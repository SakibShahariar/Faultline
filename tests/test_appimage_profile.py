import importlib.util
import tempfile
import unittest
from pathlib import Path

SOURCE = (
    Path(__file__).resolve().parents[1]
    / "packaging"
    / "appimage"
    / "diagnostics.py"
)
spec = importlib.util.spec_from_file_location("faultline_appimage_diagnostics", SOURCE)
diagnostics = importlib.util.module_from_spec(spec)
spec.loader.exec_module(diagnostics)


SAMPLE_TRACE = """\
1234 12:00:00.000001 openat(AT_FDCWD, "/usr/lib/libgtk-4.so.1", O_RDONLY) = 3 <0.000100>
1234 12:00:00.000201 mmap(NULL, 4096, PROT_READ, MAP_PRIVATE, 3</usr/lib/libgtk-4.so.1>, 0) = 0x7f <0.000050>
1234 12:00:00.000301 newfstatat(AT_FDCWD, "/usr/share/foo", 0x7f) = 0 <0.000020>
this line is not a syscall
1234 12:00:00.000401 close(3) = 0 <0.000010>
"""


class AppImageProfileTests(unittest.TestCase):
    def test_summarize_strace_log(self):
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "strace.log"
            log.write_text(SAMPLE_TRACE, encoding="utf-8")
            summary = diagnostics.summarize_strace_log(log)

        by_name = {item["name"]: item for item in summary["syscalls"]}
        self.assertEqual(set(by_name), {"openat", "mmap", "newfstatat", "close"})
        self.assertEqual(by_name["openat"]["calls"], 1)
        self.assertEqual(by_name["mmap"]["seconds"], 0.00005)
        by_path = {item["path"]: item["seconds"] for item in summary["paths"]}
        self.assertEqual(by_path["/usr/lib/libgtk-4.so.1"], 0.00015)
        self.assertEqual(by_path["/usr/share/foo"], 0.00002)

    def test_profile_modes_use_appdir_roots(self):
        image = Path("/tmp/Faultline-0.1.5-x86_64.AppImage")
        mounted = Path("/tmp/mounted-appdir")
        extracted = Path("/tmp/extracted-appdir")
        modes = diagnostics.profile_modes(image, mounted, extracted)
        by_name = {name: target for name, target, _direct, _traced in modes}
        self.assertEqual(by_name["mounted_appdir_launcher"], mounted)
        self.assertEqual(by_name["extracted_appdir_launcher"], extracted)
        for name, target, direct, _traced in modes:
            if direct:
                command, _env = diagnostics.launch_command(
                    target, appimage=image, direct_apprun=True
                )
                self.assertEqual(
                    command[4], str(target / "AppRun"),
                    f"{name} must launch its AppDir's AppRun exactly once",
                )

    def test_aggregate_trials_sums_counts_and_paths(self):
        trial = {
            "strace_summary": {
                "syscalls": [{"name": "openat", "calls": 2, "seconds": 0.5}],
                "paths": [{"path": "/lib/libgtk.so", "seconds": 0.4}],
            }
        }
        aggregate = diagnostics.aggregate_trials([trial, trial])
        self.assertEqual(aggregate["syscalls"][0]["calls"], 4)
        self.assertEqual(aggregate["syscalls"][0]["seconds"], 1.0)
        self.assertEqual(aggregate["paths"][0]["seconds"], 0.8)


if __name__ == "__main__":
    unittest.main()
