"""Tracking backup imports using synthetic in-memory data only."""

import json
import unittest
from copy import deepcopy

from internships_project.internships import export_tracking, import_tracking


class TrackingImportReliabilityTests(unittest.TestCase):
    malformed_urls = (
        "https://[broken/offer",
        "https://[not-an-ip]/offer",
        "https://example.invalid\uff0foffer",
    )

    def test_malformed_url_does_not_discard_valid_entries_or_mutate_state(self):
        existing_url = "https://example.invalid/existing"
        valid_url = "https://example.invalid/new"
        state = {existing_url: {"title": "Existing", "note": "Keep this note"}}
        original = deepcopy(state)
        for malformed_url in self.malformed_urls:
            for malformed_first in (True, False):
                with self.subTest(url=malformed_url, malformed_first=malformed_first):
                    entries = [(malformed_url, {"title": "Broken"}),
                               (valid_url, {"title": "New", "note": "Imported note"})]
                    if not malformed_first:
                        entries.reverse()
                    restored, message = import_tracking(json.dumps(dict(entries)), state)
                    self.assertEqual(set(restored), {existing_url, valid_url})
                    self.assertEqual(restored[valid_url]["note"], "Imported note")
                    self.assertEqual(restored[existing_url], original[existing_url])
                    self.assertIn("1 offre(s)", message)
                    self.assertEqual(state, original)

    def test_backup_with_only_malformed_urls_keeps_existing_entries(self):
        state = {"https://example.invalid/existing": {"note": "Keep this note"}}
        restored, message = import_tracking(
            json.dumps({url: {"title": "Broken"} for url in self.malformed_urls}), state,
        )
        self.assertEqual(restored, state)
        self.assertIn("0 offre(s)", message)

    def test_valid_https_backup_round_trip_and_other_schemes(self):
        url = "https://[2001:db8::1]/offer"
        restored, message = import_tracking(export_tracking({
            url: {"title": "Synthetic", "note": "Keep", "status": "Interview"},
            "http://example.invalid/offer": {"title": "HTTP"},
            "javascript:alert(1)": {"title": "Script"},
            "https:///missing-host": {"title": "No host"},
        }), {})
        self.assertEqual(set(restored), {url})
        self.assertEqual(restored[url]["status"], "Interview")
        self.assertEqual(restored[url]["note"], "Keep")
        self.assertIn("1 offre(s)", message)


if __name__ == "__main__":
    unittest.main()
