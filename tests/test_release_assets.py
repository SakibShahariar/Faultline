import importlib.util
import tempfile
import unittest
from pathlib import Path

SOURCE = (
    Path(__file__).resolve().parents[1]
    / "packaging"
    / "release"
    / "verify_assets.py"
)
spec = importlib.util.spec_from_file_location("faultline_verify_assets", SOURCE)
verify_assets = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verify_assets)


class ReleaseAssetsTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.appimage = self.root / "Faultline-0.1.5-x86_64.AppImage"
        self.rpm = self.root / "faultline-0.1.5-1.fc45.noarch.rpm"
        self.appimage.write_bytes(b"portable image")
        self.rpm.write_bytes(b"fedora package")
        self.manifest = self.root / "SHA256SUMS"
        self.write_manifest()

    def tearDown(self):
        self.directory.cleanup()

    def write_manifest(self, *, include_image=True, include_rpm=True, extra=None):
        lines = []
        if include_image:
            lines.append(f"{verify_assets.sha256(self.appimage)}  {self.appimage.name}")
        if include_rpm:
            lines.append(f"{verify_assets.sha256(self.rpm)}  {self.rpm.name}")
        if extra:
            lines.append(extra)
        self.manifest.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def test_valid_asset_set(self):
        self.assertEqual(
            verify_assets.verify_release_assets(
                self.appimage, self.rpm, self.manifest, "0.1.5"
            ),
            [],
        )

    def test_rejects_missing_checksum(self):
        self.write_manifest(include_rpm=False)
        errors = verify_assets.verify_release_assets(self.appimage, self.rpm, self.manifest)
        self.assertTrue(any("exactly" in error for error in errors))

    def test_rejects_extra_checksum(self):
        self.write_manifest(extra=f"{'0' * 64}  extra.src.rpm")
        errors = verify_assets.verify_release_assets(self.appimage, self.rpm, self.manifest)
        self.assertTrue(any("exactly" in error for error in errors))

    def test_rejects_wrong_checksum(self):
        self.appimage.write_bytes(b"modified image")
        errors = verify_assets.verify_release_assets(self.appimage, self.rpm, self.manifest)
        self.assertTrue(any("checksum mismatch" in error for error in errors))

    def test_rejects_wrong_asset_names(self):
        wrong = self.root / "Faultline-0.1.5-1.fc45.noarch.rpm"
        wrong.write_bytes(b"wrong case")
        errors = verify_assets.verify_release_assets(self.appimage, wrong, self.manifest)
        self.assertTrue(any("invalid Fedora RPM filename" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
