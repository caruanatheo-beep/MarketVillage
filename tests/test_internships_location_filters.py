"""Geographic filter checks with synthetic offers and no private data reads."""

from dataclasses import replace
from datetime import datetime, timezone
import unittest

from internships_project.internships import (
    Opportunity, matching_opportunities, render_opportunities,
)


class LocationFilterTests(unittest.TestCase):
    def setUp(self):
        self.offer = Opportunity(
            "Synthetic trading internship", "Synthetic company", "Paris", "Stage",
            "https://example.invalid/offer", "2026-11-04", 10,
        )

    def test_paris_filter_accepts_location_typography_variants(self):
        for location in [
            "Île de France", "ILE-DE-FRANCE", "I\u0302le-de-France",
            "Fontenay sous Bois", "Fontenay-sous-Bois",
            "La De\u0301fense", "LA   DÉFENSE",
            "Saint–Denis", "Saint Denis", "Issy les Moulineaux",
        ]:
            with self.subTest(location=location):
                offer = replace(self.offer, location=location)
                self.assertEqual(matching_opportunities(
                    [offer], category="Stages Paris",
                ), [offer])
                self.assertEqual(matching_opportunities(
                    [offer], category="Stages International",
                ), [])

    def test_non_paris_locations_and_other_contracts_remain_excluded(self):
        for location in ["London, UK", "Lyon, France", "", "Unknown"]:
            with self.subTest(location=location):
                self.assertEqual(matching_opportunities(
                    [replace(self.offer, location=location)], category="Stages Paris",
                ), [])
        for kind in ["VIE", "Graduate"]:
            with self.subTest(kind=kind):
                self.assertEqual(matching_opportunities(
                    [replace(self.offer, location="Île de France", kind=kind)],
                    category="Stages Paris",
                ), [])

    def test_board_displays_matching_card_and_keeps_original_location(self):
        offer = replace(self.offer, location="Fontenay sous Bois")
        board = render_opportunities(
            [offer], [], datetime(2026, 11, 4, tzinfo=timezone.utc),
            category="Stages Paris", delayed_updates=True,
        )
        self.assertIn('data-offer-url="https://example.invalid/offer"', board)
        self.assertIn("Fontenay sous Bois", board)
        self.assertIn("Offres 1–1 sur 1", board)
