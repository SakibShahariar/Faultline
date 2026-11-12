# Native GTK4/libadwaita UI prototype

This is the native interface reference for Faultline. Unlike `demo/index.html`, it uses actual GTK4 and libadwaita widgets.

## Fedora

Install the runtime dependencies:

```sh
sudo dnf install gtk4 libadwaita python3-gobject
```

Run from the repository root:

```sh
python3 demo/native/main.py
```

The prototype includes the main navigation and the Overview, Incidents, Incident Details, System Health, Extensions, Reports, and Preferences pages. It uses `AdwHeaderBar`, `AdwNavigationSplitView`, `AdwNavigationPage`, `AdwPreferencesPage`, `AdwPreferencesGroup`, `AdwActionRow`, `AdwSwitchRow`, `AdwAlertDialog`, and `AdwToastOverlay`.

All records are fictional. Scanning, report export, and system collection are not implemented; the dialogs explain those boundaries rather than pretending to inspect the host.

The Python prototype is intended to run inside a GNOME/GTK desktop session. It requires a libadwaita version that provides `AdwNavigationSplitView` and `AdwAlertDialog`.
