Name:           faultline
Version:        0.1.2
Release:        1%{?dist}
Summary:        Local-first Linux crash diagnosis and system forensics
License:        MIT
URL:            https://github.com/SakibShahariar/Faultline
Source0:        %{url}/archive/refs/tags/v%{version}.tar.gz

BuildArch:      noarch
BuildRequires:  python3-devel
BuildRequires:  pyproject-rpm-macros
BuildRequires:  python3-setuptools
BuildRequires:  python3-pip
Requires:       python3
Requires:       python3-gobject
Requires:       gtk4
Requires:       libadwaita
Requires:       systemd

%description
Faultline is a native GTK4/libadwaita application for local Linux crash
diagnosis and system forensics. It inspects available boot history, journals,
coredump metadata, kernel and GNOME failures, and stores evidence locally.
The optional collector runs as the logged-in user without a privileged daemon.

%prep
%autosetup -n Faultline-%{version}

%generate_buildrequires
%pyproject_buildrequires

%build
%pyproject_wheel

%install
%pyproject_install
%pyproject_save_files faultline

%check
python3 -m unittest discover -s tests -v
python3 -m compileall -q faultline tests demo/native

%files -f %{pyproject_files}
%license LICENSE
%{_bindir}/faultline
%{_bindir}/faultline-gui
%{_datadir}/faultline/demo/native/main.py
%exclude %{_datadir}/faultline/demo/native/__pycache__/*
%{_datadir}/applications/io.github.sakibshahariar.Faultline.desktop
%{_datadir}/metainfo/io.github.sakibshahariar.Faultline.metainfo.xml
%{_datadir}/icons/hicolor/scalable/apps/io.github.sakibshahariar.Faultline.svg
%{_datadir}/icons/hicolor/scalable/actions/faultline-*-symbolic.svg
%{_userunitdir}/faultline-collector.service
%{_userunitdir}/faultline-collector.timer
%{_userunitdir}/faultline-sampler.service

%changelog
* Thu Nov 12 2026 Sakib Shahariar <74959773+SakibShahariar@users.noreply.github.com> - 0.1.2-1
- Prepare the Fedora 45 package for the v0.1.2 release
- Keep the native GTK application and optional user service assets

* Thu Nov 12 2026 Sakib Shahariar <74959773+SakibShahariar@users.noreply.github.com> - 0.1.1-1
- Align Fedora package metadata with the v0.1.1 release
- Retain the native GTK application and user service assets
