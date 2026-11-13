# Agent Instructions

## Release assets

Keep GitHub Releases simple and user-facing. For each Faultline release, publish exactly these three assets:

1. `Faultline-<version>-x86_64.AppImage` — portable Linux build.
2. `faultline-<version>-<release>.fc<fedora-version>.noarch.rpm` — Fedora package.
3. `SHA256SUMS` — one combined checksum manifest covering the AppImage and Fedora RPM.

Do not attach these as separate GitHub Release assets:
- RPM source packages (`.src.rpm`).
- Individual checksum files for each package.
- Build logs, intermediate archives, test reports, or other CI artifacts.

Source RPMs and other intermediate outputs may remain available as CI workflow artifacts when useful for maintainers, but they should not clutter the public release page.

Generate `SHA256SUMS` once, after both final distributable packages are available. It must contain checksums for the exact AppImage and RPM filenames attached to that release.

Avoid having separate packaging workflows race to upload or overwrite the same release assets. Use a single coordinated release-asset publishing step/workflow so the three public assets are attached once. If an asset with the intended name already exists, handle that deliberately and idempotently rather than failing the release with a duplicate-upload error.

Before declaring a release complete, verify that the GitHub Release contains exactly the two installers and the single combined `SHA256SUMS` file, and that the manifest checksums match the uploaded files.

## Commit messages

Use Conventional Commits for all new commits:

```text
type(scope): imperative description (#issue)
```

- Use a specific type: `feat`, `fix`, `refactor`, `perf`, `test`, `docs`, `build`, `ci`, or `chore`.
- Use a concise scope naming the affected component or area, such as `scanner`, `extensions`, `ui`, `packaging`, or `release`.
- Write a clear, specific description in the imperative mood. Explain what the commit changes; avoid vague messages.
- Include the related issue number in parentheses at the end whenever the commit addresses an existing issue, for example: `fix(extensions): clarify related incident titles (#31)`.
- Do not invent issue numbers. Omit the issue reference for standalone work that does not address an existing issue.
- Keep the subject concise and consistent. Do not use square-bracket issue prefixes such as `[#31]`.
- Do not rewrite published commit history solely to change message formatting; apply this convention to all new commits.
