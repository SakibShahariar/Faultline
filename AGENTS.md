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

## Release versioning and tag selection

Use Semantic Versioning-style tags with a leading `v`: `vMAJOR.MINOR.PATCH` (for example, `v0.2.0`). The tag version must exactly match the application version in `pyproject.toml` and the version used by every release package.

While Faultline is below `1.0.0`:

- **Patch** (`0.1.4` → `0.1.5`): bug fixes, reliability improvements, small polish, and documentation or packaging corrections that do not introduce a substantial new user-facing capability.
- **Minor** (`0.1.4` → `0.2.0`): a meaningful new user-facing feature, a substantial capability change, or a milestone that warrants a new feature release.
- Keep the major version at `0` until Faultline is considered stable enough for its first stable release. Use `1.0.0` for that stability milestone.

After `1.0.0`:

- **Patch**: backward-compatible bug fixes and small corrections.
- **Minor**: backward-compatible new features and improvements.
- **Major**: changes that intentionally break established user-facing behavior, compatibility, or supported interfaces.

Release candidates and other previews must use explicit prerelease suffixes, such as `v0.2.0-rc.1` or `v0.2.0-beta.1`; do not publish a preview under the final stable tag.

Before creating or pushing a release tag:

1. Choose the smallest version increment that accurately represents the changes since the previous release; do not bump versions merely because commits were added.
2. Update the application version and all release metadata/package version references to the same version.
3. Confirm the target commit is on `main`, the working tree is ready for release, and required CI/build/test checks have passed.
4. Create the `vMAJOR.MINOR.PATCH` tag on that exact verified commit. Never tag an unverified commit or move/reuse an existing release tag.
5. Verify the tag points to the intended commit and that the resulting GitHub Release uses the same version and contains the required release assets.

If the appropriate version increment is unclear, inspect the changes since the previous tag and explain the proposed version before tagging. Never guess or create a release tag just to trigger a workflow.
