# AppImage packaging

Faultline's AppImage is an additional x86_64 distribution format. The Fedora RPM
remains the preferred native package on Fedora. The AppImage's bundled GTK
runtime has a known slower startup path; the native RPM uses the host GTK stack.

## Build

The AppImage is built from Ubuntu 24.04 packages so its bundled Python 3.12,
PyGObject, GTK 4, and libadwaita 1.5 runtime supports the APIs used by the native UI.
The build uses the pinned appimage-builder 1.1.0 release and the AppImage tool.

Install the host build tools on Ubuntu 24.04:

```sh
sudo apt-get update
sudo apt-get install -y build-essential curl libfuse2 squashfs-tools fakeroot
```

Download the build tools:

```sh
curl -fL https://github.com/AppImageCrafters/appimage-builder/releases/download/v1.1.0/appimage-builder-1.1.0-x86_64.AppImage -o appimage-builder
curl -fL https://github.com/AppImage/appimagetool/releases/download/1.9.1/appimagetool-x86_64.AppImage -o appimagetool
chmod +x appimage-builder appimagetool
export PATH="$PWD:$PATH"
```

Build from the repository root:

```sh
APP_VERSION=0.1.2 APPIMAGE_EXTRACT_AND_RUN=1 \
  ./appimage-builder --recipe packaging/appimage/AppImageBuilder.yml --skip-test
```

The output is `Faultline-0.1.2-x86_64.AppImage`. The CI workflow builds this
artifact on pushes, pull requests, and version tags; it also produces a SHA-256
checksum and runs the AppImage in a clean Ubuntu container without network
access, host Python, or host GTK packages. The GUI smoke test runs against the bundled runtime under X11 and a headless Wayland compositor, verifies the window and navigation widgets, and exercises the collapsed navigation layout.

## Run

Make the file executable and launch it:

```sh
chmod +x Faultline-0.1.2-x86_64.AppImage
./Faultline-0.1.2-x86_64.AppImage
```

The graphical application opens by default. The CLI is available through the
same file:

```sh
./Faultline-0.1.2-x86_64.AppImage --cli scan
./Faultline-0.1.2-x86_64.AppImage --cli boots
./Faultline-0.1.2-x86_64.AppImage --cli report --format markdown --output ~/faultline-report.md
```

If FUSE 2 is unavailable on the host, try the AppImage extraction fallback:

```sh
APPIMAGE_EXTRACT_AND_RUN=1 ./Faultline-0.1.2-x86_64.AppImage
```

## Runtime requirements and limitations

- Linux x86_64 with glibc 2.39 or newer. The AppImage is built against Ubuntu
  24.04; distributions using musl (such as Alpine) are not supported.
- A working X11 or Wayland desktop session and compatible host graphics drivers.
- The bundled libadwaita 1.5 runtime requires glibc 2.39 or newer.
- Faultline bundles its Python, PyGObject, GTK 4, libadwaita, and related desktop
  runtime libraries. It does not bundle the host's kernel interfaces, graphics
  drivers, systemd tools, or GNOME session.
- System journal and boot inspection depend on host `journalctl` and readable
  journal permissions. Coredump inspection requires host `coredumpctl`.
  Optional systemd user collection requires host `systemctl` and systemd user
  services. GNOME extension inventory requires `gnome-extensions`.
- Normal application startup and local database access do not require network
  access. Diagnostic sources that are unavailable on the host are reported as
  unavailable rather than silently replaced with empty results.

Faultline keeps user data outside the mounted AppImage:
- Database: `$XDG_DATA_HOME/faultline` (normally `~/.local/share/faultline`)
- Preferences: `$XDG_CONFIG_HOME/faultline` (normally `~/.config/faultline`)

Replacing or deleting the AppImage does not remove either directory. The optional
systemd user unit files are included inside the image at
`usr/share/faultline/systemd/user`; they are not installed or enabled
automatically. To inspect or install them manually, extract the image with
`./Faultline-0.1.2-x86_64.AppImage --appimage-extract` and copy the desired
units into `~/.config/systemd/user/`.


## Startup diagnostics and benchmark

Set `FAULTLINE_STARTUP_TRACE=1` to print elapsed startup milestones to standard
error, including bundled Python entry, GTK/libadwaita imports, window construction,
window mapping, and asynchronous database/UI completion.

For repeatable process-startup measurements after building an AppImage:

```sh
for run in first warm-1 warm-2; do
  echo "=== $run ==="
  /usr/bin/time -f "wall-clock: %e seconds" \
    dbus-run-session -- xvfb-run -a \
      env GTK_A11Y=none GDK_BACKEND=x11 FAULTLINE_STARTUP_TRACE=1 \
      ./Faultline-0.1.2-x86_64.AppImage --smoke-test
done
```

The first run is the first process launch in that test session, not a guaranteed
cold disk-cache measurement. Compare the milestone timings as well as wall-clock
time; the benchmark does not clear the operating system's page cache.


## AppImage profiling and dependency inventory

The CI workflow publishes a separate diagnostics artifact alongside the AppImage.
It contains:

- A JSON benchmark comparing the normal AppImage runtime, direct execution from
  a persistent FUSE mount, and direct execution from an extracted AppDir.
- GTK startup traces plus an optional dynamic-loader statistics log and
  `strace` syscall summary.
- A SquashFS superblock report and inventories of shared libraries, GI typelibs,
  GSettings schemas, and desktop assets.

Run the same diagnostics locally after building:

```sh
python3 packaging/appimage/diagnostics.py benchmark \
  --appimage ./Faultline-0.1.2-x86_64.AppImage \
  --output ./appimage-startup.json --runs 3

python3 packaging/appimage/diagnostics.py profile \
  --appimage ./Faultline-0.1.2-x86_64.AppImage \
  --output ./appimage-profile

python3 packaging/appimage/diagnostics.py inventory \
  --appimage ./Faultline-0.1.2-x86_64.AppImage \
  --output ./appimage-inventory
```

The benchmark requires `dbus-run-session` and `xvfb-run`. The profile command
also requires `strace`. If FUSE mounting is unavailable, the benchmark records
that limitation and falls back to the AppImage extraction mode; it does not
pretend that extraction is a mounted-filesystem measurement.

## Compression settings

The build currently uses appimage-builder 1.1.0 and appimagetool 1.9.1. The AppDir recipe avoids bundling the Wayland server library because Faultline is a Wayland client, and it no longer copies a README file that the recipe's own documentation exclusion would remove. The
builder's v1 recipe schema has no compression field and its appimagetool
invocation does not pass a compression override. appimagetool 1.9.1 defaults
to Zstandard and a 128 KB SquashFS block size; its bundled static
`mksquashfs` is built with Zstandard support only. The 128 KB block size is
deliberate: the upstream tool documents that a 1 MB block size caused higher
startup times.

Therefore, Faultline does not claim that an untested gzip/XZ switch improves
startup. Any future compression experiment must use a separately validated
toolchain and pass the clean offline, X11, and Wayland tests before replacing
the default.
