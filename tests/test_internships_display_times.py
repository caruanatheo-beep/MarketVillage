"""Rendering checks with synthetic timestamps and no source or user-data reads."""

from datetime import datetime
import unittest
from unittest.mock import patch

from internships_project import internships


class DisplayTimesTests(unittest.TestCase):
    def test_board_and_source_checks_display_actual_utc(self):
        for timestamp, expected in [
            ("2026-10-28T00:30:00+02:00", "27/10/2026 22:30 UTC"),
            ("2026-10-28T23:30:00-05:00", "29/10/2026 04:30 UTC"),
            ("2026-10-28T12:30:00+00:00", "28/10/2026 12:30 UTC"),
            ("2026-10-28T12:30:00", "28/10/2026 12:30 UTC"),
        ]:
            with self.subTest(timestamp=timestamp), patch.object(internships, "source_checks", return_value={
                "Synthetic source": {"status": "ok", "count": 0, "checked_at": timestamp},
            }):
                board = internships.render_opportunities([], [], datetime.fromisoformat(timestamp))
                self.assertIn(f'Mis à jour {expected}</span>', board)
                self.assertIn(f'<td>{expected}</td>', board)

    def test_invalid_source_timestamp_keeps_board_available(self):
        for timestamp in ["", "not-a-date", "2026-02-30T12:00:00Z"]:
            with self.subTest(timestamp=timestamp), patch.object(internships, "source_checks", return_value={
                "Synthetic source": {"status": "empty", "count": 0, "checked_at": timestamp},
            }):
                board = internships.render_opportunities([], [], datetime(2026, 10, 28))
                self.assertIn('<td>Inconnue</td>', board)
                self.assertIn('Mis à jour 28/10/2026 00:00 UTC</span>', board)
