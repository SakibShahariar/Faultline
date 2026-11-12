import unittest

from faultline.extensions import correlate_extension_events
from faultline.models import Event


class ExtensionCorrelationTests(unittest.TestCase):
    def event(self, message, source="gnome-shell"):
        return Event("a" * 32, "now", source, message)

    def test_matches_only_enabled_extension_error_paths(self):
        extension = "blur-my-shell@aunetx"
        events = [self.event(
            "JS ERROR: TypeError: bad value at "
            "/home/user/.local/share/gnome-shell/extensions/blur-my-shell@aunetx/extension.js:20"
        )]
        correlated, findings = correlate_extension_events(events, {extension})
        self.assertEqual(correlated[0].event_type, "extension-error")
        self.assertEqual(correlated[0].metadata["extension_id"], extension)
        self.assertEqual(len(findings), 1)
        self.assertIn("does not prove", findings[0].summary)

    def test_does_not_blame_disabled_or_unmatched_extensions(self):
        message = "JS ERROR: TypeError at /extensions/some-extension@sample/extension.js"
        _events, findings = correlate_extension_events(
            [self.event(message)], {"different-extension@sample"}
        )
        self.assertEqual(findings, [])

    def test_ignores_non_error_extension_mentions(self):
        message = "Loaded /extensions/blur-my-shell@aunetx/extension.js"
        _events, findings = correlate_extension_events(
            [self.event(message)], {"blur-my-shell@aunetx"}
        )
        self.assertEqual(findings, [])


if __name__ == "__main__":
    unittest.main()
