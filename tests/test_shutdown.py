import unittest

from faultline.models import Event
from faultline.shutdown import assess_shutdown


class ShutdownAssessmentTests(unittest.TestCase):
    def event(self, message):
        return Event("a" * 32, "now", "kernel", message)

    def test_current_boot_is_current(self):
        self.assertEqual(assess_shutdown([], current=True), "current")

    def test_explicit_shutdown_target_is_clean(self):
        self.assertEqual(
            assess_shutdown([self.event("Reached target System Shutdown")]),
            "clean",
        )

    def test_kernel_panic_is_likely_crash(self):
        self.assertEqual(
            assess_shutdown([self.event("Kernel panic - not syncing")]),
            "likely_crash",
        )

    def test_abrupt_end_alone_is_unknown(self):
        self.assertEqual(
            assess_shutdown([self.event("Some ordinary final log message")]),
            "unknown",
        )


if __name__ == "__main__":
    unittest.main()
