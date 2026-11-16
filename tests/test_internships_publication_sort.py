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

    def test_better_targeted_role_can_outweigh_an_earlier_start(self):
        april = replace(self.offer, score=100, start_period="avril 2027",
                        url="https://example.invalid/april")
        june_sales = replace(self.offer, score=115, start_period="juin 2027",
                             url="https://example.invalid/june-sales")
        self.assertEqual(matching_opportunities([april, june_sales]), [june_sales, april])

    def test_target_window_and_month_contribute_to_combined_score(self):
        april = replace(self.offer, score=100, start_period="avril 2027", published="2026-10-01")
        september = replace(april, start_period="septembre 2027", published="2026-11-10",
                            url="https://example.invalid/september")
        outside = replace(april, start_period="mars 2027", published="2026-11-11",
                          url="https://example.invalid/outside")
        self.assertEqual(matching_opportunities([outside, september, april]), [april, september, outside])

    def test_publication_only_breaks_equal_combined_scores(self):
        older = replace(self.offer, score=100, start_period="avril 2027", published="2026-10-01")
        newer = replace(older, published="2026-11-10", url="https://example.invalid/newer")
        stronger = replace(older, score=115, url="https://example.invalid/stronger")
        self.assertEqual(matching_opportunities([older, newer, stronger]), [stronger, newer, older])
