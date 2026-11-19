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
default_width, default_height = window.get_default_size()
assert (default_width, default_height) == (960, 680), f"Unexpected initial window size: {default_width}x{default_height}"
overview = window.pages["overview"]
assert isinstance(overview, module.Gtk.ScrolledWindow), "Overview is not using the dashboard layout"
clamp = overview.get_child()
while clamp is not None and not isinstance(clamp, module.Adw.Clamp):
    clamp = clamp.get_child() if hasattr(clamp, "get_child") else None
assert isinstance(clamp, module.Adw.Clamp), "Overview is not width-clamped"
assert clamp.get_maximum_size() == 1200, "Overview width limit changed unexpectedly"
assert clamp.get_tightening_threshold() == 840, "Overview clamp threshold changed unexpectedly"
assert overview.get_policy()[0] == module.Gtk.PolicyType.NEVER, "Overview should not introduce horizontal scrolling"


def walk(widget):
    """Yield a widget and all of its GTK4 children."""
    yield widget
    children = widget.observe_children()
    for index in range(children.get_n_items()):
        child = children.get_item(index)
        if isinstance(child, module.Gtk.Widget):
            yield from walk(child)


assert any(isinstance(item, module.Adw.PreferencesGroup) for item in walk(overview)), (
    "Overview cards should use Adwaita preference groups"
)
assert not any(isinstance(item, module.Gtk.Frame) for item in walk(overview)), (
    "Overview should not use bare Gtk.Frame cards"
)
preferences = window.pages["preferences"]
assert sum(isinstance(item, module.Adw.SpinRow) for item in walk(preferences)) == 4, (
    "Numeric settings should use Adw.SpinRow"
)
assert any(isinstance(item, module.Adw.ComboRow) for item in walk(preferences)), (
    "Severity setting should use Adw.ComboRow"
)
icon_theme = module.Gtk.IconTheme.get_for_display(window.get_display())
for _name, _label, icon_name in window.nav_names:
    assert icon_theme.has_icon(icon_name), f"Missing bundled navigation icon: {icon_name}"
assert all(isinstance(row, module.Adw.ActionRow) for row in window.nav_rows.values()), (
    "Navigation entries should be Adw.ActionRow instances"
)

# Incident search filters the list and uses an Adwaita status page for empty results.
module.INCIDENTS = [{
    "id": "FL-100",
    "title": "Kernel panic after update",
    "subtitle": "Boot 12",
    "detail": "A kernel panic was recorded.",
    "severity": "High",
    "icon": "dialog-warning-symbolic",
}, {
    "id": "FL-101",
    "title": "Unexpected shutdown",
    "subtitle": "Boot 11",
    "detail": "Power loss suspected.",
    "severity": "Low",
    "icon": "dialog-warning-symbolic",
}]
window.data_loading = False
window.data_error = None
window.set_incident_filter("panic")
assert isinstance(window.pages["incidents"], module.Adw.PreferencesPage)
assert sum(isinstance(item, module.Adw.ActionRow) for item in walk(window.pages["incidents"])) == 1
window.set_incident_filter("no-such-incident")
assert isinstance(window.pages["incidents"], module.Adw.StatusPage), (
    "No search matches should show an Adwaita status page"
)
window.set_incident_filter("")
window.toggle_search()
assert window.search_button.get_active()
assert window.search_revealer.get_reveal_child()
window.close_search()
assert not window.search_button.get_active()
assert window.incident_filter == ""

assert window.get_visible(), "Faultline main window is not visible"
assert window.scan_label.get_text() == "Scan"
assert not window.scan_spinner.get_visible()
window._set_scan_running(True)
assert not window.scan_button.get_sensitive()
assert window.scan_spinner.get_visible()
assert window.scan_spinner.get_spinning()
assert window.scan_label.get_text() == "Scanning…"
assert any(isinstance(item, module.Gtk.Spinner) for item in walk(window.pages["overview"])), (
    "Scan progress should also appear on the dashboard"
)
window._set_scan_running(False)
assert window.scan_button.get_sensitive()
assert not window.scan_spinner.get_visible()
assert window.scan_label.get_text() == "Scan"
assert not any(isinstance(item, module.Gtk.Spinner) for item in walk(window.pages["overview"]))
messages = []
window.refresh_data_async = lambda: None
window.toast = messages.append
window._scan_complete(
    {"findings": 0, "boots_seen": 2, "new_findings": [], "source_errors": []},
    None,
)
assert messages[-1] == "No findings detected across 2 boot(s)."
window._scan_complete(
    {"findings": 3, "boots_seen": 2, "new_findings": [{}], "source_errors": [{}]},
    None,
)
assert messages[-1] == "Scan complete: 3 finding(s) across 2 boot(s), including 1 new; 1 source warning(s)."
requested_width, requested_height = window.get_size_request()
assert requested_width < 760 and requested_height < 560, (
    f"Window still imposes a large minimum size: {requested_width}x{requested_height}"
)
assert isinstance(window.get_content(), module.Adw.ToastOverlay)
split_view = window.get_content().get_child()
assert isinstance(split_view, module.Adw.NavigationSplitView)
assert split_view.get_min_sidebar_width() == 176
assert split_view.get_max_sidebar_width() == 224
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
