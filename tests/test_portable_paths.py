import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from faultline.settings import load_settings, save_settings, settings_path
from faultline.storage import Database, default_database_path


class PortablePathsTests(unittest.TestCase):
    def test_state_survives_appdir_removal(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            appdir = root / "appdir"
            data_home = root / "state" / "data"
            config_home = root / "state" / "config"
            appdir.mkdir()
            environment = {
                "APPDIR": str(appdir),
                "APPIMAGE": str(appdir / "Faultline.AppImage"),
                "XDG_DATA_HOME": str(data_home),
                "XDG_CONFIG_HOME": str(config_home),
            }
            with patch.dict(os.environ, environment):
                database_path = default_database_path()
                config_path = settings_path()
                self.assertTrue(database_path.is_relative_to(data_home))
                self.assertTrue(config_path.is_relative_to(config_home))
                self.assertFalse(database_path.is_relative_to(appdir))
                self.assertFalse(config_path.is_relative_to(appdir))

                save_settings({"redact_reports": False})
                database = Database()
                database.close()

            # Simulate replacing or removing the portable bundle entirely.
            appdir.rmdir()
            self.assertTrue(database_path.is_file())
            self.assertTrue(config_path.is_file())

            with patch.dict(os.environ, environment):
                self.assertFalse(load_settings()["redact_reports"])
                reopened = Database()
                try:
                    self.assertEqual(reopened.path, database_path)
                finally:
                    reopened.close()


if __name__ == "__main__":
    unittest.main()
