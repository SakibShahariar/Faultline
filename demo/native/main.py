#!/usr/bin/env python3
"""Faultline native GTK4/libadwaita application."""
import argparse
import json
import os
import sys
import threading
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_STARTUP_T0 = float(os.environ.get("FAULTLINE_STARTUP_T0", time.perf_counter()))


def startup_trace(event):
    if os.environ.get("FAULTLINE_STARTUP_TRACE") == "1":
        elapsed = time.perf_counter() - _STARTUP_T0
        print(f"[Faultline startup] {event}: {elapsed:.3f}s", file=sys.stderr, flush=True)


import gi

startup_trace("PyGObject imported")
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
startup_trace("GTK and libadwaita versions selected")
from gi.repository import Gtk
startup_trace("GTK imported")
from gi.repository import Adw, Gio, GLib
startup_trace("libadwaita imported")


def evidence_detail(event):
    metadata = json.loads(event["metadata_json"])
    lines = [event["message"]]
    if metadata.get("command"):
        lines.append("Command: " + metadata["command"])
    if metadata.get("uid") is not None:
        lines.append("UID: " + str(metadata["uid"]))
    if event["source"] == "systemd-coredump":
        lines.append(
            "Stack trace summary: " +
            (metadata.get("stack_summary") or "not available from coredump metadata")
        )
    return "\n".join(lines)



INCIDENTS = []
BOOT_SUMMARY = {"count": 0, "current_started": None, "previous_status": None}
SOURCE_STATUS = {}
OPEN_INCIDENT_ID = None


