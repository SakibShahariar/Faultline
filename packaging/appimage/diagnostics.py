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
    combined_output = result.stderr + "\\n" + result.stdout
    trace = {
        name: float(value)
        for name, value in TRACE_RE.findall(combined_output)
    }
    return {
        "returncode": result.returncode,
        "wall_seconds": round(elapsed, 3),
        "milestones_seconds": trace,
        "stdout": result.stdout[-4000:],
        "stderr": result.stderr[-8000:],
        "combined_output": combined_output[-12000:],
    }


def launch_command(target: Path, *, appimage: Path, direct_apprun: bool):
    env = os.environ.copy()
    env.update({
        "GTK_A11Y": "none",
        "GDK_BACKEND": "x11",
        "FAULTLINE_STARTUP_TRACE": "1",
    })
    if direct_apprun:
        # AppRun v2 reads AppRun.env next to itself and establishes APPDIR,
        # library paths, Python/GI paths, and the remaining runtime helpers.
        for key in ("APPDIR", "APPIMAGE", "ARGV0", "OWD", "APPIMAGE_EXTRACT_AND_RUN"):
            env.pop(key, None)
        executable = target / "AppRun"
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
                            f"{mode_name} trial {index + 1} failed: "
                            f"{sample['combined_output'][-5000:]}"
                        )
                    required_milestones = ("GTK imported", "main window mapped")
                    missing_milestones = [
                        milestone for milestone in required_milestones
                        if milestone not in sample["milestones_seconds"]
                    ]
                    if missing_milestones:
                        raise RuntimeError(
                            f"{mode_name} trial {index + 1} did not reach required "
                            f"startup milestones {missing_milestones}; this is not a "
                            f"valid GTK GUI startup sample. output: "
                            f"{sample['combined_output'][-5000:]}"
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
            name: {
                "median_wall_seconds": mode["median_wall_seconds"],
                "samples": [
                    {
                        "trial": sample["trial"],
                        "wall_seconds": sample["wall_seconds"],
                        "gtk_import_seconds": sample["milestones_seconds"].get("GTK imported"),
                        "window_mapped_seconds": sample["milestones_seconds"].get("main window mapped"),
                    }
                    for sample in mode["samples"]
                ],
            }
            for name, mode in report["modes"].items()
        },
    }, indent=2))


SYSCALL_RE = re.compile(r"^\s*\d+\s+[\d:.]+\s+([A-Za-z_]\w*)\(")
SYSCALL_DURATION_RE = re.compile(r"<([0-9]+\.[0-9]+)>\s*$")
QUOTED_PATH_RE = re.compile(r'"([^"\n]+)"')
DESCRIPTOR_PATH_RE = re.compile(r"\d+<(/[^>\s]*)")


def summarize_strace_log(log_path: Path) -> dict:
    """Aggregate a raw strace log by syscall and by file path."""
    calls: dict[str, int] = {}
    seconds: dict[str, float] = {}
    path_seconds: dict[str, float] = {}
    with log_path.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            duration_match = SYSCALL_DURATION_RE.search(line.rstrip())
            syscall_match = SYSCALL_RE.match(line)
            if duration_match is None or syscall_match is None:
                continue
            name = syscall_match.group(1)
            duration = float(duration_match.group(1))
            calls[name] = calls.get(name, 0) + 1
            seconds[name] = seconds.get(name, 0.0) + duration
            candidates = QUOTED_PATH_RE.findall(line) + DESCRIPTOR_PATH_RE.findall(line)
            path = next((item for item in candidates if item.startswith("/")), None)
            if path is not None:
                path_seconds[path] = path_seconds.get(path, 0.0) + duration
    return {
        "syscalls": [
            {
                "name": name,
                "calls": calls[name],
                "seconds": round(seconds[name], 6),
            }
            for name in sorted(calls, key=lambda item: -seconds[item])
        ],
        "paths": [
            {"path": path, "seconds": round(value, 6)}
            for path, value in sorted(
                path_seconds.items(), key=lambda item: -item[1]
            )[:20]
        ],
    }


