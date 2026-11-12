# AppImage packaging

Faultline's AppImage is an additional x86_64 distribution format. The Fedora RPM
remains the preferred native package on Fedora.

## Build

The AppImage is built from Ubuntu 22.04 packages so its bundled Python 3.10,
PyGObject, GTK 4, and libadwaita runtime has a conservative glibc baseline.
The build uses the pinned appimage-builder 1.1.0 release and the AppImage tool.

Install the host build tools on Ubuntu 22.04:

```sh
sudo apt-get update
sudo apt-get install -y curl libfuse2 squashfs-tools fakeroot
```

Download the build tools:

```sh
curl -fL https://github.com/AppImageCrafters/appimage-builder/releases/download/v1.1.0/appimage-builder-1.1.0-x86_64.AppImage -o appimage-builder
curl -fL https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage -o appimagetool
chmod +x appimage-builder appimagetool
export PATH="$PWD:$PATH"
```

Build from the repository root:

```sh
APP_VERSION=0.1.0 APPIMAGE_EXTRACT_AND_RUN=1 \
  ./appimage-builder --recipe packaging/appimage/AppImageBuilder.yml --skip-test
```

The output is `Faultline-0.1.0-x86_64.AppImage`. The CI workflow builds this
artifact on pushes, pull requests, and version tags; it also produces a SHA-256
checksum and runs the AppImage in a clean Ubuntu container without network
access, host Python, or host GTK packages.

## Run

Make the file executable and launch it:

```sh
chmod +x Faultline-0.1.0-x86_64.AppImage
./Faultline-0.1.0-x86_64.AppImage
```

The graphical application opens by default. The CLI is available through the
same file:

```sh
./Faultline-0.1.0-x86_64.AppImage --cli scan
./Faultline-0.1.0-x86_64.AppImage --cli boots
./Faultline-0.1.0-x86_64.AppImage --cli report --format markdown --output ~/faultline-report.md
```

If FUSE 2 is unavailable on the host, try the AppImage extraction fallback:

```sh
APPIMAGE_EXTRACT_AND_RUN=1 ./Faultline-0.1.0-x86_64.AppImage
```

## Runtime requirements and limitations

- Linux x86_64 with glibc 2.35 or newer. The AppImage is built against Ubuntu
  22.04; distributions using musl (such as Alpine) are not supported.
- A working X11 or Wayland desktop session and compatible host graphics drivers.
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
`./Faultline-0.1.0-x86_64.AppImage --appimage-extract` and copy the desired
units into `~/.config/systemd/user/`.
