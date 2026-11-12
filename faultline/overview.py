"""Responsive GTK overview dashboard for Faultline."""
from __future__ import annotations

from gi.repository import Adw, Gtk


def _label(text, style=None, *, wrap=False, xalign=0):
    label = Gtk.Label(label=str(text), xalign=xalign)
    label.set_wrap(wrap)
    label.set_selectable(True)
    if style:
        label.add_css_class(style)
    return label


def _card(title, subtitle=None):
    frame = Gtk.Frame()
    frame.add_css_class("card")
    frame.add_css_class("overview-card")
    content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
    content.set_margin_top(16)
    content.set_margin_bottom(16)
    content.set_margin_start(14)
    content.set_margin_end(14)
    heading = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
    heading.append(_label(title, "heading"))
    if subtitle:
        heading.append(_label(subtitle, "dim-label", wrap=True))
    content.append(heading)
    frame.set_child(content)
    return frame, content


def _metric(title, value, detail, style=None):
    frame, content = _card(title)
    value_label = _label(value, "title-1")
    if style:
        value_label.add_css_class(style)
    content.append(value_label)
    content.append(_label(detail, "dim-label", wrap=True))
    return frame


def _flow(columns=2):
    flow = Gtk.FlowBox()
    flow.set_selection_mode(Gtk.SelectionMode.NONE)
    flow.set_homogeneous(True)
    flow.set_min_children_per_line(1)
    flow.set_max_children_per_line(columns)
    flow.set_row_spacing(14)
    flow.set_column_spacing(14)
    flow.set_activate_on_single_click(False)
    flow.add_css_class("overview-grid")
    return flow


def _append_row(container, title, subtitle=None, suffix=None, callback=None, icon=None):
    button = Gtk.Button()
    button.add_css_class("flat")
    button.set_halign(Gtk.Align.FILL)
    button.set_hexpand(True)
    row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
    row.set_margin_top(8)
    row.set_margin_bottom(8)
    if icon:
        image = Gtk.Image.new_from_icon_name(icon)
        image.set_pixel_size(18)
        row.append(image)
    text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
    text_box.set_hexpand(True)
    text_box.append(_label(title, "heading", wrap=True))
    if subtitle:
        text_box.append(_label(subtitle, "dim-label", wrap=True))
    row.append(text_box)
    if suffix is not None:
        row.append(suffix)
    button.set_child(row)
    if callback:
        button.connect("clicked", callback)
    container.append(button)


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

    if window.data_loading:
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

    status = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
    status.add_css_class("card")
    status.set_margin_top(2)
    status.set_margin_bottom(2)
    status.set_margin_start(2)
    status.set_margin_end(2)
    status.set_hexpand(True)
    status.set_margin_top(4)
    status.set_margin_bottom(4)
    status.set_margin_start(4)
    status.set_margin_end(4)
    status.set_spacing(12)
    status_icon = Gtk.Image.new_from_icon_name(state_icon)
    status_icon.set_pixel_size(24)
    status.append(status_icon)
    status_label = _label(state_text, state_style, wrap=True)
    status_label.set_hexpand(True)
    status.append(status_label)
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

    recent, recent_body = _card(
        "Recent incidents",
        "Open a finding to inspect its assessment and supporting evidence.",
    )
    if window.data_loading:
        recent_body.append(_label("Loading incident history…", "dim-label"))
    elif window.data_error:
        recent_body.append(_label("Incident history is unavailable.", "dim-label"))
    elif incidents:
        for incident in incidents[:6]:
            severity = incident.get("severity", "Unknown")
            badge = _label(severity, window.severity_style(severity))
            _append_row(
                recent_body, incident["title"], incident.get("subtitle"),
                badge,
                callback=lambda _button, item=incident: window.show_incident(item),
                icon=incident.get("icon", "dialog-warning-symbolic"),
            )
    else:
        recent_body.append(_label(
            "Nothing to review yet. Run a scan to inspect accessible boot journals and optional sources.",
            "dim-label", wrap=True,
        ))
    sections.append(recent)

    patterns, patterns_body = _card(
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
                patterns_body, title, subtitle, count,
                callback=lambda _button, recurrence=item: window.show_recurrence(recurrence),
            )
    else:
        patterns_body.append(_label(
            "No repeated signatures have been recorded across multiple boots.",
            "dim-label", wrap=True,
        ))
    sections.append(patterns)

    resources, resources_body = _card(
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
            line = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            line.append(_label(name, "dim-label"))
            value_label = _label(value, "heading", xalign=1)
            value_label.set_hexpand(True)
            line.append(value_label)
            resources_body.append(line)
    else:
        resources_body.append(_label(
            "No resource samples yet. Enable background resource sampling in Preferences to collect optional metrics.",
            "dim-label", wrap=True,
        ))
    sections.append(resources)

    attention, attention_body = _card(
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
                attention_body, name.replace("-", " ").title(),
                source.get("detail", ""), _label(state, style),
            )
    else:
        attention_body.append(_label(
            "Source status will appear after diagnostic records have been collected.",
            "dim-label", wrap=True,
        ))
    sections.append(attention)

    root.append(sections)
    return scroller
