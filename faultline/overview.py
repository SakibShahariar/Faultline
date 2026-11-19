"""Responsive libadwaita overview dashboard for Faultline."""
from __future__ import annotations

from gi.repository import Adw, Gtk


def _label(text, style=None, *, wrap=False, xalign=0):
    label = Gtk.Label(label=str(text), xalign=xalign)
    label.set_wrap(wrap)
    label.set_selectable(True)
    if style:
        label.add_css_class(style)
    return label


def _content_row(text, style="dim-label"):
    """A non-interactive Adwaita row for empty-state and explanatory text."""
    label = _label(text, style, wrap=True)
    label.set_margin_top(12)
    label.set_margin_bottom(12)
    label.set_margin_start(16)
    label.set_margin_end(16)
    row = Adw.PreferencesRow()
    row.set_child(label)
    return row


def _card(title, subtitle=None):
    """A titled Adwaita group that provides the card background and spacing."""
    group = Adw.PreferencesGroup()
    group.set_title(title)
    if subtitle:
        group.set_description(subtitle)
    return group


def _metric(title, value, detail, style=None):
    group = _card(title)
    content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
    content.set_margin_top(10)
    content.set_margin_bottom(12)
    content.set_margin_start(16)
    content.set_margin_end(16)
    value_label = _label(value, "title-1")
    if style:
        value_label.add_css_class(style)
    content.append(value_label)
    content.append(_label(detail, "dim-label", wrap=True))
    row = Adw.PreferencesRow()
    row.set_child(content)
    group.add(row)
    return group


def _flow(columns=2):
    flow = Gtk.FlowBox()
    flow.set_selection_mode(Gtk.SelectionMode.NONE)
    flow.set_homogeneous(True)
    flow.set_min_children_per_line(1)
    flow.set_max_children_per_line(columns)
    flow.set_row_spacing(14)
    flow.set_column_spacing(14)
    flow.set_activate_on_single_click(False)
    return flow


def _append_row(container, title, subtitle=None, suffix=None, callback=None, icon=None):
    row = Adw.ActionRow()
    row.set_title(title)
    if subtitle:
        row.set_subtitle(subtitle)
    if icon:
        image = Gtk.Image.new_from_icon_name(icon)
        row.add_prefix(image)
    if suffix is not None:
        row.add_suffix(suffix)
    if callback:
        row.set_activatable(True)
        row.connect("activated", callback)
    container.add(row)
    return row


