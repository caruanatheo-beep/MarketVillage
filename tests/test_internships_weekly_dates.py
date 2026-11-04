"""Weekly publication filtering with synthetic offers and no source/data reads."""

from dataclasses import replace
from datetime import date, datetime, timezone
import unittest

from internships_project.internships import (
    Opportunity, matching_opportunities, render_opportunities,
)


class WeeklyPublicationTests(unittest.TestCase):
    def setUp(self):
        self.today = date(2026, 11, 4)
        self.offer = Opportunity(
            "Synthetic offer", "Synthetic company", "Paris", "Stage",
            "https://example.invalid/valid", "2026-11-04", 10,
        )

    def test_noncanonical_and_invalid_dates_are_excluded_only_when_filtered(self):
        for published in ["20261104", "2026-W45-3", "2026W453", "2026-11-31",
                          "0000-01-01", "unknown", ""]:
            invalid = replace(self.offer, published=published)
            with self.subTest(published=published):
                self.assertEqual(matching_opportunities([invalid]), [invalid])
                for period in ["weekly", "daily"]:
                    self.assertEqual(matching_opportunities(
                        [invalid], today=self.today, **{period: True},
                    ), [])

    def test_window_includes_today_and_previous_six_days_across_months(self):
        for published, included in [("2026-11-04", True), ("2026-10-29", True),
                                    ("2026-10-28", False), ("2026-11-05", False)]:
            offer = replace(self.offer, published=published)
            with self.subTest(published=published):
                self.assertEqual(matching_opportunities(
                    [offer], weekly=True, today=self.today,
                ), [offer] if included else [])

    def test_board_excludes_noncanonical_dates_before_pagination(self):
        invalid = replace(self.offer, published="20261104", score=20,
                          url="https://example.invalid/invalid")
        board = render_opportunities(
            [invalid, self.offer], [], datetime(2026, 11, 4, tzinfo=timezone.utc),
            weekly=True, today=self.today, delayed_updates=True, page_size=1,
        )
        self.assertIn('data-offer-url="https://example.invalid/valid"', board)
        self.assertNotIn('data-offer-url="https://example.invalid/invalid"', board)


if __name__ == "__main__":
    unittest.main()
