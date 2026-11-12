import importlib.util
from pathlib import Path

source = Path(__file__).resolve().parents[1] / "demo" / "native" / "main.py"
spec = importlib.util.spec_from_file_location("faultline_native_smoke", source)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

app = module.FaultlineApplication()
app.register(None)


class CommandLine:
    def get_arguments(self):
        return ["faultline-gui", "--incident-id", "FL-0001"]


app.do_command_line(CommandLine())
assert module.OPEN_INCIDENT_ID == "FL-0001"
window = app.props.active_window
assert window is not None, "Faultline did not create its main window"
assert window.get_title() == "Faultline"
window.close()
app.quit()
