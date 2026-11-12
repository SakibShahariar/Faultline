import tempfile
import unittest
from pathlib import Path

from faultline.models import Boot
from faultline.storage import Database


class RetentionTests(unittest.TestCase):
    def test_prunes_old_boot_and_keeps_recent_or_unknown(self):
        with tempfile.TemporaryDirectory() as directory:
            db = Database(Path(directory) / "faultline.db")
            db.upsert_boot(Boot("a" * 32, last_seen="Mon 2020-01-01 00:00:00", index=-2))
            db.upsert_boot(Boot("b" * 32, last_seen="Mon 2099-01-01 00:00:00", index=-1))
            db.upsert_boot(Boot("c" * 32, last_seen=None, index=0, current=True))
            self.assertEqual(db.prune_old_boots(90), 1)
            remaining = {row["boot_id"] for row in db.connection.execute("SELECT boot_id FROM boots")}
            self.assertEqual(remaining, {"b" * 32, "c" * 32})
            db.close()


if __name__ == "__main__":
    unittest.main()