def build_overview(window, incidents, boot_summary, source_status):
    """Build a spacious, responsive dashboard from the existing view models."""

    scroller = Gtk.ScrolledWindow()
    scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
    scroller.set_vexpand(True)
    scroller.set_hexpand(True)

    clamp = Adw.Clamp()
    clamp.set_maximum_size(1200)
    clamp.set_tightening_threshold(840)
    scroller.set_child(clamp)

    root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=22)
    root.set_margin_top(22)
    root.set_margin_bottom(24)
    root.set_margin_start(20)
    root.set_margin_end(20)
    clamp.set_child(root)

    intro = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
    intro.append(_label("Your system at a glance", "title-1"))
    intro.append(_label(
        "A clear view of collected diagnostic evidence, boot history, and resource samples.",
        "dim-label", wrap=True,
    ))
    root.append(intro)

    scanning = bool(getattr(window, "scanning", False))
    if scanning:
        state_text = "Scanning diagnostic sources…"
        state_style = "accent"
        state_icon = "content-loading-symbolic"
    elif window.data_loading:
        state_text = "Loading your local diagnostic history…"
        state_style = "dim-label"
        state_icon = "content-loading-symbolic"
    elif window.data_error:
        state_text = "Diagnostic history could not be loaded. Existing records were not changed."
        state_style = "error"
        state_icon = "dialog-error-symbolic"
    elif incidents:
        state_text = f"{len(incidents)} stored finding(s) are ready for review."
        state_style = "warning" if any(i.get("severity") == "High" for i in incidents) else "success"
        state_icon = "dialog-information-symbolic"
    else:
        state_text = "No findings are stored yet. Run a scan to inspect available records."
        state_style = "dim-label"
        state_icon = "emblem-system-symbolic"

    status = Adw.PreferencesGroup()
    status_content = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
    status_content.set_margin_top(12)
    status_content.set_margin_bottom(12)
    status_content.set_margin_start(16)
    status_content.set_margin_end(16)
    status_icon = Gtk.Image.new_from_icon_name(state_icon)
    status_icon.set_pixel_size(24)
    status_content.append(status_icon)
    if scanning:
        spinner = Gtk.Spinner()
        spinner.start()
        status_content.append(spinner)
    status_label = _label(state_text, state_style, wrap=True)
    status_label.set_hexpand(True)
    status_content.append(status_label)
    status_row = Adw.PreferencesRow()
    status_row.set_child(status_content)
    status.add(status_row)
    root.append(status)

    available_sources = sum(1 for item in source_status.values() if item.get("available"))
    metrics = _flow(4)
    metrics.append(_metric("Findings", len(incidents), "Stored diagnostic assessments",
                           "warning" if incidents else None))
    metrics.append(_metric("Boot records", boot_summary.get("count", 0), "Collected from systemd journal"))
    previous = (boot_summary.get("previous_status") or "Not assessed").replace("_", " ").title()
    metrics.append(_metric("Previous boot", previous, "Evidence-based shutdown assessment"))
    metrics.append(_metric("Sources available", available_sources, "Diagnostic sources checked"))
    root.append(metrics)

    sections = _flow(2)

    recent = _card(
        "Recent incidents",
        "Open a finding to inspect its assessment and supporting evidence.",
    )
    if window.data_loading:
        recent.add(_content_row("Loading incident history…"))
    elif window.data_error:
        recent.add(_content_row("Incident history is unavailable."))
    elif incidents:
        for incident in incidents[:6]:
            severity = incident.get("severity", "Unknown")
            badge = _label(severity, window.severity_style(severity))
            _append_row(
                recent, incident["title"], incident.get("subtitle"),
                badge,
                callback=lambda _row, item=incident: window.show_incident(item),
                icon=incident.get("icon", "dialog-warning-symbolic"),
            )
    else:
        recent.add(_content_row(
            "Nothing to review yet. Run a scan to inspect accessible boot journals and optional sources."
        ))
    sections.append(recent)

    patterns = _card(
        "Recurring patterns",
        "Matching event signatures recorded across multiple boots.",
    )
    if window.recurring_events:
        for item in window.recurring_events[:5]:
            title = (item.get("sources") or item.get("source") or "Unknown source")
            title += " · " + str(item.get("boot_count", 0)) + " boots"
            subtitle = item.get("example", "")
            count = _label(str(item.get("event_count", 0)) + " events", "dim-label")
            _append_row(
                patterns, title, subtitle, count,
                callback=lambda _row, recurrence=item: window.show_recurrence(recurrence),
            )
    else:
        patterns.add(_content_row(
            "No repeated signatures have been recorded across multiple boots."
        ))
    sections.append(patterns)

    resources = _card(
        "Resource snapshot",
        "Latest optional sample. Unavailable hardware metrics are not inferred.",
    )
    sample = window.latest_sample
    if sample:
        values = [
            ("Memory", window.format_sample_memory(sample["memory_used_bytes"], sample["memory_total_bytes"])),
            ("Swap", window.format_sample_memory(sample["swap_used_bytes"], sample["swap_total_bytes"])),
            ("CPU", window.format_percent(sample["cpu_percent"])),
            ("Temperature", window.format_temperature(sample["temperature_c"])),
            ("GPU load", window.format_percent(sample["gpu_busy_percent"])),
        ]
        for name, value in values:
            suffix = _label(value, "heading", xalign=1)
            suffix.set_hexpand(True)
            _append_row(resources, name, suffix=suffix)
    else:
        resources.add(_content_row(
            "No resource samples yet. Enable background resource sampling in Preferences to collect optional metrics."
        ))
    sections.append(resources)

    attention = _card(
        "Diagnostic sources",
        "Availability reflects the last recorded check, not a guarantee of system health.",
    )
    if source_status:
        for name, source in list(source_status.items())[:6]:
            available = bool(source.get("available"))
            stale = bool(source.get("stale"))
            state = "Stale" if available and stale else ("Available" if available else "Unavailable")
            style = "warning" if stale or not available else "success"
            _append_row(
                attention, name.replace("-", " ").title(),
                source.get("detail", ""), _label(state, style),
            )
    else:
        attention.add(_content_row(
            "Source status will appear after diagnostic records have been collected."
        ))
    sections.append(attention)

    root.append(sections)
    return scroller
