# Faultline

**Linux crash diagnosis & system forensics**

Faultline is a planned native GTK4/libadwaita application for understanding Linux crashes, unexpected shutdowns, and desktop failures. It correlates system logs, coredumps, boot records, and optional resource history to present evidence-based explanations.

## UI concept

The interactive prototype lives in [`demo/index.html`](demo/index.html).

It is a browser-based design prototype, not the application itself. Open the file in a browser to explore the screens and interactions. All displayed incidents, system metrics, extensions, and timestamps are illustrative sample data; the prototype does not inspect or modify the host system.

### Screens and windows represented

- **Overview** — system stability summary, recent incidents, resource snapshot, and attention items.
- **Incidents** — searchable and filterable incident history.
- **Incident details** — evidence, event timeline, confidence, possible causes, related incidents, and suggested next steps.
- **System health** — resource history, kernel/storage/GPU/thermal signals, and collection status.
- **Extensions** — GNOME Shell and extension log correlation, with clear distinction between correlation and proof.
- **Reports** — locally saved reports and export privacy guidance.
- **Preferences** — general behavior, collection settings, privacy, notifications, and storage.
- **First-run setup** — introduction to log inspection and optional monitoring.
- **Diagnostic access dialog** — explains data-source permissions and access limitations.
- **Report export dialog** — selectable report sections and redaction controls.
- **Other dialogs** — scan confirmation, monitoring configuration, data clearing, and About.

## Product direction

The prototype is a visual and interaction roadmap for the native application. The intended implementation is:

- GTK4 and libadwaita for the desktop interface.
- A small background collector, separate from the GUI.
- Local SQLite storage under `~/.local/share/faultline/`.
- Existing system sources such as previous-boot journals, `coredumpctl`, kernel messages, pstore when available, and GNOME Shell logs.
- Optional lightweight resource sampling with configurable retention.
- Rule-based diagnosis that shows supporting evidence and confidence instead of claiming an unverified root cause.
- Local-first reports with preview and explicit redaction before sharing.

### Important constraints

Some diagnostic sources are not readable by an ordinary user on every distribution. Faultline should explain missing access and continue with available sources rather than silently requesting broad privileges. Sudden power loss and hard freezes may prevent the final events or samples from being written.

## Development status

The repository currently contains the UI concept only. The native application, collector, database, and real diagnostic engine are not implemented yet.
