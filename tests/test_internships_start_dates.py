"""Start-date filtering checks using synthetic offers only."""

from dataclasses import replace
from datetime import datetime, timezone
import unittest

from internships_project.internships import (
    Opportunity, matching_opportunities, render_opportunities, start_month,
)


class StartDateTests(unittest.TestCase):
    def test_valid_start_formats(self):
        for period, expected in [
            ("4/1/2027", "2027-01"), ("04.01.2027", "2027-01"),
            ("2027-01-04", "2027-01"), ("2027-01", "2027-01"),
            ("29/02/2028", "2028-02"), ("2028-02-29", "2028-02"),
            ("janvier 2027", "2027-01"), ("January 2027", "2027-01"),
            ("Starts in September 2027", "2027-09"),
        ]:
            with self.subTest(period=period):
                self.assertEqual(start_month(period), expected)

    def test_impossible_dates_are_unknown(self):
        for period in ["31/02/2027", "29/02/2027", "00/04/2027",
                       "01/00/2027", "01/13/2027", "01/04/0000",
                       "2027-02-29", "2027-04-31", "2027-04-00",
                       "2027-00", "2027-13", "", "unknown"]:
            with self.subTest(period=period):
                self.assertEqual(start_month(period), "")

    def test_filter_and_board_exclude_invalid_start_without_hiding_unfiltered_offer(self):
        valid = Opportunity("Valid start", "Synthetic", "Paris", "Stage",
                            "https://example.invalid/valid", "2026-11-04", 10,
                            start_period="2027-04-01")
        invalid = replace(valid, title="Invalid start", url="https://example.invalid/invalid",
                          start_period="31/04/2027", score=20)
        jobs = [invalid, valid]
        self.assertEqual(matching_opportunities(jobs, earliest="2027-04"), [valid])
        # An impossible date must not confer the April–September start priority.
        self.assertEqual(matching_opportunities(jobs), [valid, invalid])
        board = render_opportunities(
            jobs, [], datetime(2026, 11, 4, tzinfo=timezone.utc),
            earliest="2027-04", delayed_updates=True,
        )
        self.assertIn('data-offer-url="https://example.invalid/valid"', board)
        self.assertNotIn('data-offer-url="https://example.invalid/invalid"', board)
