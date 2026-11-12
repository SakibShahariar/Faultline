# Native GTK4/libadwaita application

This is Faultline's native desktop interface. It uses GTK4 and libadwaita widgets and
reads diagnostic findings from the local SQLite database.

## Fedora

Install dependencies:

```sh
sudo dnf install python3 python3-pip gtk4 libadwaita python3-gobject systemd
```

From the repository root:

```sh
python3 -m pip install --user -e .
python3 demo/native/main.py
```

The **Scan** action reads boot journals and enabled optional sources available to the
current user. Collection runs away from the GTK main thread, stores records locally,
and refreshes the Overview and Incidents pages when finished. The app does not invoke
sudo or request elevated permissions.

The Overview, Incidents, Incident Details, System Health, Extensions, Reports, and
Preferences pages use actual GTK4/libadwaita widgets. Reports support Markdown and
JSON, with a preview and configurable privacy redaction. Source access, retention,
and scan-limit settings are persisted under `~/.config/faultline/settings.json`.

The optional systemd user timer is documented in the repository README. Resource
sampling and next-login notifications are not implemented yet; those pages describe
their status instead of showing fabricated values.

The database is stored at `~/.local/share/faultline/crashes.db` by default. It may be
moved under `$XDG_DATA_HOME` when that environment variable is set.

The application requires a GNOME/GTK desktop session and a libadwaita version that
provides `AdwNavigationSplitView` and `AdwAlertDialog`.
