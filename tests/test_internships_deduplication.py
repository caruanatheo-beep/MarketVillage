"""Deduplication checks using synthetic offers, without source or data reads."""

from dataclasses import replace
import unittest

from internships_project.internships import Opportunity, _deduplicate_opportunities


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

    def test_direct_source_in_paris_area_still_replaces_jobteaser(self):
        teaser = replace(self.offer, location="La Défense",
                         source="JobTeaser · sitemap",
                         url="https://example.invalid/teaser")
        self.assertEqual(_deduplicate_opportunities([teaser, self.offer]),
                         [self.offer])
