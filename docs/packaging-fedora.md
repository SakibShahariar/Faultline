# Fedora packaging

Faultline is packaged as a noarch RPM. The RPM installs the Python command-line
tools, native GTK launcher, desktop entry, AppStream metadata, icon, and optional
systemd **user** units. It does not enable background collection automatically.

## Build locally on Fedora

Install the RPM build tooling and GTK runtime dependencies:

```sh
sudo dnf install rpm-build rpmdevtools python3-devel python3-pip \
  python3-setuptools python3-gobject gtk4 libadwaita systemd-rpm-macros
```

Prepare the standard RPM build tree, then build from a tagged source archive:

```sh
rpmdev-setuptree
spectool -g -R packaging/rpm/faultline.spec
rpmbuild -ba packaging/rpm/faultline.spec
```

The spec downloads the GitHub archive for the `v0.1.0` tag. The resulting RPM
is written to `~/rpmbuild/RPMS/noarch/`.

To build the current working tree before creating a release, create a tarball
whose top-level directory is `Faultline-0.1.0/` and copy it to
`~/rpmbuild/SOURCES/Faultline-0.1.0.tar.gz`. Then run
`rpmbuild -ba packaging/rpm/faultline.spec` from the checkout.

## Install and enable optional collection

Install the package:

```sh
sudo dnf install ./faultline-0.1.0-1*.noarch.rpm
```

Launch Faultline from the application grid or run `faultline-gui`. A manual scan
is available with `faultline scan`.

Background collection remains opt-in. To enable the timer for the current user:

```sh
systemctl --user daemon-reload
systemctl --user enable --now faultline-collector.timer
```

The resource sampler is separately controlled in Preferences and remains disabled
by default. Do not enable its service unless sampling is enabled in Faultline.

## Remove

```sh
systemctl --user disable --now faultline-collector.timer faultline-sampler.service
sudo dnf remove faultline
```

Removing the RPM does not delete the user's local database or preferences. To
remove personal data, use the application's **Clear History** action and remove
`~/.local/share/faultline` and `~/.config/faultline` separately if desired.

## Support boundary

The initial package targets Fedora releases that provide Python 3, GTK 4,
libadwaita, and systemd user services. The collector itself is designed around
systemd and Linux diagnostic interfaces; other distributions may package the
same runtime and unit files using their native packaging tools.
