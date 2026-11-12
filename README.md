# Faultline

**Linux crash diagnosis and system forensics**

Faultline is a planned native GTK4/libadwaita application for understanding Linux crashes, unexpected shutdowns, and desktop failures. It will correlate system logs, coredumps, boot records, and optional resource history to present evidence-based explanations.

## Native UI prototype

The primary design reference is the [native GTK4/libadwaita prototype](demo/native/main.py). It uses real libadwaita widgets rather than CSS imitations.

On Fedora, install the dependencies and launch it:

```sh
sudo dnf install gtk4 libadwaita python3-gobject
python3 demo/native/main.py
```

See [native demo setup](demo/native/README.md) for details.

The native prototype includes Overview, Incidents, Incident Details, System Health, Extensions, Reports, and Preferences. It uses a GNOME-style header bar and split navigation, grouped preference pages, action rows, switch rows, native alert dialogs, and toast notifications.

A [browser-based interactive prototype](demo/index.html) is also available for quick preview. It is secondary to the native demo and only approximates libadwaita visually.

All incidents, system metrics, extension activity, and timestamps shown in both prototypes are fictional sample data. Neither prototype inspects or modifies the host system.

## Product direction

The prototypes are an interaction and layout roadmap for the actual application. The intended implementation is:

- GTK4 and libadwaita for the desktop interface.
- A small background collector, separate from the GUI.
- Local SQLite storage under `~/.local/share/faultline/`.
- Existing system sources such as previous-boot journals, `coredumpctl`, kernel messages, pstore when available, and GNOME Shell logs.
- Optional lightweight resource sampling with configurable retention.
- Rule-based diagnosis that presents supporting evidence and confidence instead of claiming an unverified root cause.
- Local-first reports with preview and explicit redaction before sharing.

### Important constraints

Some diagnostic sources are not readable by an ordinary user on every distribution. Faultline should explain missing access and continue with available sources rather than silently requesting broad privileges. Sudden power loss and hard freezes may prevent the final events or samples from being written.

## Development status

The repository currently contains UI prototypes and a product roadmap. The production collector, database, and real diagnostic engine are not implemented yet.
