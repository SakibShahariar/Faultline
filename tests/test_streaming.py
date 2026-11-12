import json
import os
import threading
import unittest
from unittest.mock import patch

from faultline.sources import iter_boot_events


class FakeProcess:
    def __init__(self, payload):
        read_fd, write_fd = os.pipe()
        self.stdout = os.fdopen(read_fd, "rb", buffering=0)
        self.returncode = None

        def write_payload():
            with os.fdopen(write_fd, "wb", buffering=0) as stream:
                stream.write(payload)
            self.returncode = 0

        self.writer = threading.Thread(target=write_payload, daemon=True)
        self.writer.start()

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        self.writer.join(timeout=timeout)
        if self.writer.is_alive():
            raise TimeoutError("fake process did not finish")
        return self.returncode

    def kill(self):
        self.returncode = -9


class JournalStreamingTests(unittest.TestCase):
    def test_streams_multiple_json_records_from_pipe(self):
        boot_id = "a" * 32
        payload = (
            json.dumps({"MESSAGE": "first", "__REALTIME_TIMESTAMP": "1000000"}) + "\n"
            + json.dumps({"MESSAGE": "second", "__REALTIME_TIMESTAMP": "2000000"}) + "\n"
        ).encode()
        fake = FakeProcess(payload)
        with (
            patch("faultline.sources.shutil.which", return_value="/usr/bin/journalctl"),
            patch("faultline.sources.subprocess.Popen", return_value=fake),
        ):
            events = list(iter_boot_events(boot_id))
        self.assertEqual([event.message for event in events], ["first", "second"])
        self.assertTrue(all(event.boot_id == boot_id for event in events))


if __name__ == "__main__":
    unittest.main()
