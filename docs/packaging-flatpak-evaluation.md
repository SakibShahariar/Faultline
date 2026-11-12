# Flatpak packaging evaluation

## Decision: do not ship a Flatpak yet

Faultline is a host-diagnostics application, not a self-contained desktop utility.
Its main data sources are host services and host-owned diagnostic files:

- `journalctl --list-boots` and per-boot journal records.
- `coredumpctl` metadata.
- Retained records under `/sys/fs/pstore` and `/var/lib/systemd/pstore`.
- The host `gnome-extensions` command and the user's enabled extension inventory.
- Optional user systemd units and services.

A normal Flatpak sandbox does not automatically expose these commands, host paths,
or system journal data. Granting broad host filesystem access would weaken the
sandbox without creating a well-defined support boundary. Calling host tools via
`flatpak-spawn --host` would require an explicit host-command integration design,
narrow command allow-list, argument validation, and a clear security review.
There is no general desktop portal that provides the complete journal, coredump,
pstore, and GNOME extension data Faultline currently reads.

A Flatpak could be built that launches the UI but reports many of Faultline's
important sources as unavailable. That would not be feature parity, and a
manifest with broad host permissions would be misleading.

## Reconsider when

- A small host-side helper with a documented, narrow IPC interface exists.
- The helper can enforce read-only access and expose only the data required by
  Faultline.
- The project has a permission and threat model for journal, coredump, pstore,
  and extension data.
- A prototype can demonstrate useful diagnostics without `--filesystem=host`
  or unrestricted host command execution.

Until then, keep the Fedora RPM as the native package and the AppImage as the
portable option. The Flatpak issue is closed as not planned, not as a completed
package implementation.
