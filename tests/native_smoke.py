import importlib.util
from pathlib import Path

source = Path(__file__).resolve().parents[1] / "demo" / "native" / "main.py"
spec = importlib.util.spec_from_file_location("faultline_native_smoke", source)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

app = module.FaultlineApplication()
app.register(None)
app.do_activate()
window = app.props.active_window
assert window is not None, "Faultline did not create its main window"
assert window.get_title() == "Faultline"
window.close()
app.quit()
