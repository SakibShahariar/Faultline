# Faultline

**Local-first Linux crash diagnosis and system forensics**

Faultline is a native GTK4/libadwaita application with an unprivileged diagnostic
collector. It examines systemd boot history, journals, coredump metadata, retained
kernel crash records, and GNOME Shell/extension errors. Findings keep their supporting
evidence and uncertainty instead of presenting guesses as confirmed root causes.

## Implemented

- Boot discovery with stable systemd boot IDs and first/last timestamps.
- Incremental journal parsing with bounded reads and source availability reporting.
- Metadata-only coredump collection; core files are never extracted automatically.
- Bounded pstore text collection, explicitly associated with the previous boot as a
  heuristic because pstore records do not reliably carry a systemd boot ID.
- Rule-based detection for OOM, kernel panic/oops, GPU reset/hang, storage I/O errors,
  GNOME Shell/Mutter failures, and userspace coredumps.
- Explicit GNOME extension error correlation when a journal record names an enabled
  extension. Correlation is not proof of causation.
- Stable event signatures, duplicate suppression, and local SQLite storage.
- Conservative shutdown assessment: an abrupt journal ending alone remains unknown.
- Native GTK4/libadwaita UI connected to real stored findings and evidence.
- Functional source/privacy/retention preferences.
- Local Markdown and JSON report export with a preview and configurable redaction.
- Optional systemd user service and low-frequency timer; no root service.
- Unit tests and GitHub Actions CI.

## Not implemented yet

- Pre-incident CPU, memory, swap, temperature, and GPU sampling.
- Next-login desktop notifications.
- Full incident recurrence analysis and cross-boot correlation.
- Dedicated timeline filtering and richer evidence inspection.
- Fedora RPM packaging and installation/uninstallation integration.

The UI labels these features as unavailable or planned rather than displaying invented
system data.

## Fedora development setup

Install dependencies:

```sh
sudo dnf install python3 python3-pip gtk4 libadwaita python3-gobject systemd
```

From the repository root:

```sh
python3 -m pip install --user -e .
faultline scan
faultline boots
python3 demo/native/main.py
```

Run tests and syntax checks:

```sh
python3 -m unittest discover -s tests -v
python3 -m compileall -q faultline tests demo/native
```

The SQLite database is stored at
`~/.local/share/faultline/crashes.db` by default, or under `$XDG_DATA_HOME`.

## Optional background collection

Faultline includes a systemd **user** timer. It runs a bounded scan three minutes
after login and then every six hours. It does not run as root or keep a resident
process running.

Install and enable the units:

```sh
mkdir -p ~/.config/systemd/user
cp data/systemd/user/faultline-collector.service ~/.config/systemd/user/
cp data/systemd/user/faultline-collector.timer ~/.config/systemd/user/
cp data/systemd/user/faultline-sampler.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now faultline-collector.timer
```

Inspect or disable it:

```sh
systemctl --user status faultline-collector.timer
journalctl --user -u faultline-collector.service
systemctl --user disable --now faultline-collector.timer
```

The timer is optional; the GUI's Scan action works independently. Scans process at
most the configured number of recent boot journals (10 by default). Older collected
records remain until the configured age-based retention policy removes them.

## Diagnostic report export

From the application, open **Reports** and choose Markdown or JSON. The preview
summarizes the included boot, finding, and event counts. Personal-data redaction is
enabled by default.

The CLI can also export reports:

```sh
faultline report --format markdown --output ~/faultline-report.md
faultline report --format json --output ~/faultline-report.json
```

Use `--include-sensitive` only when you explicitly need an unredacted local report.
Review exported files before sharing them.

## Privacy and permissions

The collector runs as the current user. It does not invoke `sudo`, install a privileged
helper, or upload diagnostic data. Journal and pstore access depend on system
configuration; inaccessible sources are reported instead of silently escalating
permissions. Reports are generated locally and only when requested.

A clean shutdown marker is positive evidence of a clean ending. A kernel panic/oops
is positive evidence of a likely kernel failure. An abrupt journal ending, OOM
activity, or a pstore-to-previous-boot association is not by itself proof of the
machine's root cause.

## Architecture

See [docs/architecture.md](docs/architecture.md) for module boundaries, data flow,
permissions, and diagnostic interpretation.
