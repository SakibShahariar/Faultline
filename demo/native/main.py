#!/usr/bin/env python3
"""Faultline native libadwaita UI prototype.

Run on a GNOME/Linux desktop with GTK4, libadwaita and PyGObject installed:
    python3 demo/native/main.py

All displayed records are fictional. This prototype does not inspect the host.
"""
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, Gtk


INCIDENTS = [
    {
        "id": "FL-003",
        "title": "Memory pressure detected",
        "subtitle": "8 November 2026 · Previous boot",
        "severity": "High",
        "icon": "dialog-warning-symbolic",
        "detail": (
            "Memory pressure may have contributed to the system becoming "
            "unresponsive. OOM-killer activity is confirmed, but the reason "
            "the boot ended is not."
        ),
        "evidence": [
            ("09:40:52", "Memory pressure increased",
             "Available memory fell below the configured threshold."),
            ("09:41:03", "OOM killer invoked",
             "The kernel selected a process for termination."),
            ("09:41:09", "Last journal activity",
             "No clean shutdown sequence was found after this point."),
            ("09:42:17", "Next boot recorded",
             "The system returned without a matching clean shutdown record."),
        ],
        "causes": [
            "Memory exhaustion from one or more processes",
            "Workload exceeded available RAM and swap capacity",
            "A separate freeze or power event after OOM activity",
        ],
    },
    {
        "id": "FL-002",
        "title": "GNOME Shell restarted",
        "subtitle": "2 November 2026 · Previous boot",
        "severity": "Medium",
        "icon": "preferences-desktop-display-symbolic",
        "detail": (
            "The GNOME Shell process exited and restarted during the session. "
            "The available records do not establish what caused the exit."
        ),
        "evidence": [
            ("18:16:02", "Shell process exited",
             "The session journal recorded an unexpected process exit."),
            ("18:16:04", "Shell restarted",
             "The desktop session recovered."),
            ("18:16:08", "Extension state recorded",
             "Several extensions were enabled during the event."),
        ],
        "causes": [
            "GNOME Shell or Mutter defect",
            "Extension-triggered failure (not confirmed)",
            "Graphics driver or compositor interaction",
        ],
    },
    {
        "id": "FL-001",
        "title": "GNOME Software crashed",
        "subtitle": "29 October 2026 · Current session",
        "severity": "Low",
        "icon": "application-x-executable-symbolic",
        "detail": (
            "GNOME Software terminated unexpectedly and left an application "
            "coredump. This does not indicate a system-wide failure."
        ),
        "evidence": [
            ("12:03:11", "Application started",
             "GNOME Software launched in the user session."),
            ("12:03:44", "Process terminated",
             "The application exited unexpectedly."),
            ("12:03:45", "Coredump recorded",
             "A matching application coredump became available."),
        ],
        "causes": [
            "Application defect",
            "Library or plugin interaction",
            "Transient application state",
        ],
    },
]


