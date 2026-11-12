"""Launch the native Faultline GTK4/libadwaita application."""
from __future__ import annotations

import runpy
import sys
from pathlib import Path


def main() -> int:
    package_root = Path(__file__).resolve().parent.parent
    candidates = [
        package_root / "demo" / "native" / "main.py",
        Path(sys.prefix) / "share" / "faultline" / "demo" / "native" / "main.py",
    ]
    application = next((path for path in candidates if path.is_file()), None)
    if application is None:
        raise SystemExit(
            "Faultline's native UI files were not found. Reinstall the application package."
        )
    runpy.run_path(str(application), run_name="__main__")
    return 0
