# Faultline

**Local-first Linux crash diagnosis and system forensics.**

Faultline is a native GTK4/libadwaita application and optional user-session
collector. It gathers available evidence from systemd boot history, the journal,
coredump metadata, kernel/pstore records, and GNOME Shell/Mutter failures. Findings
retain their supporting events and uncertainty: correlation is not presented as
proof of causation.

## Current capabilities

- Boot history and conservative unexpected-shutdown assessment.
- Bounded, incremental journal collection with source availability reporting.
- Metadata-only coredump inspection; core files are not extracted automatically.
- Kernel panic/oops, OOM, GPU reset, storage I/O, GNOME Shell/Mutter, and userspace
  crash evidence.
- Explicit extension-error correlation against nearby Shell failures.
- Event normalization, stable signatures, duplicate suppression, and recurrence
  matching across boots.
- Supporting and explicit counter-evidence, with confidence reduced when a direct
  contradiction is present.
- Local SQLite storage with schema migrations, retention, and clear-history support.
- GTK4/libadwaita screens for overview, incidents, evidence, system health,
  extensions, reports, and preferences.
- Optional low-frequency resource sampling (including available disk I/O error
  counters) and optional actionable desktop
  notifications for newly detected findings.
- Local Markdown/JSON report export with personal-data redaction enabled by default.
- Optional systemd **user** timer; no privileged daemon and no automatic upload.

Unsupported or inaccessible sources remain visibly unavailable. Missing metrics
are represented as unavailable rather than zero, and abrupt journal endings alone
are not treated as proof of a crash.

## Fedora development setup

Install the runtime dependencies:

```sh
sudo dnf install python3 python3-pip python3-gobject gtk4 libadwaita systemd
```

Install Faultline from a checkout:

```sh
python3 -m venv --system-site-packages .venv
.venv/bin/python -m pip install -e .
.venv/bin/faultline scan
.venv/bin/faultline boots
.venv/bin/faultline-gui
```

Run automated checks:

```sh
python3 -m unittest discover -s tests -v
python3 -m compileall -q faultline tests demo/native
```

For Fedora RPM build instructions, see
[docs/packaging-fedora.md](docs/packaging-fedora.md) and the spec at
[packaging/rpm/faultline.spec](packaging/rpm/faultline.spec).

## Optional background collection

The user timer performs a bounded scan shortly after login and then every six
hours. It is not enabled automatically:

```sh
mkdir -p ~/.config/systemd/user
cp data/systemd/user/faultline-collector.service ~/.config/systemd/user/
cp data/systemd/user/faultline-collector.timer ~/.config/systemd/user/
cp data/systemd/user/faultline-sampler.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now faultline-collector.timer
```

The resource sampler is independently opt-in in Preferences. It records supported
CPU, memory, swap, thermal, GPU-busy, and disk-I/O counters at the configured
interval; hardware-specific metrics may be unavailable.

Inspect or disable collection:

```sh
systemctl --user status faultline-collector.timer
journalctl --user -u faultline-collector.service
systemctl --user disable --now faultline-collector.timer
```

## Reports and privacy

Open **Reports** to preview and export Markdown or JSON. The CLI equivalents are:

```sh
faultline report --format markdown --output ~/faultline-report.md
faultline report --format json --output ~/faultline-report.json
```

Use `--include-sensitive` only when you explicitly need an unredacted local report.
Review exported files before sharing them.

Faultline stores its database under `$XDG_DATA_HOME/faultline` (normally
`~/.local/share/faultline`) and preferences under `$XDG_CONFIG_HOME/faultline`.
The collector runs as the logged-in user. It does not invoke `sudo`, install a
privileged helper, or upload diagnostic data. Journal and pstore access depend on
the system's existing permissions.

## Architecture

See [docs/architecture.md](docs/architecture.md) for module boundaries, data flow,
permissions, and diagnostic interpretation.

## License

Faultline is licensed under the [MIT License](LICENSE).
