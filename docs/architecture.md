# Faultline architecture

Faultline is a local-first Linux diagnostics application. The GTK4/libadwaita UI is a
client of the Python diagnostic core. The core is independent of GTK and does not
require administrator privileges.

## Components

- **UI** — native GTK4/libadwaita screens. Reads normalized findings from SQLite and
  dispatches scans on a worker thread so journal processing does not block GTK.
- **Collector** — CLI and optional systemd user oneshot service/timer. Scans a
  configurable number of recent boots, bounded to 100 by settings.
- **Sampler** — optional systemd user service. Samples CPU utilization, memory,
  swap, readable thermal zones, and supported GPU busy values at a configurable
  interval. Missing metrics remain NULL, not zero. Samples are pruned by age.
- **Sources** — systemd journal, coredump metadata, pstore, and GNOME extension
  adapters. Every adapter reports missing tools or access failures explicitly.
- **Core** — stable event signatures, deduplication, rule-based classification,
  shutdown assessment, and extension error correlation.
- **Storage** — versioned SQLite database (schema version 2) at
  `$XDG_DATA_HOME/faultline/crashes.db` (default
  `~/.local/share/faultline/crashes.db`). Database directories use mode 0700 and
  the database file mode 0600 where supported.
- **Settings** — per-user JSON configuration at
  `$XDG_CONFIG_HOME/faultline/settings.json` (default
  `~/.config/faultline/settings.json`), written atomically with mode 0600.
- **Reports** — user-initiated Markdown/JSON export. Redaction is enabled by default
  and can be configured in the UI; nothing is uploaded automatically.
- **Notifications** — the scheduled collector dispatches a detached notification
  listener only for newly inserted findings. Notifications can be disabled or
  severity-filtered and open the matching incident through the GUI command-line
  activation path.

## Data flow

1. Discover boot IDs and first/last timestamps through `journalctl --list-boots`.
2. Stream bounded JSON journal records for each selected boot.
3. Parse coredump metadata without extracting core files.
4. Read pstore text records when accessible. Since pstore does not reliably expose a
   systemd boot ID, records are associated with the immediately previous boot as a
   **heuristic**, and the UI/source status explains this limitation.
5. Optionally inspect enabled GNOME extension IDs and correlate only explicit error
   records that include an extension path.
6. Normalize events with source, timestamp, priority, message, and signature.
7. Store evidence and per-source availability in SQLite.
8. Optionally sample resource metrics into a bounded, time-retained SQLite table.
9. Apply conservative deterministic rules and store findings with evidence.
10. Display findings, exact linked evidence, and same-boot resource context in the native UI.

## Permission model

The collector runs as the current user. It does not silently invoke `sudo`, install a
privileged helper, or broaden journal permissions. If a source is inaccessible,
Faultline records that state and continues with other sources. A future privileged
collector would require separate review and a narrow interface.

## Shutdown and diagnosis interpretation

A recorded system shutdown/reboot target is positive evidence of a clean ending.
A kernel panic/oops is positive evidence of a likely kernel failure. An abrupt
journal ending by itself is **unknown**: hard freezes, power loss, journal rotation,
and missing permissions can all produce incomplete history. OOM activity is not,
by itself, proof that the machine shut down because of memory exhaustion.

Extension error correlation is not proof of causation. Pstore-to-boot association is
heuristic. Findings retain confidence and original evidence so users can inspect the
basis of each classification.

## Storage and retention

Events are deduplicated by boot ID, timestamp, source, and normalized signature.
Findings are replaced per boot after a successful journal scan so rescans do not
multiply the same diagnosis. Existing findings are preserved if journal access fails.
The retention policy deletes non-current boot records older than the configured
number of days; records with unparseable timestamps are retained rather than deleted
on a guess. Resource samples have a separate configurable retention window.

## Current limitations

The sampler, actionable next-login notifications, and basic cross-boot recurrence
queries are implemented. Richer incident recurrence analysis and Fedora RPM
packaging remain unimplemented. The application reports these features as unavailable rather than
simulating data.
