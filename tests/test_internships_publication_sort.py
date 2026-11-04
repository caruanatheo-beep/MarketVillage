"""Publication sorting checks with synthetic offers and no data/source reads."""

from dataclasses import replace
from datetime import datetime, timezone
import unittest

from internships_project.internships import (
    Opportunity, matching_opportunities, render_opportunities,
)


class PublicationSortTests(unittest.TestCase):
    def setUp(self):
        self.offer = Opportunity(
            "Synthetic offer", "Synthetic company", "Paris", "Stage",
            "https://example.invalid/valid", "2026-11-04", 10,
        )

    def test_impossible_and_unknown_dates_do_not_outrank_valid_dates(self):
        for published in ["2026-99-99", "2026-11-31", "2027-02-29",
                          "0000-01-01", "", "unknown", "20261105"]:
            invalid = replace(self.offer, url="https://example.invalid/invalid",
                              published=published)
            for sort_by in ["recent", "pertinence"]:
                with self.subTest(published=published, sort_by=sort_by):
                    self.assertEqual(matching_opportunities(
                        [invalid, self.offer], sort_by=sort_by,
                    ), [self.offer, invalid])

    def test_valid_dates_sort_newest_first_including_leap_day(self):
        offers = [replace(self.offer, published=published,
                          url=f"https://example.invalid/{published}")
                  for published in ["2028-02-28", "2027-12-31", "2028-03-01", "2028-02-29"]]
        for sort_by in ["recent", "pertinence"]:
            with self.subTest(sort_by=sort_by):
                self.assertEqual(
                    [job.published for job in matching_opportunities(offers, sort_by=sort_by)],
                    ["2028-03-01", "2028-02-29", "2028-02-28", "2027-12-31"],
                )

    def test_relevance_retains_score_and_target_start_priorities(self):
        scored = replace(self.offer, score=20, published="",
                         url="https://example.invalid/scored")
        targeted = replace(self.offer, score=1, published="unknown",
                           start_period="avril 2027", url="https://example.invalid/targeted")
        self.assertEqual(matching_opportunities([self.offer, scored, targeted]),
                         [targeted, scored, self.offer])
        self.assertEqual(matching_opportunities([self.offer, scored, targeted], sort_by="recent"),
                         [self.offer, scored, targeted])

    def test_board_paginates_after_validating_publication_order(self):
        invalid = replace(self.offer, url="https://example.invalid/invalid",
                          published="2026-99-99")
        board = render_opportunities(
            [invalid, self.offer], [], datetime(2026, 11, 4, tzinfo=timezone.utc),
            sort_by="recent", page_size=1, delayed_updates=True,
        )
        self.assertIn('data-offer-url="https://example.invalid/valid"', board)
        self.assertNotIn('data-offer-url="https://example.invalid/invalid"', board)
