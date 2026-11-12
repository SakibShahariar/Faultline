# Faultline

**Local-first Linux crash diagnosis and system forensics**

Faultline is a native GTK4/libadwaita application backed by an unprivileged diagnostic
collector. It aims to explain Linux crashes, unexpected shutdowns, and desktop failures
by correlating boot history, system journals, coredumps, kernel events, and optional
resource history. Findings retain their supporting evidence and uncertainty.

## Current implementation

The repository now contains an initial diagnostic core:

- systemd boot discovery through `journalctl --list-boots`;
- journal JSON parsing with timestamps, source metadata, and priorities;
- normalized event signatures and duplicate-event suppression;
- conservative rules for OOM, kernel panic/oops, GPU resets, storage errors, and
  GNOME Shell/Mutter failures;
- boot-ending assessment that does not mistake an abruptly ending journal for proof
  of a crash;
- versioned, local SQLite storage;
- a CLI for scanning and listing collected boots;
- unit tests and a GitHub Actions test workflow.

The native UI in `demo/native/` remains a design prototype with fictional sample
records. It is not yet connected to the diagnostic database. Coredump collection,
pstore, resource sampling, notifications, report export, and distribution packaging
are not implemented yet.

## Fedora development setup

Install the system dependencies:

```sh
sudo dnf install python3 python3-pip systemd
```

From the repository root, install Faultline in editable mode and run a scan:

```sh
python3 -m pip install --user -e .
faultline scan
faultline boots
```

You can also run the CLI without installing its entry point:

```sh
python3 -m faultline.cli scan
```

Run the test suite:

```sh
python3 -m unittest discover -s tests -v
python3 -m compileall -q faultline tests
```

The database is created at
`~/.local/share/faultline/crashes.db` (or under `$XDG_DATA_HOME` when set).

## Optional background collection

Faultline includes a low-frequency systemd **user** timer. It runs a bounded scan
three minutes after login and then every six hours. It does not run as root or keep
a resident process running.

After installing Faultline in editable mode, install and enable the units:

```sh
mkdir -p ~/.config/systemd/user
cp data/systemd/user/faultline-collector.service ~/.config/systemd/user/
cp data/systemd/user/faultline-collector.timer ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now faultline-collector.timer
```

Check the latest collection:

```sh
systemctl --user status faultline-collector.timer
journalctl --user -u faultline-collector.service
```

Disable background collection:

```sh
systemctl --user disable --now faultline-collector.timer
```

The GUI's Scan action remains available independently of the timer. Each scheduled
scan processes at most the ten most recent boot journals; older collected records
remain in the local database.

## Native UI prototype

The primary design reference is the [native GTK4/libadwaita prototype](demo/native/main.py).
To run it on Fedora:

```sh
sudo dnf install gtk4 libadwaita python3-gobject
python3 demo/native/main.py
```

See [native demo setup](demo/native/README.md). A
[browser-based prototype](demo/index.html) is also available for quick preview, but
it is secondary to the native interface.

## Privacy and permissions

The collector runs as the current user. It does not invoke `sudo`, install a privileged
helper, or upload diagnostic data. Journal access varies by distribution and user
permissions; inaccessible sources are reported rather than silently escalated.
Reports, when implemented, will be local and user-initiated.

An abrupt journal ending is not enough to conclude that a system crashed. Power loss,
hard freezes, journal retention, and permission gaps can all leave incomplete records.
Likewise, OOM activity alone does not prove that memory pressure caused a reboot.

## Architecture

See [docs/architecture.md](docs/architecture.md) for module boundaries, data flow,
permission design, and diagnostic interpretation rules.
