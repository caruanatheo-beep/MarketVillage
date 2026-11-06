"""Deduplication checks using synthetic offers, without source or data reads."""

from dataclasses import replace
from datetime import date, datetime, timezone
from itertools import permutations
import unittest
from unittest.mock import Mock, patch

from internships_project import internships
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

    def test_richer_duplicate_keeps_confirmed_publication_and_daily_visibility(self):
        for published, inferred in [("", False), ("2026-11-05", True),
                                    ("2026-11-31", False)]:
            detailed = replace(self.offer, published=published,
                               published_inferred=inferred,
                               description="Trading desk internship details",
                               url="https://example.invalid/detailed")
            for ordered in permutations([self.offer, detailed]):
                with self.subTest(published=published, order=[job.url for job in ordered]):
                    result = _deduplicate_opportunities(list(ordered))
                    self.assertEqual(len(result), 1)
                    self.assertEqual(result[0].url, detailed.url)
                    self.assertEqual(result[0].published, self.offer.published)
                    self.assertFalse(result[0].published_inferred)
                    self.assertEqual(matching_opportunities(
                        result, daily=True, today=date(2026, 11, 4)), result)

    def test_confirmed_date_from_another_direct_source_is_preserved(self):
        undated = replace(self.offer, published="", source="Career site")
        confirmed = replace(self.offer, source="Public feed",
                            url="https://example.invalid/feed")
        for ordered in permutations([undated, confirmed]):
            result = _deduplicate_opportunities(list(ordered))
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0].published, confirmed.published)
            self.assertFalse(result[0].published_inferred)

    def test_duplicates_keep_earliest_detection_without_claiming_publication(self):
        older = replace(self.offer, published="2026-10-20", published_inferred=True)
        detailed = replace(self.offer, published_inferred=True,
                           description="Trading desk internship details",
                           url="https://example.invalid/detailed")
        for ordered in permutations([older, detailed]):
            result = _deduplicate_opportunities(list(ordered))
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0].published, older.published)
            self.assertTrue(result[0].published_inferred)

    def test_publication_dates_do_not_leak_between_start_cohorts(self):
        april = replace(self.offer, start_period="April 2027")
        september = replace(self.offer, published="", start_period="September 2027",
                            url="https://example.invalid/september")
        for ordered in permutations([april, september]):
            result = _deduplicate_opportunities(list(ordered))
            self.assertEqual(next(job for job in result if job.url == september.url).published, "")

    def test_progressive_refresh_publishes_confirmed_date_after_duplicate_replacement(self):
        detailed = replace(self.offer, published="", description="Trading desk details",
                           url="https://example.invalid/detailed")
        now = datetime(2026, 11, 5, tzinfo=timezone.utc)
        writer = Mock()
        with patch.multiple(internships, _cache=None, _last_attempt=now,
                            _refresh_previous_jobs={self.offer.url: self.offer},
                            _refresh_first_seen={}, _write_cache=writer):
            internships._publish_refresh_progress([detailed], [])
            jobs = internships._cache[1]
            self.assertEqual(len(jobs), 1)
            self.assertEqual(jobs[0].url, detailed.url)
            self.assertEqual(jobs[0].published, self.offer.published)
            self.assertFalse(jobs[0].published_inferred)
            writer.assert_called_once_with(now, jobs, [])

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

    def test_direct_sources_keep_known_start_in_either_order(self):
        career = replace(self.offer, source="Career site",
                         description="Trading desk details")
        feed = replace(self.offer, source="Public feed", start_period="April 2027",
                       url="https://example.invalid/feed")
        for ordered in permutations([career, feed]):
            with self.subTest(order=[job.source for job in ordered]):
                result = _deduplicate_opportunities(list(ordered))
                self.assertEqual(len(result), 1)
                self.assertEqual(result[0].url, ordered[0].url)
                self.assertEqual(result[0].source, ordered[0].source)
                self.assertEqual(result[0].start_period, feed.start_period)
                self.assertEqual(matching_opportunities(result, earliest="2027-04"), result)
                self.assertEqual(matching_opportunities(result, earliest="2027-05"), [])

    def test_direct_sources_do_not_assign_an_ambiguous_start(self):
        unknown = replace(self.offer, source="Career site")
        april = replace(self.offer, source="Public feed", start_period="April 2027",
                        url="https://example.invalid/april")
        september = replace(april, start_period="September 2027",
                            url="https://example.invalid/september")
        for ordered in permutations([unknown, april, september]):
            result = _deduplicate_opportunities(list(ordered))
            self.assertCountEqual(result, [unknown, april, september])
            self.assertEqual(matching_opportunities(result, earliest="2027-09"), [september])

    def test_progressive_refresh_keeps_start_from_another_direct_source(self):
        career = replace(self.offer, source="Career site")
        feed = replace(self.offer, source="Public feed", start_period="April 2027",
                       url="https://example.invalid/feed")
        now = datetime(2026, 11, 5, tzinfo=timezone.utc)
        writer = Mock()
        with patch.multiple(internships, _cache=None, _last_attempt=now,
                            _refresh_previous_jobs={career.url: career},
                            _refresh_first_seen={}, _write_cache=writer):
            internships._publish_refresh_progress([feed], [])
            jobs = internships._cache[1]
            self.assertEqual(jobs, [replace(career, start_period=feed.start_period)])
            self.assertEqual(matching_opportunities(jobs, earliest="2027-04"), jobs)
            writer.assert_called_once_with(now, jobs, [])

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

    def test_rejected_employer_location_does_not_suppress_jobteaser_fallback(self):
        for location in ["", "Description du poste", "x" * 121]:
            direct = replace(self.offer, location=location)
            # A sitemap does not always identify the city. It remains usable
            # without one, unlike an incomplete employer detail extraction.
            teaser = replace(self.offer, location="", source="JobTeaser · sitemap",
                             url="https://example.invalid/teaser")
            for ordered in permutations([direct, teaser]):
                with self.subTest(location=location, order=[job.url for job in ordered]):
                    self.assertEqual(_deduplicate_opportunities(list(ordered)), [teaser])

    def test_progressive_refresh_keeps_fallback_until_usable_employer_result(self):
        teaser = replace(self.offer, location="", source="JobTeaser · sitemap",
                         url="https://example.invalid/teaser")
        incomplete = replace(self.offer, location="")
        now = datetime(2026, 11, 5, tzinfo=timezone.utc)
        writer = Mock()
        with patch.multiple(internships, _cache=None, _last_attempt=now,
                            _refresh_previous_jobs={teaser.url: teaser},
                            _refresh_first_seen={}, _write_cache=writer):
            internships._publish_refresh_progress([incomplete], [])
            self.assertEqual(internships._cache[1], [teaser])
            writer.assert_called_once_with(now, [teaser], [])

            internships._publish_refresh_progress([self.offer], [])
            self.assertEqual(internships._cache[1], [self.offer])
            self.assertEqual(writer.call_count, 2)
            writer.assert_called_with(now, [self.offer], [])
