# Faultline architecture

Faultline is a local-first Linux diagnostics application. The native GTK4/libadwaita
front end is a client of the diagnostic core; it must not own privileged collection
logic or parse raw journal output itself.

## Components

- **UI** — native GTK4/libadwaita screens. Reads normalized records from local storage
  and dispatches scan requests without blocking the GTK main loop.
- **Collector** — unprivileged systemd user process/CLI. Discovers boots and reads
  sources available to the current user. It reports access failures per source.
- **Sources** — narrow adapters for systemd journal, coredump metadata, kernel logs,
  pstore, and desktop-session logs. Adapters return normalized events.
- **Core** — signatures, deduplication, correlation, and conservative rule-based
  diagnosis. It has no GTK dependency and does not run shell commands.
- **Storage** — versioned SQLite database in
  `$XDG_DATA_HOME/faultline/crashes.db` (default
  `~/.local/share/faultline/crashes.db`). Data is local to the user.
- **Reports** — explicit user-initiated Markdown/JSON export with preview and
  redaction. Nothing is uploaded automatically.

## Data flow

1. Discover boot IDs and timestamps from `journalctl --list-boots`.
2. Read journal records for each boot in JSON form.
3. Normalize records into events with source, timestamp, priority, and signature.
4. Store raw message evidence and source availability in SQLite.
5. Run deterministic rules against events and store findings with their evidence.
6. Present findings as observations or hypotheses, never as unqualified root-cause
   claims.

## Permission model

The default collector runs without root. It must not silently invoke `sudo`, install
a privileged helper, or broaden journal permissions. If a source is inaccessible,
Faultline records that state and continues with other sources. A future optional
privileged collector must be a separately reviewed feature with a narrow interface.

## Shutdown interpretation

A recorded system shutdown/reboot target is positive evidence of a clean ending.
A kernel panic/oops is positive evidence of a likely kernel crash. An abrupt journal
ending by itself is **unknown**: hard freezes, power loss, journal rotation, and
missing permissions can all produce incomplete history. OOM activity is not, by
itself, proof that the machine shut down because of memory exhaustion.

## Current implementation

The initial core provides boot discovery, JSON journal parsing, event signatures,
SQLite schema version 1, conservative kernel/desktop rule matching, and a CLI scan.
The GTK prototype is still a separate sample-data UI until its screens are connected
to the database. Coredump, pstore, resource sampling, notifications, report export,
and packaging are subsequent implementation stages.
