#!/usr/bin/env python3
"""Verify the three public Faultline release assets and their combined checksums."""
from __future__ import annotations

import argparse
import hashlib
import re
from pathlib import Path

VERSION_PATTERN = r"\d+\.\d+\.\d+(?:-[0-9A-Za-z.]+)?"
APPIMAGE_NAME = re.compile(rf"^Faultline-({VERSION_PATTERN})-x86_64\.AppImage$")
RPM_NAME = re.compile(rf"^faultline-({VERSION_PATTERN})-\d+\.fc\d+\.noarch\.rpm$")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_release_assets(
    appimage: Path, rpm: Path, manifest: Path, version: str | None = None
) -> list[str]:
    """Return a list of problems; an empty list means the asset set is valid."""
    errors: list[str] = []
    paths = {"AppImage": appimage, "Fedora RPM": rpm, "SHA256SUMS": manifest}
    for label, path in paths.items():
        if not path.is_file():
            errors.append(f"missing {label}: {path}")
    if errors:
        return errors

    image_match = APPIMAGE_NAME.match(appimage.name)
    rpm_match = RPM_NAME.match(rpm.name)
    if image_match is None:
        errors.append(f"invalid AppImage filename: {appimage.name}")
    if rpm_match is None:
        errors.append(f"invalid Fedora RPM filename: {rpm.name}")
    versions = {match.group(1) for match in (image_match, rpm_match) if match}
    if version is not None:
        versions.add(version)
    if len(versions) != 1:
        errors.append(f"release version mismatch: {sorted(versions)}")

    entries: dict[str, str] = {}
    for line in manifest.read_text(encoding="utf-8").splitlines():
        fields = line.split()
        if not fields:
            continue
        if len(fields) != 2:
            errors.append(f"malformed manifest line: {line!r}")
            continue
        checksum, name = fields
        if name in entries:
            errors.append(f"duplicate manifest entry: {name}")
        entries[name] = checksum

    expected = {appimage.name, rpm.name}
    if set(entries) != expected:
        errors.append(
            f"SHA256SUMS must contain exactly {sorted(expected)}, got {sorted(entries)}"
        )
    for path in (appimage, rpm):
        if entries.get(path.name) != sha256(path):
            errors.append(f"checksum mismatch for {path.name}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--appimage", type=Path, required=True)
    parser.add_argument("--rpm", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--version", help="expected application version, if known")
    args = parser.parse_args()
    errors = verify_release_assets(args.appimage, args.rpm, args.manifest, args.version)
    for error in errors:
        print(f"error: {error}")
    if errors:
        return 1
    print("Release assets verified: AppImage, Fedora RPM, and combined SHA256SUMS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