class FaultlineWindow(Adw.ApplicationWindow):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_title("Faultline")
        self.set_default_size(1120, 760)
        self.set_size_request(760, 560)

        self.window_title = Adw.WindowTitle(title="Overview", subtitle="System summary")
        self.stack = Gtk.Stack(
            transition_type=Gtk.StackTransitionType.CROSSFADE,
            transition_duration=150,
            hexpand=True,
            vexpand=True,
        )
        self.pages = {}
        self._build_pages()

        header = Adw.HeaderBar()
        header.set_title_widget(self.window_title)
        search_button = Gtk.Button.new_from_icon_name("system-search-symbolic")
        search_button.set_tooltip_text("Search incidents")
        search_button.add_css_class("flat")
        search_button.connect("clicked", lambda *_: self.show_page("incidents"))
        header.pack_end(search_button)

        scan_button = Gtk.Button(label="Scan")
        scan_button.add_css_class("suggested-action")
        scan_button.connect("clicked", self.scan_dialog)
        header.pack_end(scan_button)

        content_toolbar = Adw.ToolbarView()
        content_toolbar.add_top_bar(header)
        content_toolbar.set_content(self.stack)

        sidebar_header = Adw.HeaderBar()
        sidebar_header.set_show_end_title_buttons(False)
        sidebar_header.set_title_widget(Gtk.Label(label="Faultline"))
        sidebar_toolbar = Adw.ToolbarView()
        sidebar_toolbar.add_top_bar(sidebar_header)

        nav_list = Gtk.ListBox()
        nav_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        nav_list.add_css_class("navigation-sidebar")
        nav_list.connect("row-selected", self.on_navigation_selected)

        self.nav_names = [
            ("overview", "Overview", "view-dashboard-symbolic"),
            ("incidents", "Incidents", "dialog-warning-symbolic"),
            ("health", "System health", "utilities-system-monitor-symbolic"),
            ("extensions", "Extensions", "application-x-addon-symbolic"),
            ("reports", "Reports", "document-properties-symbolic"),
            ("preferences", "Preferences", "preferences-system-symbolic"),
        ]
        self.nav_rows = {}
        for name, title, icon in self.nav_names:
            row = Gtk.ListBoxRow()
            box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            box.set_margin_top(7)
            box.set_margin_bottom(7)
            box.set_margin_start(9)
            box.set_margin_end(9)
            image = Gtk.Image.new_from_icon_name(icon)
            image.set_pixel_size(16)
            label = Gtk.Label(label=title, xalign=0, hexpand=True)
            box.append(image)
            box.append(label)
            row.set_child(box)
            row.set_name(name)
            nav_list.append(row)
            self.nav_rows[name] = row

        sidebar_content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        sidebar_content.append(nav_list)
        sidebar_content.append(Gtk.Box(vexpand=True))
        collector = Gtk.Label(label="●  Collector not connected", xalign=0)
        collector.add_css_class("dim-label")
        collector.add_css_class("caption")
        collector.set_margin_start(14)
        collector.set_margin_end(8)
        collector.set_margin_top(12)
        collector.set_margin_bottom(14)
        sidebar_content.append(Gtk.Separator())
        sidebar_content.append(collector)
        sidebar_toolbar.set_content(sidebar_content)

        split = Adw.NavigationSplitView()
        split.set_sidebar(Adw.NavigationPage.new(sidebar_toolbar, "Navigation"))
        split.set_content(Adw.NavigationPage.new(content_toolbar, "Faultline"))
        split.set_min_sidebar_width(210)
        split.set_max_sidebar_width(260)
        split.set_sidebar_width_fraction(0.22)
        self.toast_overlay = Adw.ToastOverlay()
        self.toast_overlay.set_child(split)
        self.set_content(self.toast_overlay)

        nav_list.select_row(self.nav_rows["overview"])

    def add_page(self, name, title, subtitle=None):
        page = Adw.PreferencesPage()
        page.set_name(name)
        self.stack.add_titled(page, name, title)
        self.pages[name] = page
        return page

    @staticmethod
    def group(page, title, description=None):
        group = Adw.PreferencesGroup()
        group.set_title(title)
        if description:
            group.set_description(description)
        page.add(group)
        return group

    @staticmethod
    def action_row(group, title, subtitle=None, suffix=None, icon=None, callback=None):
        row = Adw.ActionRow()
        row.set_title(title)
        if subtitle:
            row.set_subtitle(subtitle)
        if icon:
            image = Gtk.Image.new_from_icon_name(icon)
            row.add_prefix(image)
        if suffix:
            row.add_suffix(suffix)
        if callback:
            row.set_activatable(True)
            row.connect("activated", callback)
        group.add(row)
        return row

    @staticmethod
    def status_label(text, style):
        label = Gtk.Label(label=text)
        label.add_css_class("caption")
        label.add_css_class(style)
        return label

    def _build_pages(self):
        page = self.add_page("overview", "Overview")
        group = self.group(page, "System status", "A summary of recent diagnostic activity.")
        self.action_row(group, "System status", "No critical findings in the current sample data.",
                        self.status_label("Stable", "success"))
        self.action_row(group, "Incidents in the last 30 days", "One finding needs review.",
                        Gtk.Label(label="3"))
        self.action_row(group, "Current boot", "Started 8 November 2026 at 09:42.",
                        Gtk.Label(label="2d 14h"))
        self.action_row(group, "Last unexpected shutdown", "Cause has not been confirmed.",
                        Gtk.Label(label="8 Nov"))

        group = self.group(page, "Recent incidents")
        for incident in INCIDENTS:
            self.action_row(
                group, incident["title"], incident["subtitle"],
                self.status_label(incident["severity"], self.severity_style(incident["severity"])),
                incident["icon"],
                lambda _row, item=incident: self.show_incident(item),
            )

        group = self.group(page, "Resource snapshot", "Illustrative values; no live monitoring is active.")
        for title, value, subtitle in [
            ("Memory", "5.8 / 7.6 GiB", "76% used"),
            ("Swap", "1.2 / 7.6 GiB", "16% used"),
            ("CPU", "18%", "Current sample"),
            ("Disk usage", "62%", "Root filesystem"),
        ]:
            self.action_row(group, title, subtitle, Gtk.Label(label=value))

        group = self.group(page, "Needs attention")
        self.action_row(
            group, "Memory pressure before an unclean shutdown",
            "OOM-killer activity appears shortly before the last recorded journal entry. "
            "This may be related; the shutdown cause remains unknown.",
            self.status_label("Review", "warning"),
            "dialog-warning-symbolic",
            lambda *_: self.show_incident(INCIDENTS[0]),
        )

        page = self.add_page("incidents", "Incidents")
        group = self.group(page, "Incident history", "Select an incident to inspect its evidence.")
        for incident in INCIDENTS:
            self.action_row(
                group, incident["title"], incident["subtitle"],
                self.status_label(incident["severity"], self.severity_style(incident["severity"])),
                incident["icon"],
                lambda _row, item=incident: self.show_incident(item),
            )

        page = self.add_page("health", "System health")
        group = self.group(page, "Resource history", "Optional background sampling is not enabled in this UI prototype.")
        for title, value, subtitle in [
            ("Memory", "5.8 GiB", "of 7.6 GiB · 76% used"),
            ("Swap", "1.2 GiB", "of 7.6 GiB · 16% used"),
            ("CPU load", "18%", "Illustrative current sample"),
        ]:
            self.action_row(group, title, subtitle, Gtk.Label(label=value))
        group = self.group(page, "Diagnostic sources", "Availability depends on system permissions and configuration.")
        for title, state, style in [
            ("Previous boot journal", "Available", "success"),
            ("Application coredumps", "Available", "success"),
            ("Kernel messages", "Limited access", "warning"),
            ("pstore", "Not detected", "dim-label"),
            ("Resource sampler", "Disabled", "dim-label"),
        ]:
            self.action_row(group, title, suffix=self.status_label(state, style))

        page = self.add_page("extensions", "Extensions")
        group = self.group(page, "GNOME Shell extensions",
                           "Extension activity can be correlated with incidents, but timing alone is not proof.")
        for title, subtitle, state in [
            ("Blur my Shell", "Enabled during the Shell restart session.", "Review logs"),
            ("Dash to Dock", "No matching error found in the sample.", "No signal"),
            ("GSConnect", "No matching error found in the sample.", "No signal"),
        ]:
            self.action_row(group, title, subtitle, self.status_label(state, "warning" if state == "Review logs" else "dim-label"))

        page = self.add_page("reports", "Reports")
        group = self.group(page, "Export diagnostics", "Reports are generated locally and should be reviewed before sharing.")
        self.action_row(group, "Create incident report", "Summary, evidence timeline, and assessment.",
                        Gtk.Button(label="Create"), callback=lambda *_: self.export_dialog())
        self.action_row(group, "Privacy", "Personal paths and log excerpts may contain sensitive information.",
                        self.status_label("Review before sharing", "warning"))

        page = self.add_page("preferences", "Preferences")
        group = self.group(page, "Collection", "Choose which diagnostic sources Faultline should inspect.")
        for title, subtitle, enabled in [
            ("Inspect logs on startup", "Look for new boot and crash records.", True),
            ("Background resource monitoring", "Collect lightweight CPU, memory, and thermal samples.", False),
            ("Monitor GNOME Shell logs", "Correlate desktop restarts with session events.", True),
        ]:
            row = Adw.SwitchRow()
            row.set_title(title)
            row.set_subtitle(subtitle)
            row.set_active(enabled)
            group.add(row)

        group = self.group(page, "Privacy", "Diagnostic data stays on this device unless you export it.")
        for title, subtitle, enabled in [
            ("Redact home directory paths", "Replace personal paths in generated reports.", True),
            ("Include application logs in reports", "Application logs may contain private information.", False),
        ]:
            row = Adw.SwitchRow()
            row.set_title(title)
            row.set_subtitle(subtitle)
            row.set_active(enabled)
            group.add(row)

        group = self.group(page, "Notifications")
        for title, subtitle, enabled in [
            ("Notify about new incidents", "Show a desktop notification after a new finding.", True),
            ("Notify after unexpected shutdown", "Summarize findings after the next login.", True),
        ]:
            row = Adw.SwitchRow()
            row.set_title(title)
            row.set_subtitle(subtitle)
            row.set_active(enabled)
            group.add(row)

        group = self.group(page, "Storage")
        self.action_row(group, "Local database", "~/.local/share/faultline/crashes.db")
        self.action_row(group, "Retention", "Keep diagnostic history for 90 days.")

        self.show_page("overview")

    @staticmethod
    def severity_style(severity):
        return {"High": "error", "Medium": "warning", "Low": "accent"}.get(severity, "dim-label")

    def on_navigation_selected(self, _listbox, row):
        if row is None:
            return
        name = row.get_name()
        if name:
            self.show_page(name)

    def show_page(self, name):
        if name not in self.pages:
            return
        self.stack.set_visible_child_name(name)
        title = dict((key, label) for key, label, _icon in self.nav_names).get(name, "Overview")
        self.window_title.set_title(title)
        subtitles = {
            "overview": "System summary",
            "incidents": "Crash and shutdown history",
            "health": "Resource and diagnostic sources",
            "extensions": "Desktop diagnostics",
            "reports": "Export and sharing",
            "preferences": "Application settings",
        }
        self.window_title.set_subtitle(subtitles.get(name, ""))

    def show_incident(self, incident):
        page = self.pages.get("incident-detail")
        if page:
            self.stack.remove(page)
        page = Adw.PreferencesPage()
        self.pages["incident-detail"] = page
        self.stack.add_titled(page, "incident-detail", "Incident details")
        self.window_title.set_title(incident["title"])
        self.window_title.set_subtitle(incident["id"] + " · " + incident["severity"] + " severity")

        group = self.group(page, "Assessment", incident["detail"])
        self.action_row(group, "Severity", suffix=self.status_label(
            incident["severity"], self.severity_style(incident["severity"])))
        self.action_row(group, "Confidence", "Evidence supports the event classification; root cause may remain uncertain.")

        group = self.group(page, "Evidence timeline")
        for time, title, detail in incident["evidence"]:
            self.action_row(group, time + "  ·  " + title, detail)

        group = self.group(page, "Possible explanations",
                           "These are hypotheses to investigate, not confirmed causes.")
        for cause in incident["causes"]:
            self.action_row(group, cause)

        group = self.group(page, "Next steps")
        self.action_row(group, "Inspect related journal records",
                        "Review the original records around the incident timestamp.")
        self.action_row(group, "Compare repeated incidents",
                        "Look for the same signature in earlier boots.")

        group = self.group(page, "Navigation")
        self.action_row(group, "Back to incidents", "Return to the incident list.",
                        icon="go-previous-symbolic",
                        callback=lambda *_: self.show_page("incidents"))
        self.stack.set_visible_child_name("incident-detail")

    def scan_dialog(self, *_args):
        dialog = Adw.AlertDialog(
            heading="Scan diagnostic records?",
            body="Faultline will inspect available boot journals, coredumps, and desktop logs. This prototype does not access your system.",
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("scan", "Start Scan")
        dialog.set_response_appearance("scan", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("scan")
        dialog.set_close_response("cancel")
        dialog.choose(self, None, self.scan_finished)

    def scan_finished(self, dialog, result):
        try:
            response = dialog.choose_finish(result)
        except Exception:
            return
        if response == "scan":
            self.toast("Scan is a UI prototype only.")

    def export_dialog(self):
        dialog = Adw.AlertDialog(
            heading="Create diagnostic report",
            body="The native report flow will provide a preview, selectable evidence, and privacy redaction before writing a Markdown or JSON file.",
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("create", "Create Report")
        dialog.set_response_appearance("create", Adw.ResponseAppearance.SUGGESTED)
        dialog.choose(self, None, self.export_finished)

    def export_finished(self, dialog, result):
        try:
            response = dialog.choose_finish(result)
        except Exception:
            return
        if response == "create":
            self.toast("Report export is not connected in this prototype.")

    def toast(self, message):
        self.toast_overlay.add_toast(Adw.Toast.new(message))


class FaultlineApplication(Adw.Application):
    def __init__(self):
        super().__init__(
            application_id="io.github.sakibshahariar.FaultlineDemo",
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
        )

    def do_activate(self):
        window = self.props.active_window
        if not window:
            window = FaultlineWindow(application=self)
        window.present()


if __name__ == "__main__":
    app = FaultlineApplication()
    raise SystemExit(app.run(None))