class FaultlineWindow(Adw.ApplicationWindow):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_title("Faultline")
        self.set_default_size(1120, 760)
        startup_trace("window construction started")

        self.window_title = Adw.WindowTitle(title="Overview", subtitle="System summary")
        self.stack = Gtk.Stack(
            transition_type=Gtk.StackTransitionType.CROSSFADE,
            transition_duration=150,
            hexpand=True,
            vexpand=True,
        )
        self.pages = {}
        self.data_loading = True
        self.data_error = None
        self.recurring_events = []
        self.latest_sample = None
        # Ship our own symbolic navigation icons so they remain available even
        # when the host uses a minimal or incomplete icon theme.
        icon_theme = Gtk.IconTheme.get_for_display(self.get_display())
        source_icon_path = ROOT / "data" / "icons"
        if source_icon_path.is_dir():
            icon_theme.add_search_path(str(source_icon_path))
        self.nav_names = [
            ("overview", "Overview", "faultline-overview-symbolic"),
            ("incidents", "Incidents", "faultline-incidents-symbolic"),
            ("health", "System health", "faultline-health-symbolic"),
            ("extensions", "Extensions", "faultline-extensions-symbolic"),
            ("reports", "Reports", "faultline-reports-symbolic"),
            ("preferences", "Preferences", "faultline-preferences-symbolic"),
        ]
        self._build_pages()

        header = Adw.HeaderBar()
        header.set_title_widget(self.window_title)
        search_button = Gtk.Button.new_from_icon_name("system-search-symbolic")
        search_button.set_tooltip_text("Search incidents")
        search_button.add_css_class("flat")
        search_button.connect("clicked", lambda *_: self.show_page("incidents"))
        header.pack_end(search_button)

        scan_content = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.scan_spinner = Gtk.Spinner()
        self.scan_spinner.set_visible(False)
        self.scan_label = Gtk.Label(label="Scan")
        scan_content.append(self.scan_spinner)
        scan_content.append(self.scan_label)
        scan_button = Gtk.Button(child=scan_content)
        self.scan_button = scan_button
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
        collector = Gtk.Label(label="●  Optional systemd user collector", xalign=0)
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
        self.connect("map", lambda *_args: startup_trace("main window mapped"))
        startup_trace("window constructed")

        nav_list.select_row(self.nav_rows["overview"])
        self.refresh_data_async()
        startup_trace("database load scheduled")

    def refresh_data_async(self):
        """Read database-backed view models away from the GTK main thread."""
        self.data_loading = True
        self.data_error = None
        def load():
            from faultline.presentation import load_boot_summary, load_incidents, load_source_status
            from faultline.recurrence import find_recurring_events
            from faultline.storage import Database

            db = None
            try:
                db = Database()
                samples = db.latest_samples(1)
                data = {
                    "incidents": load_incidents(db),
                    "boot_summary": load_boot_summary(db),
                    "source_status": load_source_status(db),
                    "recurring_events": find_recurring_events(db),
                    "latest_sample": dict(samples[0]) if samples else None,
                }
                error = None
            except Exception as exc:
                data = None
                error = str(exc)
            finally:
                if db is not None:
                    db.close()
            GLib.idle_add(self._data_loaded, data, error)

        threading.Thread(target=load, daemon=True).start()

    def _data_loaded(self, data, error):
        global INCIDENTS, BOOT_SUMMARY, SOURCE_STATUS
        self.data_loading = False
        self.data_error = error
        startup_trace("database load completed")
        if data is not None:
            INCIDENTS = data["incidents"]
            BOOT_SUMMARY = data["boot_summary"]
            SOURCE_STATUS = data["source_status"]
            self.recurring_events = data["recurring_events"]
            self.latest_sample = data["latest_sample"]
        else:
            INCIDENTS = []
            BOOT_SUMMARY = {"count": 0, "current_started": None, "previous_status": None}
            SOURCE_STATUS = {}
            self.recurring_events = []
            self.latest_sample = None

        active_page = self.stack.get_visible_child_name() or "overview"
        for page in list(self.pages.values()):
            self.stack.remove(page)
        self.pages = {}
        self._build_pages()
        self.show_page(active_page if active_page in self.pages else "overview")
        startup_trace("first data render completed")

        if OPEN_INCIDENT_ID:
            incident = next(
                (item for item in INCIDENTS if item["id"] == OPEN_INCIDENT_ID), None
            )
            if incident:
                self.show_incident(incident)
        if error:
            self.toast("Could not load local diagnostic history: " + error)
        return GLib.SOURCE_REMOVE

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
        from faultline.settings import load_settings

        settings = load_settings()
        recurring_events = self.recurring_events
        latest_sample = self.latest_sample

        from faultline.overview import build_overview

        overview = build_overview(self, INCIDENTS, BOOT_SUMMARY, SOURCE_STATUS)
        self.stack.add_named(overview, "overview")
        self.pages["overview"] = overview

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
        group = self.group(
            page, "Resource history",
            "Most recent sample: " + (latest_sample["captured_at"] if latest_sample else "no samples recorded")
        )
        if latest_sample:
            sample_metadata = json.loads(latest_sample.get("metadata_json") or "{}")
            disk_errors = sample_metadata.get("disk_io_errors")
            for title, value, subtitle in [
                ("Memory", self.format_sample_memory(latest_sample["memory_used_bytes"], latest_sample["memory_total_bytes"]), "Used / total"),
                ("Swap", self.format_sample_memory(latest_sample["swap_used_bytes"], latest_sample["swap_total_bytes"]), "Used / total"),
                ("CPU load", self.format_percent(latest_sample["cpu_percent"]), "Last sampling interval"),
                ("Temperature", self.format_temperature(latest_sample["temperature_c"]), "Highest readable thermal zone"),
                ("GPU load", self.format_percent(latest_sample["gpu_busy_percent"]), "Supported GPU devices only"),
                ("Disk I/O errors", str(disk_errors) if disk_errors is not None else "Unavailable", "Available device counters only"),
            ]:
                self.action_row(group, title, subtitle, Gtk.Label(label=value))
        else:
            self.action_row(
                group,
                "Loading resource history" if self.data_loading else "No resource samples",
                "Reading local samples…" if self.data_loading else
                "Enable the optional background sampler in Preferences."
            )
        group = self.group(page, "Diagnostic sources", "Availability depends on system permissions and configuration.")
        for title, source, fallback in [
            ("Boot journals", "journal", "Not checked"),
            ("Application coredumps", "coredumpctl", "Not checked"),
            ("Kernel messages", "journal", "Collected through journal"),
            ("pstore", "pstore", "Not checked"),
            ("GNOME extension inventory", "gnome-extensions", "Not available on this desktop"),
            ("Resource sampler", "sampler", "Not enabled"),
        ]:
            status = SOURCE_STATUS.get(source)
            disabled = bool(status and status["detail"].startswith("Disabled in Faultline settings"))
            state = ("Disabled" if disabled else
                     ("Stale" if status["available"] and status.get("stale") else
                      ("Available" if status["available"] else "Unavailable"))) if status else (
                         "Checking…" if self.data_loading else
                         ("Unavailable" if self.data_error else fallback)
                     )
            style = ("dim-label" if disabled else
                     ("warning" if status and (not status["available"] or status.get("stale")) else
                      "success" if status else "dim-label"))
            subtitle = (
                status["detail"] + " · checked " + status["checked_at"]
                if status else None
            )
            self.action_row(group, title, subtitle, self.status_label(state, style))

        page = self.add_page("extensions", "Extensions")
        group = self.group(page, "GNOME Shell extensions",
                           "Extension activity can be correlated with incidents, but timing alone is not proof.")
        extension_status = SOURCE_STATUS.get("gnome-extensions")
        if extension_status:
            self.action_row(
                group, "Enabled extension inventory",
                extension_status["detail"] + " · checked " + extension_status["checked_at"],
                self.status_label(
                    "Stale" if extension_status["available"] and extension_status.get("stale") else
                    ("Available" if extension_status["available"] else "Unavailable"),
                    "warning" if not extension_status["available"] or extension_status.get("stale") else "success",
                ),
            )
        extension_incidents = [
            incident for incident in INCIDENTS
            if incident["category"] == "extension-error"
        ]
        if extension_incidents:
            for incident in extension_incidents:
                self.action_row(
                    group, incident["title"], incident["detail"],
                    self.status_label("Correlated", "warning"),
                    "application-x-addon-symbolic",
                    lambda *_args, item=incident: self.show_incident(item),
                )
        else:
            self.action_row(
                group, "No explicit extension error match",
                "Faultline only lists an extension when an error record explicitly references an enabled extension. No causal claim is made."
            )

        page = self.add_page("reports", "Reports")
        group = self.group(page, "Export diagnostics", "Reports are generated locally and should be reviewed before sharing.")
        self.action_row(group, "Create incident report", "Summary, evidence timeline, and assessment.",
                        Gtk.Button(label="Create"), callback=lambda *_: self.export_dialog())
        self.action_row(group, "Privacy", "Personal paths and log excerpts may contain sensitive information.",
                        self.status_label("Review before sharing", "warning"))

        page = self.add_page("preferences", "Preferences")
        group = self.group(page, "Diagnostic sources",
                           "Choose which optional sources Faultline reads during a scan.")
        for title, subtitle, key in [
            ("Application coredump metadata", "Read systemd-coredump metadata; core files are never copied.", "collect_coredumps"),
            ("Retained kernel crash records", "Read bounded text records from pstore when accessible.", "collect_pstore"),
            ("GNOME extension error correlation", "Match explicit error paths against enabled extension IDs.", "correlate_extensions"),
        ]:
            row = Adw.SwitchRow()
            row.set_title(title)
            row.set_subtitle(subtitle)
            row.set_active(bool(settings[key]))
            row.connect("notify::active", self.on_setting_switch, key)
            group.add(row)

        group = self.group(page, "Privacy",
                           "Reports are generated locally. Redaction is enabled by default.")
        row = Adw.SwitchRow()
        row.set_title("Redact personal data in reports")
        row.set_subtitle("Replace home paths, email addresses, IP addresses, MAC addresses, and bearer tokens.")
        row.set_active(bool(settings["redact_reports"]))
        row.connect("notify::active", self.on_setting_switch, "redact_reports")
        group.add(row)

        group = self.group(page, "Background collection",
                           "The optional systemd user timer runs at login and every six hours after you enable it.")
        self.action_row(group, "Collector timer",
                        "Manage with systemctl --user enable --now faultline-collector.timer")
        sampler_row = Adw.SwitchRow()
        sampler_row.set_title("Background resource sampling")
        sampler_row.set_subtitle(
            "Sample CPU, memory, swap, thermal sensors, and supported GPU load at the configured interval."
        )
        sampler_row.set_active(bool(settings["background_sampler"]))
        self.sampler_switch_handler = sampler_row.connect(
            "notify::active", self.on_sampler_switch
        )
        self.sampler_switch = sampler_row
        group.add(sampler_row)
        for title, key, minimum, maximum in [
            ("Sampling interval (seconds)", "sample_interval_seconds", 2, 300),
            ("Sample history (hours)", "sample_retention_hours", 1, 720),
        ]:
            row = Adw.ActionRow()
            row.set_title(title)
            spin = Gtk.SpinButton.new_with_range(minimum, maximum, 1)
            spin.set_value(settings[key])
            spin.connect("value-changed", self.on_setting_number, key)
            row.add_suffix(spin)
            group.add(row)

        group = self.group(page, "Storage and retention",                           "Older boot records are pruned after a successful scan. Unknown timestamps are retained.")
        self.action_row(group, "Local database", str(__import__("pathlib").Path.home() / ".local/share/faultline/crashes.db"))
        clear_button = Gtk.Button(label="Clear")
        clear_button.add_css_class("destructive-action")
        clear_button.connect("clicked", lambda *_: self.clear_history_dialog())
        self.action_row(
            group, "Clear diagnostic history",
            "Delete collected boots, events, findings, source status, and resource samples.",
            clear_button,
        )
        for title, key, minimum, maximum in [
            ("History retention (days)", "retention_days", 1, 3650),
            ("Maximum boots per scan", "max_boots_per_scan", 1, 100),
        ]:
            row = Adw.ActionRow()
            row.set_title(title)
            spin = Gtk.SpinButton.new_with_range(minimum, maximum, 1)
            spin.set_value(settings[key])
            spin.connect("value-changed", self.on_setting_number, key)
            row.add_suffix(spin)
            group.add(row)

        group = self.group(page, "Notifications",
                           "The background collector can notify about newly detected findings after login.")
        notify_row = Adw.SwitchRow()
        notify_row.set_title("Notify about new incidents")
        notify_row.set_subtitle("Do not repeat notifications for findings already stored.")
        notify_row.set_active(bool(settings["notify_new_incidents"]))
        notify_row.connect("notify::active", self.on_setting_switch, "notify_new_incidents")
        group.add(notify_row)
        severity_row = Adw.ActionRow()
        severity_row.set_title("Minimum notification severity")
        severity_dropdown = Gtk.DropDown.new_from_strings(["Low", "Medium", "High"])
        severity_dropdown.set_selected(
            {"low": 0, "medium": 1, "high": 2}.get(
                settings["notification_min_severity"], 0
            )
        )
        severity_dropdown.connect("notify::selected", self.on_notification_severity_changed)
        severity_row.add_suffix(severity_dropdown)
        group.add(severity_row)

        self.show_page("overview")

    @staticmethod
    def format_percent(value):
        return f"{value:.1f}%" if value is not None else "Unavailable"

    @staticmethod
    def format_temperature(value):
        return f"{value:.1f} °C" if value is not None else "Unavailable"

    @staticmethod
    def format_sample_memory(used, total):
        if used is None or total is None:
            return "Unavailable"
        gib = 1024 ** 3
        return f"{used / gib:.1f} / {total / gib:.1f} GiB"

    def on_sampler_switch(self, row, _property):
        import subprocess
        from faultline.settings import update_setting

        enabled = row.get_active()
        update_setting("background_sampler", enabled)
        command = (
            ["systemctl", "--user", "enable", "--now", "faultline-sampler.service"]
            if enabled else
            ["systemctl", "--user", "disable", "--now", "faultline-sampler.service"]
        )
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=15)
        except (OSError, subprocess.TimeoutExpired) as exc:
            result = None
            detail = str(exc)
        else:
            detail = result.stderr.strip() or result.stdout.strip()
        if result is None or result.returncode != 0:
            update_setting("background_sampler", not enabled)
            row.handler_block(self.sampler_switch_handler)
            row.set_active(not enabled)
            row.handler_unblock(self.sampler_switch_handler)
            self.toast("Could not change sampler service. Install its user unit first. " + detail)
            return
        self.toast("Background resource sampling enabled." if enabled else
                   "Background resource sampling disabled.")

    def clear_history_dialog(self):
        dialog = Adw.AlertDialog(
            heading="Clear diagnostic history?",
            body=(
                "This permanently deletes stored boot records, journal events, findings, "
                "source status, and resource samples from this device. Preferences remain. "
                "An enabled background sampler will continue recording new samples."
            ),
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("clear", "Clear History")
        dialog.set_response_appearance("clear", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.choose(self, None, self.clear_history_finished)

    def clear_history_finished(self, dialog, result):
        try:
            response = dialog.choose_finish(result)
        except Exception:
            return
        if response != "clear":
            return
        from faultline.storage import Database

        db = Database()
        try:
            db.clear_history()
        finally:
            db.close()
        global INCIDENTS, BOOT_SUMMARY, SOURCE_STATUS
        INCIDENTS = load_incidents()
        BOOT_SUMMARY = load_boot_summary()
        SOURCE_STATUS = load_source_status()
        for page in list(self.pages.values()):
            self.stack.remove(page)
        self.pages = {}
        self._build_pages()
        self.toast("Local diagnostic history cleared.")

    def on_notification_severity_changed(self, dropdown, _property):
        from faultline.settings import update_setting
        severity = ["low", "medium", "high"][dropdown.get_selected()]
        update_setting("notification_min_severity", severity)
        self.toast("Notification preference saved.")

    def on_setting_switch(self, row, _property, key):
        from faultline.settings import update_setting
        update_setting(key, row.get_active())
        self.toast("Preference saved.")

    def on_setting_number(self, spin, key):
        from faultline.settings import update_setting
        update_setting(key, spin.get_value_as_int())

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
            incident["severity"], self.severity_style(incident["severity"])))        self.action_row(group, "Confidence", incident.get("confidence", "Not assessed"))
        self.action_row(group, "Boot ID", incident.get("boot_id", "Unavailable"))

        group = self.group(
            page, "Counter-evidence",
            "Explicit records that conflict with a detected rule. Absence of a match does not prove the diagnosis."
        )
        if incident.get("contradicting_evidence"):
            for message in incident["contradicting_evidence"]:
                self.action_row(group, "Conflicting record", message)
        else:
            self.action_row(
                group, "No explicit counter-evidence recorded",
                "None of the collected records matched a direct counter-pattern for this finding."
            )

        group = self.group(
            page, "Evidence timeline",
            "Expand a record to inspect its original message. Related records from overlapping sources are grouped."
        )
        if incident["evidence"]:
            if incident.get("evidence_truncated"):
                self.action_row(
                    group,
                    f"Showing {len(incident['evidence'])} of {incident['evidence_count']} records",
                    "The timeline is capped to keep large incidents responsive. Export a report for the complete stored evidence.",
                )
            for time, source, detail in incident["evidence"]:
                row = Adw.ExpanderRow()
                row.set_title((time or "Timestamp unavailable") + "  ·  " + source)
                row.set_subtitle("Expand to inspect original diagnostic evidence")
                message = Gtk.Label(label=detail, xalign=0, wrap=True, selectable=True)
                message.set_margin_top(8)
                message.set_margin_bottom(8)
                message.set_margin_start(12)
                message.set_margin_end(12)
                row.add_row(message)
                group.add(row)
        else:
            self.action_row(group, "No linked records", "No matching raw event records are stored for this finding.")

        from faultline.storage import Database
        db = Database()
        try:
            samples = db.connection.execute("""
                SELECT captured_at, cpu_percent, memory_used_bytes, memory_total_bytes,
                       temperature_c, gpu_busy_percent
                FROM samples WHERE boot_id = ? ORDER BY captured_at DESC LIMIT 5
            """, (incident.get("boot_id"),)).fetchall()
        finally:
            db.close()
        group = self.group(
            page, "Resource context",
            "Recent samples from this boot. They provide context, not proof of conditions at the exact crash moment."
        )
        if samples:
            for sample in reversed(samples):
                memory = self.format_sample_memory(
                    sample["memory_used_bytes"], sample["memory_total_bytes"]
                )
                detail = (
                    f"CPU {self.format_percent(sample['cpu_percent'])} · "
                    f"Memory {memory} · "
                    f"Temperature {self.format_temperature(sample['temperature_c'])} · "
                    f"GPU {self.format_percent(sample['gpu_busy_percent'])}"
                )
                self.action_row(group, sample["captured_at"], detail)
        else:
            self.action_row(group, "No samples for this boot",
                            "Enable optional background sampling to collect resource history.")

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

    def show_recurrence(self, recurrence):
        page = self.pages.get("recurrence-detail")
        if page:
            self.stack.remove(page)
        page = Adw.PreferencesPage()
        self.pages["recurrence-detail"] = page
        self.stack.add_titled(page, "recurrence-detail", "Recurring pattern")
        self.window_title.set_title("Recurring pattern")
        self.window_title.set_subtitle(
            str(recurrence["boot_count"]) + " boots · " +
            str(recurrence["event_count"]) + " occurrences"
        )

        group = self.group(
            page, "Pattern summary",
            "Occurrences share the same normalized event signature. Similarity does not prove a shared root cause."
        )
        self.action_row(group, "Sources", recurrence.get("sources") or recurrence.get("source", "Unknown"))
        self.action_row(group, "First seen", recurrence.get("first_seen") or "Timestamp unavailable")
        self.action_row(group, "Last seen", recurrence.get("last_seen") or "Timestamp unavailable")
        self.action_row(group, "Signature", recurrence["signature"])

        group = self.group(
            page, "Occurrences",
            "Each row is one stored event. Open an associated finding when Faultline has one for that record."
        )
        if recurrence.get("occurrences_truncated"):
            self.action_row(
                group,
                f"Showing {len(recurrence['occurrences'])} of {recurrence['event_count']} occurrences",
                "The occurrence list is bounded to keep the interface responsive.",
            )
        for occurrence in recurrence.get("occurrences", []):
            row = Adw.ExpanderRow()
            row.set_title(
                (occurrence["timestamp"] or "Timestamp unavailable") +
                " · " + occurrence["source"]
            )
            row.set_subtitle("Boot " + occurrence["boot_id"][:8])
            message = Gtk.Label(label=occurrence["message"], xalign=0, wrap=True, selectable=True)
            message.set_margin_top(8)
            message.set_margin_bottom(8)
            message.set_margin_start(12)
            message.set_margin_end(12)
            row.add_row(message)
            matching_incident = next((
                incident for incident in INCIDENTS
                if incident["boot_id"] == occurrence["boot_id"]
                and any(
                    evidence[2].split("\nCommand:", 1)[0] == occurrence["message"]
                    for evidence in incident["evidence"]
                )
            ), None)
            if matching_incident:
                open_button = Gtk.Button(label="Open incident")
                open_button.add_css_class("flat")
                open_button.connect(
                    "clicked",
                    lambda *_args, item=matching_incident: self.show_incident(item),
                )
                row.add_suffix(open_button)
            group.add(row)

        navigation = self.group(page, "Navigation")
        self.action_row(
            navigation, "Back to overview", "Return to the system summary.",
            icon="go-previous-symbolic",
            callback=lambda *_: self.show_page("overview"),
        )
        self.stack.set_visible_child_name("recurrence-detail")

    def scan_dialog(self, *_args):
        dialog = Adw.AlertDialog(
            heading="Scan diagnostic records?",
            body="Faultline will read the boot journals and selected optional sources available to your user account, including coredump metadata and retained pstore records when enabled. It will not request administrator privileges.",
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
            self._set_scan_running(True)
            self.toast("Scanning available diagnostic sources…")
            threading.Thread(target=self._run_scan, daemon=True).start()

    def _set_scan_running(self, running):
        self.scan_button.set_sensitive(not running)
        self.scan_label.set_text("Scanning…" if running else "Scan")
        self.scan_spinner.set_visible(running)        if running:
            self.scan_spinner.start()
        else:
            self.scan_spinner.stop()

    def _run_scan(self):
        try:
            from faultline.collector import scan
            result = scan()
            error = None
        except Exception as exc:
            result = None
            error = str(exc)
        GLib.idle_add(self._scan_complete, result, error)

    def _scan_complete(self, result, error):
        global INCIDENTS, BOOT_SUMMARY, SOURCE_STATUS
        self._set_scan_running(False)
        if error:
            self.toast("Scan failed: " + error)
            return GLib.SOURCE_REMOVE
        self.refresh_data_async()
        result = result or {}
        findings = int(result.get("findings", 0))
        boots = int(result.get("boots_seen", 0))
        new_findings = len(result.get("new_findings", []))
        warnings = len(result.get("source_errors", []))
        if findings:
            message = f"Scan complete: {findings} finding(s) across {boots} boot(s)"
            if new_findings:
                message += f", including {new_findings} new"
        else:
            message = f"No findings detected across {boots} boot(s)"
        if warnings:
            message += f"; {warnings} source warning(s)"
        self.toast(message + ".")
        return GLib.SOURCE_REMOVE

    def export_dialog(self):
        from faultline.reports import build_report
        from faultline.settings import load_settings
        from faultline.storage import Database

        settings = load_settings()
        db = Database()
        try:
            report = build_report(db, redact=settings["redact_reports"])
        finally:
            db.close()
        boot_count = len(report["boots"])
        finding_count = sum(len(boot["findings"]) for boot in report["boots"])
        event_count = sum(len(boot["events"]) for boot in report["boots"])
        dialog = Adw.AlertDialog(
            heading="Review diagnostic report",
            body=(
                f"Preview: {boot_count} boot(s), {finding_count} finding(s), "
                f"and {event_count} event record(s).\n\n"
                + ("Personal data redaction is enabled. " if settings["redact_reports"] else
                   "Warning: personal data redaction is disabled. ")
                + "The report stays on this device; review the saved file before sharing it."
            ),
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("markdown", "Save Markdown")
        dialog.add_response("json", "Save JSON")
        dialog.set_response_appearance("markdown", Adw.ResponseAppearance.SUGGESTED)
        dialog.choose(self, None, self.export_finished)

    def export_finished(self, dialog, result):
        try:
            response = dialog.choose_finish(result)
        except Exception:
            return
        if response in ("markdown", "json"):
            self.choose_report_path(response)

    def choose_report_path(self, report_format):
        extension = "md" if report_format == "markdown" else "json"
        chooser = Gtk.FileChooserNative.new(
            "Save Faultline report", self, Gtk.FileChooserAction.SAVE,
            "Save", "Cancel",
        )
        chooser.set_current_name(f"faultline-report.{extension}")
        chooser.connect("response", self.report_path_selected, report_format)
        chooser.show()

    def report_path_selected(self, chooser, response, report_format):
        if response != Gtk.ResponseType.ACCEPT:
            chooser.destroy()
            return
        file = chooser.get_file()
        path = file.get_path() if file else None
        chooser.destroy()
        if not path:
            self.toast("Could not access the selected report path.")
            return
        try:
            from faultline.reports import build_report, write_report
            from faultline.settings import load_settings
            from faultline.storage import Database

            settings = load_settings()
            db = Database()
            try:
                report = build_report(db, redact=settings["redact_reports"])
            finally:
                db.close()
            write_report(path, report, report_format)
        except Exception as exc:
            self.toast("Report export failed: " + str(exc))
            return
        self.toast(
            "Redacted report saved." if settings["redact_reports"] else
            "Unredacted report saved. Review it carefully before sharing."
        )

    def toast(self, message):
        self.toast_overlay.add_toast(Adw.Toast.new(message))


class FaultlineApplication(Adw.Application):
    def __init__(self):
        super().__init__(
            application_id="io.github.sakibshahariar.Faultline",
            flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE,
        )
        self.startup_error = False

    def do_command_line(self, command_line):
        global OPEN_INCIDENT_ID
        argument_parser = argparse.ArgumentParser(prog="faultline-gui", add_help=False)
        argument_parser.add_argument("--incident-id")
        arguments, _unknown = argument_parser.parse_known_args(
            command_line.get_arguments()[1:]
        )
        OPEN_INCIDENT_ID = arguments.incident_id
        self.activate()
        return 1 if self.startup_error else 0

    def do_activate(self):
        try:
            window = self.props.active_window
            if not window:
                window = FaultlineWindow(application=self)
            window.present()
        except Exception:
            self.startup_error = True
            print("Faultline could not construct its graphical interface:", file=sys.stderr)
            traceback.print_exc()
            self.quit()
            return
        if OPEN_INCIDENT_ID:
            incident = next(
                (item for item in INCIDENTS if item["id"] == OPEN_INCIDENT_ID), None
            )
            if incident:
                window.show_incident(incident)
            else:
                window.show_page("incidents")


if __name__ == "__main__":
    app = FaultlineApplication()
    exit_status = app.run(None)
    raise SystemExit(1 if app.startup_error else exit_status)