def aggregate_trials(trials: list[dict]) -> dict:
    calls: dict[str, int] = {}
    seconds: dict[str, float] = {}
    paths: dict[str, float] = {}
    for trial in trials:
        for syscall in trial["strace_summary"]["syscalls"]:
            name = syscall["name"]
            calls[name] = calls.get(name, 0) + syscall["calls"]
            seconds[name] = seconds.get(name, 0.0) + syscall["seconds"]
        for path in trial["strace_summary"]["paths"]:
            paths[path["path"]] = paths.get(path["path"], 0.0) + path["seconds"]
    return {
        "syscalls": [
            {
                "name": name,
                "calls": calls[name],
                "seconds": round(seconds[name], 6),
            }
            for name in sorted(calls, key=lambda item: -seconds[item])[:15]
        ],
        "paths": [
            {"path": path, "seconds": round(value, 6)}
            for path, value in sorted(paths.items(), key=lambda item: -item[1])[:15]
        ],
    }


def print_syscall_summary(title: str, summary: dict):
    print(f"=== {title}: dominant syscalls ===")
    for syscall in summary["syscalls"]:
        print(
            f"  {syscall['name']:<16} {syscall['calls']:>7} calls  "
            f"{syscall['seconds']:.4f}s"
        )
    print(f"=== {title}: top paths by attributed syscall time ===")
    for path in summary["paths"]:
        print(f"  {path['seconds']:.4f}s  {path['path']}")


