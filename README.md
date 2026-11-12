# Faultline

**Linux crash diagnosis and system forensics**

Faultline is a planned native GTK4/libadwaita application for understanding Linux crashes, unexpected shutdowns, and desktop failures. It will correlate system logs, coredumps, boot records, and optional resource history to present evidence-based explanations.

## Interface prototype

Open the [interactive UI prototype](demo/index.html) in a browser.

The prototype follows GNOME/libadwaita design conventions more closely than a generic web dashboard: a compact header bar, navigation sidebar, restrained Adwaita-style surfaces, clear status indicators, responsive layouts, and preference rows. It is still a standalone HTML/CSS/JavaScript prototype—not a native GTK application and not a pixel-perfect reproduction of libadwaita widgets.

All incidents, system metrics, extension activity, and timestamps shown are fictional sample data. Buttons and controls demonstrate navigation and interaction only; the prototype does not inspect or modify the host system.

### Screens and flows

- **Overview** — system stability, recent incidents, resource snapshot, and findings that need attention.
- **Incidents** — searchable and filterable incident history.
- **Incident details** — evidence timeline, interpretation, confidence, possible explanations, and next steps.
- **System health** — resource history and availability of diagnostic sources.
- **GNOME extensions** — extension activity around Shell incidents, with correlation clearly separated from proof.
- **Reports** — report creation and privacy guidance.
- **Preferences** — general behavior, collection, privacy, notifications, and storage.
- **Dialogs** — scan, monitoring, report export, data clearing, and About.

## Product direction

The prototype is an interaction and layout roadmap for the native application. The intended implementation is:

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

The repository currently contains a browser-based interface prototype and product roadmap. The native application, collector, database, and real diagnostic engine are not implemented yet.
