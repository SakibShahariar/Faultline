import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from faultline.settings import DEFAULT_SETTINGS, load_settings, save_settings, update_setting


class SettingsTests(unittest.TestCase):
    def test_defaults_are_safe_and_bounded(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            os.environ, {"XDG_CONFIG_HOME": directory}
        ):
            settings = load_settings()
            self.assertTrue(settings["redact_reports"])
            self.assertTrue(settings["collect_coredumps"])
            self.assertFalse(settings["background_sampler"])
            self.assertEqual(settings["max_boots_per_scan"], 10)

    def test_settings_persist_and_validate_numeric_ranges(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            os.environ, {"XDG_CONFIG_HOME": directory}
        ):
            settings = DEFAULT_SETTINGS.copy()
            settings["retention_days"] = 99999
            settings["max_boots_per_scan"] = 0
            save_settings(settings)
            loaded = load_settings()
            self.assertEqual(loaded["retention_days"], 3650)
            self.assertEqual(loaded["max_boots_per_scan"], 1)
            update_setting("redact_reports", False)
            self.assertFalse(load_settings()["redact_reports"])
            path = Path(directory) / "faultline" / "settings.json"
            self.assertTrue(json.loads(path.read_text())["redact_reports"] is False)

    def test_unknown_setting_is_rejected(self):
        with self.assertRaises(KeyError):
            update_setting("arbitrary-command", True)


if __name__ == "__main__":
    unittest.main()
