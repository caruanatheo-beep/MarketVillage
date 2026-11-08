from dataclasses import replace

import pytest

from src.analytics import curve_spreads, format_change, narratives, points_frame, talking_points
from src.data import SERIES
from tests.sample_data import sample_points


@pytest.mark.parametrize("category,unit,previous,change,expected", [
    ("Risk", "index", 0.1, 1e308, "N/A"),
    ("FX", "USD", 1e-308, -1e308, "N/A"),
    ("Credit", "%", 1, 1e308, "N/A"),
    ("Rates", "%", 1, -1e308, "N/A"),
    ("Risk", "index", float("inf"), 2, "N/A"),
    ("Risk", "index", float("nan"), 2, "N/A"),
    ("Other", "index", 1, float("inf"), "N/A"),
    ("Other", "index", 1, float("nan"), "N/A"),
    ("Risk", "index", 100, 2, "+2.00%"),
    ("Credit", "%", 3, -0.05, "-5.0 bp"),
    ("Other", "index", 100, 2, "+2.00"),
    ("Risk", "index", None, 2, "+2.00"),
    ("Risk", "index", 0, 2, "+2.00"),
    ("Risk", "index", 100, None, "N/A"),
])
def test_change_display_requires_a_finite_calculated_variation(category, unit, previous, change, expected):
    point = replace(sample_points()[0], category=category, unit=unit,
                    previous=previous, change=change)
    assert format_change(point) == expected


def test_curve_spreads_are_calculated_in_basis_points():
    spreads = curve_spreads(sample_points())
    assert spreads["US 2s10s"] == -47.0
    assert spreads["US 5s30s"] == 12.0


def test_transformations_keep_dates_and_statuses():
    frame = points_frame(sample_points())
    assert len(frame) == len(SERIES)
    assert {"Indicator", "Latest", "Change", "Observation", "Status"}.issubset(frame.columns)
    assert (frame["Status"] == "latest available").all()


def test_narratives_and_talking_points_are_labelled():
    assert narratives(sample_points())
    drafts = talking_points(sample_points())
    assert len(drafts) == 3
    assert all("human approval required" in item for item in drafts)