def profile(args):
    image = args.appimage.resolve()
    if not image.is_file():
        raise SystemExit(f"AppImage not found: {image}")
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    strace = shutil.which("strace")
    if not strace:
        raise SystemExit("strace is required for the optional AppImage profile")
    runs = max(1, args.runs)

    with tempfile.TemporaryDirectory(prefix="faultline-appimage-profile-") as temporary:
        extracted = extract_appimage(image, Path(temporary) / "extract")
        mount_process = None
        mounted = None
        mount_error = None
        try:
            mount_process, mounted = mount_appimage(image)
        except Exception as exc:
            mount_error = str(exc)

        modes = [("appimage_runtime", image, False)]
        if mounted is not None:
            modes.append(("mounted_appdir_launcher", mounted / "AppRun", True))
        else:
            modes.append(("mounted_appdir_launcher_unavailable", None, True))
        modes.append(("extracted_appdir_launcher", extracted / "AppRun", True))

        report = {
            "appimage": str(image),
            "runs_per_mode": runs,
            "mount_available": mounted is not None,
            "mount_error": mount_error,
            "modes": {},
            "notes": [
                "Each mode is warmed up once, then traced for --runs trials.",
                "The normal AppImage mode is never silently replaced by extraction; "
                "a fallback is labeled explicitly in the trial record.",
                "wait4 wall time includes the launcher waiting on its child; it is "
                "not file-loading cost.",
            ],
        }

        try:
            for mode_name, executable, direct in modes:
                if executable is None:
                    report["modes"][mode_name] = {
                        "skipped": True,
                        "reason": mount_error or "FUSE mount unavailable",
                    }
                    continue
                mode_output = output / mode_name
                mode_output.mkdir(parents=True, exist_ok=True)
                base_command, base_env = launch_command(
                    executable, appimage=image, direct_apprun=direct
                )
                warmup = subprocess.run(
                    base_command,
                    env=base_env,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=120,
                    check=False,
                )
                if warmup.returncode != 0:
                    raise SystemExit(
                        f"{mode_name} warm-up failed: {(warmup.stderr + warmup.stdout)[-4000:]}"
                    )

                trials = []
                for index in range(runs):
                    trial_output = mode_output / f"trial-{index + 1}"
                    trial_output.mkdir(parents=True, exist_ok=True)
                    raw_log = trial_output / "strace.log"
                    traced_command = base_command[:4] + [
                        strace, "-f", "-yy", "-ttt", "-T",
                        "-e", "trace=%file,%process,%memory",
                        "-o", str(raw_log), "--",
                        "env", "LD_DEBUG=libs,statistics",
                    ] + base_command[4:]
                    trial_env = base_env.copy()
                    result = subprocess.run(
                        traced_command,
                        env=trial_env,
                        text=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        timeout=180,
                        check=False,
                    )
                    fallback_used = False
                    if result.returncode != 0 and not direct:
                        fallback_used = True
                        trial_env["APPIMAGE_EXTRACT_AND_RUN"] = "1"
                        result = subprocess.run(
                            traced_command,
                            env=trial_env,
                            text=True,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            timeout=180,
                            check=False,
                        )

                    combined = result.stderr + "\n" + result.stdout
                    (trial_output / "loader-output.log").write_text(
                        combined, encoding="utf-8"
                    )
                    trace = {
                        name: float(value) for name, value in TRACE_RE.findall(combined)
                    }
                    missing = [
                        name for name in ("GTK imported", "main window mapped")
                        if name not in trace
                    ]
                    (trial_output / "profile-exit-status.txt").write_text(
                        f"returncode={result.returncode}\n"
                        f"fallback_used={fallback_used}\n"
                        f"gtk_imported={trace.get('GTK imported', 'missing')}\n"
                        f"main_window_mapped={trace.get('main window mapped', 'missing')}\n",
                        encoding="utf-8",
                    )
                    if result.returncode != 0 or missing:
                        raise SystemExit(
                            f"{mode_name} trial {index + 1} failed: "
                            f"returncode={result.returncode}; missing milestones={missing}; "
                            f"output={combined[-6000:]}"
                        )

                    syscall_summary = (
                        summarize_strace_log(raw_log) if raw_log.is_file()
                        else {"syscalls": [], "paths": []}
                    )
                    trials.append({
                        "trial": index + 1,
                        "returncode": result.returncode,
                        "fallback_used": fallback_used,
                        "gtk_import_seconds": trace["GTK imported"],
                        "window_mapped_seconds": trace["main window mapped"],
                        "strace_summary": syscall_summary,
                    })

                report["modes"][mode_name] = {
                    "executable": str(executable),
                    "direct": direct,
                    "fallback_used": any(trial["fallback_used"] for trial in trials),
                    "trials": trials,
                    "aggregate": aggregate_trials(trials),
                }
        finally:
            if mount_process is not None:
                stop_mount(mount_process)

    (output / "profile-summary.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    for mode_name, mode in report["modes"].items():
        if mode.get("skipped"):
            print(f"=== {mode_name}: skipped ({mode['reason']}) ===")
            continue
        first = mode["trials"][0]
        print_syscall_summary(mode_name, mode["aggregate"])
        print(
            f"{mode_name}: GTK import {first['gtk_import_seconds']:.3f}s; "
            f"main window mapped {first['window_mapped_seconds']:.3f}s; "
            f"fallback={mode['fallback_used']}"
        )
    print(f"Wrote startup profiles to {output}")

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
        bundle_manifest = appdir / ".bundle.yml"
        if bundle_manifest.exists():
            shutil.copy2(bundle_manifest, output / "bundle.yml")
        status = appdir / "var" / "lib" / "dpkg" / "status"
        package_names = []
        if status.exists():
            shutil.copy2(status, output / "dpkg-status")
            package_names = sorted(set(re.findall(
                r"(?m)^Package: (.+)$",
                status.read_text(encoding="utf-8", errors="replace"),
            )))
            (output / "package-inventory.txt").write_text(
                "\\n".join(package_names) + "\\n", encoding="utf-8"
            )
        print(json.dumps({
            "shared_library_count": len((output / "shared-libraries.txt").read_text().splitlines()),
            "typelib_count": len((output / "gi-typelibs.txt").read_text().splitlines()),
            "package_count": len(package_names),
            "development_packages": [name for name in package_names if name.endswith("-dev")],
            "mesa_or_gpu_packages": [
                name for name in package_names
                if name.startswith(("mesa-", "libllvm", "libclc", "libvulkan", "libgbm", "libdrm"))
            ],
        }, indent=2))
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
    prof.add_argument("--runs", type=int, default=3)
    prof.set_defaults(function=profile)

    inv = subparsers.add_parser("inventory")
    inv.add_argument("--appimage", required=True, type=Path)
    inv.add_argument("--output", required=True)
    inv.set_defaults(function=inventory)

    args = parser.parse_args()
    args.function(args)


if __name__ == "__main__":
    main()
