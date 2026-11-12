"""AppImage entry point for the Faultline GUI and CLI."""
from __future__ import annotations

import runpy
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(APP_ROOT))

if sys.argv[1:2] == ["--cli"]:
    del sys.argv[1]
    runpy.run_module("faultline.cli", run_name="__main__")
else:
    ui = APP_ROOT / "demo" / "native" / "main.py"
    sys.argv[0] = str(ui)
    runpy.run_path(str(ui), run_name="__main__")
