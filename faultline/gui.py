"""Launch the native Faultline GTK4/libadwaita application."""
from __future__ import annotations

import runpy
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    application = root / "demo" / "native" / "main.py"
    runpy.run_path(str(application), run_name="__main__")
    return 0
