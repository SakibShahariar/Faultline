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
assert window.get_visible(), "Faultline main window is not visible"
assert window.get_size_request() == (-1, -1), "Window still imposes a minimum size"
assert isinstance(window.get_content(), module.Adw.ToastOverlay)
split_view = window.get_content().get_child()
assert isinstance(split_view, module.Adw.NavigationSplitView)
assert split_view.get_sidebar() is not None
assert split_view.get_content() is not None
window.show_incident({
    "id": "FL-0001",
    "title": "Smoke-test incident",
    "severity": "Medium",
    "detail": "Synthetic UI-only evidence used by the smoke test.",
    "confidence": "Moderate",
    "boot_id": "a" * 32,
    "evidence": [("2026-11-12T09:30:00+00:00", "kernel", "Out of memory: Killed process 123")],
    "evidence_count": 1,
    "evidence_truncated": False,
})
assert window.stack.get_visible_child_name() == "incident-detail"
module.INCIDENTS = [{
    "id": "FL-0001",
    "boot_id": "a" * 32,
    "evidence": [("2026-11-10T09:00:00+00:00", "kernel", "Out of memory: Killed process 123")],
}]
window.show_recurrence({
    "signature": "fixture-signature",
    "sources": "kernel",
    "source": "kernel",
    "first_seen": "2026-11-10T09:00:00+00:00",
    "last_seen": "2026-11-11T09:00:00+00:00",
    "boot_count": 2,
    "event_count": 2,
    "occurrences_truncated": False,
    "occurrences": [{
        "boot_id": "a" * 32,
        "timestamp": "2026-11-10T09:00:00+00:00",
        "source": "kernel",
        "message": "Out of memory: Killed process 123",
    }],
})
assert window.stack.get_visible_child_name() == "recurrence-detail"
# Exercise the collapsed navigation state used by narrow tiled windows.
split_view.set_collapsed(True)
assert split_view.get_collapsed(), "Navigation split view did not collapse"
split_view.set_collapsed(False)
assert not split_view.get_collapsed(), "Navigation split view did not expand"
window.close()
app.quit()
