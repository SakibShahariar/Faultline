# Native GTK4/libadwaita application

This is Faultline's native desktop interface. It uses actual GTK4 and libadwaita
widgets and reads diagnostic findings from the local SQLite database.

## Fedora

Install the runtime dependencies:

```sh
sudo dnf install gtk4 libadwaita python3-gobject python3-pip systemd
```

From the repository root, install the diagnostic core and launch the application:

```sh
python3 -m pip install --user -e .
python3 demo/native/main.py
```

The **Scan** action reads the boot journals and coredump metadata available to the
current user. It runs collection away from the GTK main thread, stores records in
the local database, and refreshes the Overview and Incidents pages when finished.
The app does not invoke sudo or request elevated permissions.

The database is stored at
`~/.local/share/faultline/crashes.db` (or under `$XDG_DATA_HOME`).

The native application currently displays database-backed findings and their linked
evidence. Resource sampling, extension correlation, report export, notifications,
and persistent settings are still under development; those screens must not be read
as proof that those features are already active.

The application requires a GNOME/GTK desktop session and a libadwaita version that
provides `AdwNavigationSplitView` and `AdwAlertDialog`.
