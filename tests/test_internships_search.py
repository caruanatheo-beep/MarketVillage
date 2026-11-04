"""Search checks using synthetic offers, without loading data or sources."""

from datetime import datetime, timezone
import unittest

from internships_project.internships import Opportunity, matching_opportunities, render_opportunities


class OfferSearchTests(unittest.TestCase):
    def setUp(self):
        self.offer = Opportunity(
            title="Stage — Marchés actions", company="Société Générale",
            location="Évry-Courcouronnes", kind="Stage",
            url="https://example.invalid/offer", published="2026-11-04",
            score=10, family="Trading / Structuring",
        )

    def test_search_normalizes_accents_case_spacing_and_separators(self):
        for query in ["societe generale", "SOCIÉTÉ GÉNÉRALE", "  societe   generale  ",
                      "socie\u0301te\u0301 ge\u0301ne\u0301rale", "marches actions",
                      "evry courcouronnes", "ÉVRY-COURCOURONNES"]:
            with self.subTest(query=query):
                self.assertEqual(matching_opportunities([self.offer], query=query), [self.offer])

    def test_empty_query_and_missing_match(self):
        for query in ["", "   ", None]:
            with self.subTest(query=query):
                self.assertEqual(matching_opportunities([self.offer], query=query), [self.offer])
        self.assertEqual(matching_opportunities([self.offer], query="obligations"), [])

    def test_search_combines_all_terms_across_fields_in_any_order(self):
        for query in ["societe evry marches", "marches evry societe",
                      "  ÉVRY,   SOCIÉTÉ — actions  "]:
            with self.subTest(query=query):
                self.assertEqual(matching_opportunities([self.offer], query=query), [self.offer])
        self.assertEqual(matching_opportunities([self.offer], query="societe obligations"), [])
        self.assertEqual(matching_opportunities([self.offer], query="societe paris"), [])

    def test_search_preserves_non_latin_letters_and_digits(self):
        offer = Opportunity("Trading 東京 2027", "Synthetic", "Paris", "Stage",
                            "https://example.invalid/tokyo", "2026-11-04", 10)
        self.assertEqual(matching_opportunities([self.offer, offer], query="東京"), [offer])
        self.assertEqual(matching_opportunities([offer], query="大阪"), [])
        self.assertEqual(matching_opportunities([offer], query="2027"), [offer])

    def test_search_keeps_contract_filters_and_dismissed_status(self):
        self.assertEqual(matching_opportunities([self.offer], query="evry societe", category="VIE"), [])
        self.assertEqual(matching_opportunities(
            [self.offer], query="evry societe", tracking={self.offer.url: {"status": "Écartée"}},
        ), [])

    def test_render_uses_same_search_and_preserves_display_text(self):
        board = render_opportunities(
            [self.offer], [], datetime(2026, 11, 4, tzinfo=timezone.utc),
            query="evry marches generale", delayed_updates=True,
        )
        self.assertIn('data-offer-url="https://example.invalid/offer"', board)
        self.assertIn("Société Générale", board)
        self.assertIn("Offres 1–1 sur 1", board)
