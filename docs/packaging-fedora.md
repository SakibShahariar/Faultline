# Fedora packaging

Faultline is distributed under the MIT License. The RPM installs the Python
command-line tools, native GTK4/libadwaita application, desktop entry,
AppStream metadata, icons, and optional systemd **user** units. It does not
enable background collection automatically.

The Fedora 45 CI job builds the RPM from the checked-out source, installs it,
checks the command-line and GUI entry points, verifies packaged assets, and
removes the package while confirming that user data is preserved. For a new
version tag matching the project metadata, the release workflow attaches the
Fedora 45 RPM and its SHA-256 checksum alongside the AppImage. The published
v0.1.1 release predates this version-aligned RPM path and remains AppImage-only.

## Build locally on Fedora

Install the RPM build tooling and application dependencies:

```sh
sudo dnf install rpm-build rpmdevtools redhat-rpm-config pyproject-rpm-macros \
  python3-devel python3-pip python3-setuptools python3-gobject \
  gtk4 libadwaita systemd-rpm-macros
```

Build the package from the current checkout using the same source archive
layout as CI:

```sh
version="$(python3 -c 'import tomllib; print(tomllib.load(open("pyproject.toml", "rb"))["project"]["version"])')"
mkdir -p "$HOME/rpmbuild/SOURCES"
tar --exclude=.git --transform="s,^\\./,Faultline-$version/," \
  -czf "$HOME/rpmbuild/SOURCES/v$version.tar.gz" .
rpmbuild -ba packaging/rpm/faultline.spec --define "_topdir $HOME/rpmbuild"
```

The resulting noarch RPM is written under
`~/rpmbuild/RPMS/noarch/`. For a published version, build from its matching
`v<version>` tag; the spec's `Source0` points to that tagged source archive.

## Install

Install the RPM with DNF:

```sh
sudo dnf install "$HOME"/rpmbuild/RPMS/noarch/faultline-*.rpm
```

Launch Faultline from the application grid or run `faultline-gui`. The
command-line interface is available as `faultline`.

Background collection remains opt-in. To enable the collector timer for the
current user:

```sh
systemctl --user daemon-reload
systemctl --user enable --now faultline-collector.timer
```

The resource sampler is separately controlled in Preferences and remains
disabled by default. Do not enable its service unless sampling is enabled in
Faultline.

## Remove

```sh
systemctl --user disable --now faultline-collector.timer faultline-sampler.service
sudo dnf remove faultline
```

Removing the RPM does not delete the user's local database or preferences. To
remove personal data, use the application's **Clear History** action and
remove `~/.local/share/faultline` and `~/.config/faultline` separately if
desired.

## Support boundary

The RPM build, installation, GUI smoke test, and uninstall/data-preservation
checks run in Fedora 45 CI. The package uses the distribution's Python, GTK4,
libadwaita, and systemd runtime rather than bundling them. Other Fedora
versions may work when they provide the required dependencies, but are not
separately validated by this workflow.
