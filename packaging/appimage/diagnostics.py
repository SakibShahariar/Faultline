#!/usr/bin/env python3
"""Benchmark and inspect Faultline's portable AppImage build.

The benchmark compares the normal AppImage runtime, direct AppRun execution from
a persistent FUSE mount, and direct AppRun execution from an extracted AppDir.
All application launches use the same X11/D-Bus smoke-test command.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import select
import shutil
import subprocess
import tempfile
import time
from pathlib import Path


TRACE_RE = re.compile(r"\[Faultline startup\] (.*?): ([0-9.]+)s")
LIBRARY_PATH_CACHE: dict[str, str] = {}


def run_command(command: list[str], *, env: dict[str, str], timeout: int = 90):
    started = time.perf_counter()
    result = subprocess.run(
        command,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )
    elapsed = time.perf_counter() - started
    trace = {
        name: float(value)
        for name, value in TRACE_RE.findall(result.stderr)
    }
    return {
        "returncode": result.returncode,
        "wall_seconds": round(elapsed, 3),
        "milestones_seconds": trace,
        "stdout": result.stdout[-4000:],
        "stderr": result.stderr[-8000:],
    }


def launch_command(target: Path, *, appimage: Path, direct_apprun: bool):
    env = os.environ.copy()
    env.update({
        "GTK_A11Y": "none",
        "GDK_BACKEND": "x11",
        "FAULTLINE_STARTUP_TRACE": "1",
    })
    if direct_apprun:
        appdir = target
        env.update({
            "APPDIR": str(appdir),
            "APPIMAGE": str(appimage),
            "ARGV0": str(appimage),
            "OWD": os.getcwd(),
            "PYTHONHOME": str(appdir / "usr"),
            "PYTHONPATH": str(appdir / "usr" / "share" / "faultline"),
            "PYTHONNOUSERSITE": "1",
            "GI_TYPELIB_PATH": str(appdir / "usr" / "lib" / "x86_64-linux-gnu" / "girepository-1.0"),
            "GSETTINGS_SCHEMA_DIR": str(appdir / "usr" / "share" / "glib-2.0" / "schemas"),
            "XDG_DATA_DIRS": str(appdir / "usr" / "share") + ":" + env.get("XDG_DATA_DIRS", "/usr/local/share:/usr/share"),
            "XDG_CONFIG_DIRS": str(appdir / "etc" / "xdg") + ":" + env.get("XDG_CONFIG_DIRS", "/etc/xdg"),
            "PATH": str(appdir / "usr" / "bin") + ":" + env.get("PATH", "/usr/bin:/bin"),
        })
        appdir_key = str(appdir)
        if appdir_key not in LIBRARY_PATH_CACHE:
            LIBRARY_PATH_CACHE[appdir_key] = ":".join(sorted({
                str(path.parent)
                for path in appdir.rglob("*.so*")
                if path.is_file()
            }))
        library_path = LIBRARY_PATH_CACHE[appdir_key]
        existing_library_path = env.get("LD_LIBRARY_PATH")
        if existing_library_path:
            library_path += ":" + existing_library_path
        env["LD_LIBRARY_PATH"] = library_path
        env.pop("APPIMAGE_EXTRACT_AND_RUN", None)
        executable = appdir / "usr" / "bin" / "faultline-app"
        command = [
            "dbus-run-session", "--", "xvfb-run", "-a",
            str(executable), "--smoke-test",
        ]
    else:
        # Let the AppImage runtime establish APPIMAGE, APPDIR, ARGV0, and OWD.
        for key in ("APPDIR", "APPIMAGE", "ARGV0", "OWD"):
            env.pop(key, None)
        env.pop("APPIMAGE_EXTRACT_AND_RUN", None)
        command = [
            "dbus-run-session", "--", "xvfb-run", "-a",
            str(appimage), "--smoke-test",
        ]
    return command, env


def mount_appimage(image: Path):
    process = subprocess.Popen(
        [str(image), "--appimage-mount"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    try:
        ready, _, _ = select.select([process.stdout], [], [], 20)
        if not ready:
            raise RuntimeError("AppImage mount did not report a mount point within 20 seconds")
        mountpoint = process.stdout.readline().strip()
        if not mountpoint or not Path(mountpoint).is_dir():
            stderr = process.stderr.read() if process.poll() is not None else ""
            raise RuntimeError("AppImage mount failed: " + stderr[-2000:])
        return process, Path(mountpoint)
    except Exception:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        raise


def stop_mount(process: subprocess.Popen):
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


def extract_appimage(image: Path, destination: Path):
    destination.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [str(image), "--appimage-extract"],
        cwd=destination,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=120,
        check=False,
    )
    appdir = destination / "squashfs-root"
    if result.returncode != 0 or not (appdir / "AppRun").exists():
        raise RuntimeError(
            "AppImage extraction failed: "
            + result.stderr[-3000:] + result.stdout[-1000:]
        )
    return appdir


def benchmark(args):
    image = args.appimage.resolve()
    if not image.is_file():
        raise SystemExit(f"AppImage not found: {image}")

    report = {
        "appimage": str(image),
        "appimage_bytes": image.stat().st_size,
        "runs_per_mode": args.runs,
        "modes": {},
        "notes": [
            "First trial is not a guaranteed cold page-cache measurement.",
            "All modes run the same GUI smoke test under Xvfb and a private D-Bus session.",
            "Direct packaged-launcher modes use the same bundle environment while bypassing the AppImage runtime launcher.",
        ],
    }

    with tempfile.TemporaryDirectory(prefix="faultline-appimage-bench-") as temporary:
        root = Path(temporary)
        extracted = extract_appimage(image, root / "extract")
        report["extracted_appdir_bytes"] = sum(
            item.stat().st_size for item in extracted.rglob("*") if item.is_file()
        )

        mounted = None
        mount_process = None
        try:
            mount_process, mounted = mount_appimage(image)
            report["mount_available"] = True
        except Exception as exc:
            report["mount_available"] = False
            report["mount_error"] = str(exc)

        try:
            modes = [
                ("appimage_runtime", image, False),
                ("extracted_appdir_launcher", extracted, True),
            ]
            if mounted is not None:
                modes.insert(1, ("mounted_appdir_launcher", mounted, True))

            samples_by_mode = {name: [] for name, _target, _direct in modes}
            for index in range(args.runs):
                ordered_modes = modes if index % 2 == 0 else list(reversed(modes))
                for mode_name, target, direct in ordered_modes:
                    command, env = launch_command(
                        target, appimage=image, direct_apprun=direct
                    )
                    sample = run_command(command, env=env)
                    sample["trial"] = index + 1
                    if sample["returncode"] != 0 and mode_name == "appimage_runtime":
                        # Keep a usable benchmark on runners where /dev/fuse is unavailable.
                        env["APPIMAGE_EXTRACT_AND_RUN"] = "1"
                        sample = run_command(command, env=env)
                        sample["fallback"] = "APPIMAGE_EXTRACT_AND_RUN=1"
                        sample["trial"] = index + 1
                    samples_by_mode[mode_name].append(sample)
                    if sample["returncode"] != 0:
                        raise RuntimeError(
                            f"{mode_name} trial {index + 1} failed: {sample['stderr'][-2000:]}"
                        )
                    if "main window mapped" not in sample["milestones_seconds"]:
                        raise RuntimeError(
                            f"{mode_name} trial {index + 1} exited without reaching "
                            f"the main-window-mapped milestone; this is not a valid "
                            f"GUI startup sample. stderr: {sample['stderr'][-3000:]}"
                        )

            for mode_name, samples in samples_by_mode.items():
                report["modes"][mode_name] = {
                    "samples": samples,
                    "wall_seconds": [sample["wall_seconds"] for sample in samples],
                    "median_wall_seconds": round(
                        sorted(sample["wall_seconds"] for sample in samples)[len(samples) // 2],
                        3,
                    ),
                }
        finally:
            if mount_process is not None:
                stop_mount(mount_process)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "output": str(output),
        "appimage_bytes": report["appimage_bytes"],
        "extracted_appdir_bytes": report["extracted_appdir_bytes"],
        "mount_available": report["mount_available"],
        "modes": {
            name: mode["median_wall_seconds"]
            for name, mode in report["modes"].items()
        },
    }, indent=2))


def profile(args):
    image = args.appimage.resolve()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    strace = shutil.which("strace")
    if not strace:
        raise SystemExit("strace is required for the optional AppImage profile")
    command = [
        "dbus-run-session", "--", "xvfb-run", "-a", "env",
        "GTK_A11Y=none", "GDK_BACKEND=x11", "FAULTLINE_STARTUP_TRACE=1",
        "LD_DEBUG=statistics", str(image), "--smoke-test",
    ]
    traced = [
        strace, "-f", "-c", "-w", "-o",
        str(output / "strace-summary.txt"), "--",
        *command,
    ]
    env = os.environ.copy()
    result = subprocess.run(
        traced,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=120,
        check=False,
    )
    fallback_used = False
    if result.returncode != 0:
        fallback_used = True
        fallback_command = [
            "dbus-run-session", "--", "xvfb-run", "-a", "env",
            "GTK_A11Y=none", "GDK_BACKEND=x11",
            "FAULTLINE_STARTUP_TRACE=1", "LD_DEBUG=statistics",
            "APPIMAGE_EXTRACT_AND_RUN=1", str(image), "--smoke-test",
        ]
        fallback_traced = [
            strace, "-f", "-c", "-w", "-o",
            str(output / "strace-summary.txt"), "--",
            *fallback_command,
        ]
        result = subprocess.run(
            fallback_traced,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=120,
            check=False,
        )
    (output / "loader-statistics.log").write_text(
        result.stderr + "\n" + result.stdout, encoding="utf-8"
    )
    (output / "profile-exit-status.txt").write_text(
        f"returncode={result.returncode}\nfallback_used={fallback_used}\n",
        encoding="utf-8",
    )
    if result.returncode != 0:
        raise SystemExit(
            f"Profile launch failed ({result.returncode}); see {output}/loader-statistics.log"
        )
    print(f"Wrote startup profile to {output}")


def inventory(args):
    image = args.appimage.resolve()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="faultline-appimage-inventory-") as temporary:
        appdir = extract_appimage(image, Path(temporary))
        unsquashfs = shutil.which("unsquashfs")
        if unsquashfs:
            result = subprocess.run(
                [unsquashfs, "-s", str(image)],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                check=False,
            )
            (output / "squashfs-superblock.txt").write_text(
                result.stdout, encoding="utf-8"
            )

        def write_find(name: str, pattern: str):
            paths = sorted(str(path.relative_to(appdir)) for path in appdir.rglob(pattern))
            (output / name).write_text("\n".join(paths) + "\n", encoding="utf-8")

        write_find("shared-libraries.txt", "*.so*")
        write_find("gi-typelibs.txt", "*.typelib")
        write_find("gsettings-schemas.txt", "*.gschema.xml")
        write_find("desktop-assets.txt", "*.desktop")
        (output / "appdir-size.txt").write_text(
            f"appimage_bytes={image.stat().st_size}\n"
            f"extracted_appdir_bytes={sum(p.stat().st_size for p in appdir.rglob('*') if p.is_file())}\n",
            encoding="utf-8",
        )
        status = appdir / "var" / "lib" / "dpkg" / "status"
        if status.exists():
            shutil.copy2(status, output / "dpkg-status")
    print(f"Wrote AppImage inventory to {output}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(required=True, dest="command")

    bench = subparsers.add_parser("benchmark")
    bench.add_argument("--appimage", required=True, type=Path)
    bench.add_argument("--output", required=True)
    bench.add_argument("--runs", type=int, default=3)
    bench.set_defaults(function=benchmark)

    prof = subparsers.add_parser("profile")
    prof.add_argument("--appimage", required=True, type=Path)
    prof.add_argument("--output", required=True)
    prof.set_defaults(function=profile)

    inv = subparsers.add_parser("inventory")
    inv.add_argument("--appimage", required=True, type=Path)
    inv.add_argument("--output", required=True)
    inv.set_defaults(function=inventory)

    args = parser.parse_args()
    args.function(args)


if __name__ == "__main__":
    main()
