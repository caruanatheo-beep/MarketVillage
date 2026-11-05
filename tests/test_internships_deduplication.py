"""Deduplication checks using synthetic offers, without source or data reads."""

from dataclasses import replace
from itertools import permutations
import unittest

from internships_project.internships import (
    Opportunity, _deduplicate_opportunities, matching_opportunities,
)


class DeduplicationTests(unittest.TestCase):
    def setUp(self):
        self.offer = Opportunity(
            "Assistant Trading", "Synthetic Bank", "Paris", "Stage",
            "https://example.invalid/stage", "2026-11-04", 10,
        )

    def test_different_contracts_survive_in_either_source_order(self):
        offers = [replace(self.offer, kind=kind,
                          url=f"https://example.invalid/{index}")
                  for index, kind in enumerate(["Stage", "VIE", "Alternance"])]
        for ordered in [offers, list(reversed(offers))]:
            with self.subTest(order=[job.kind for job in ordered]):
                result = _deduplicate_opportunities(ordered)
                self.assertCountEqual(result, offers)

    def test_distinct_start_cohorts_remain_available_to_date_filters(self):
        april = replace(self.offer, start_period="avril 2027")
        september = replace(self.offer, start_period="September 2027",
                            url="https://example.invalid/september")
        unknown = replace(self.offer, url="https://example.invalid/unknown")
        for ordered in permutations([april, september, unknown]):
            with self.subTest(order=[job.url for job in ordered]):
                result = _deduplicate_opportunities(list(ordered))
                self.assertCountEqual(result, [april, september, unknown])
                self.assertEqual(matching_opportunities(result, earliest="2027-09"),
                                 [september])

    def test_same_start_month_merges_date_formats_and_undated_duplicate(self):
        april = replace(self.offer, start_period="April 2027")
        duplicate = replace(april, start_period="01/04/2027",
                            url="https://example.invalid/april")
        for ordered in permutations([self.offer, april, duplicate]):
            with self.subTest(order=[job.url for job in ordered]):
                result = _deduplicate_opportunities(list(ordered))
                self.assertEqual(len(result), 1)
                self.assertIn(result[0], [april, duplicate])

    def test_jobteaser_different_start_cohort_survives_direct_source_preference(self):
        april = replace(self.offer, start_period="April 2027")
        teaser = replace(self.offer, start_period="September 2027",
                         source="JobTeaser · sitemap",
                         url="https://example.invalid/teaser-september")
        for ordered in [[april, teaser], [teaser, april]]:
            with self.subTest(order=[job.url for job in ordered]):
                self.assertCountEqual(_deduplicate_opportunities(ordered), [april, teaser])

    def test_undated_description_does_not_erase_the_only_known_start(self):
        april = replace(self.offer, start_period="April 2027")
        detailed = replace(self.offer, description="Trading desk internship details",
                           url="https://example.invalid/detailed")
        for ordered in [[april, detailed], [detailed, april]]:
            with self.subTest(order=[job.url for job in ordered]):
                result = _deduplicate_opportunities(ordered)
                self.assertEqual(len(result), 1)
                self.assertEqual(result[0].description, detailed.description)
                self.assertEqual(result[0].start_period, april.start_period)
                self.assertEqual(matching_opportunities(result, earliest="2027-04"), result)

    def test_same_contract_still_merges_normalized_title_and_paris_area(self):
        duplicate = replace(self.offer, title="Stage - Assistant Trading",
                            location="La Défense", url="https://example.invalid/duplicate")
        self.assertEqual(_deduplicate_opportunities([self.offer, duplicate]),
                         [self.offer])

    def test_richer_duplicate_replaces_only_its_own_contract(self):
        vie = replace(self.offer, kind="VIE", url="https://example.invalid/vie")
        detailed = replace(self.offer, description="Trading desk internship details",
                           url="https://example.invalid/detailed")
        self.assertCountEqual(_deduplicate_opportunities([self.offer, vie, detailed]),
                              [vie, detailed])

    def test_direct_source_preference_preserves_another_contract(self):
        teaser = replace(self.offer, source="JobTeaser · sitemap",
                         url="https://example.invalid/teaser")
        vie = replace(teaser, kind="VIE", url="https://example.invalid/vie")
        for ordered in [[teaser, vie, self.offer], [self.offer, vie, teaser]]:
            with self.subTest(order=[job.url for job in ordered]):
                self.assertCountEqual(_deduplicate_opportunities(ordered),
                                      [self.offer, vie])

    def test_direct_source_in_another_city_keeps_jobteaser_offer(self):
        direct = replace(self.offer, location="New York, USA")
        teaser = replace(self.offer, location="London, UK",
                         source="JobTeaser · sitemap",
                         url="https://example.invalid/teaser")
        for ordered in [[teaser, direct], [direct, teaser]]:
            with self.subTest(order=[job.url for job in ordered]):
                self.assertCountEqual(_deduplicate_opportunities(ordered),
                                      [teaser, direct])

    def test_direct_source_same_city_merges_location_typography(self):
        direct = replace(self.offer, location="Zürich, Switzerland")
        teaser = replace(self.offer, location=" ZURICH — Switzerland ",
                         source="JobTeaser · sitemap",
                         url="https://example.invalid/teaser")
        for ordered in [[teaser, direct], [direct, teaser]]:
            with self.subTest(order=[job.url for job in ordered]):
                self.assertEqual(_deduplicate_opportunities(ordered), [direct])

    def test_same_city_typography_merges_direct_postings(self):
        direct = replace(self.offer, location="Zürich, Switzerland",
                         description="Trading desk internship details")
        duplicate = replace(self.offer, location=" ZURICH — Switzerland ",
                            url="https://example.invalid/duplicate")
        for ordered in [[direct, duplicate], [duplicate, direct]]:
            with self.subTest(order=[job.url for job in ordered]):
                self.assertEqual(_deduplicate_opportunities(ordered), [direct])

    def test_normalized_location_preserves_distinct_cities_and_contracts(self):
        zurich = replace(self.offer, location="Zürich, Switzerland")
        geneva = replace(self.offer, location="Geneva, Switzerland",
                         url="https://example.invalid/geneva")
        vie = replace(zurich, location=" ZURICH — Switzerland ", kind="VIE",
                      url="https://example.invalid/vie")
        offers = [zurich, geneva, vie]
        for ordered in [offers, list(reversed(offers))]:
            with self.subTest(order=[job.url for job in ordered]):
                self.assertCountEqual(_deduplicate_opportunities(ordered), offers)

    def test_direct_source_in_paris_area_still_replaces_jobteaser(self):
        teaser = replace(self.offer, location="La Défense",
                         source="JobTeaser · sitemap",
                         url="https://example.invalid/teaser")
        self.assertEqual(_deduplicate_opportunities([teaser, self.offer]),
                         [self.offer])
