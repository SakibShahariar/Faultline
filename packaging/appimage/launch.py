"""AppImage entry point for the Faultline GUI and CLI."""
from __future__ import annotations

import os
import runpy
import sys
import time
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(APP_ROOT))
STARTUP_T0 = time.perf_counter()
os.environ.setdefault("FAULTLINE_STARTUP_T0", str(STARTUP_T0))
if os.environ.get("FAULTLINE_STARTUP_TRACE") == "1":
    print("[Faultline startup] bundled Python entrypoint: 0.000s", file=sys.stderr, flush=True)

if sys.argv[1:2] == ["--smoke-test"]:
    del sys.argv[1]
    runpy.run_path(str(APP_ROOT / "tests" / "native_smoke.py"), run_name="__main__")
elif sys.argv[1:2] == ["--cli"]:
    del sys.argv[1]
    runpy.run_module("faultline.cli", run_name="__main__")
else:
    ui = APP_ROOT / "demo" / "native" / "main.py"
    sys.argv[0] = str(ui)
    runpy.run_path(str(ui), run_name="__main__")
