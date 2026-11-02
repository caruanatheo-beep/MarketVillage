import subprocess

import requests

from src.calendar import BLS_ICS, _download_bls_calendar, _parse_dt, filter_events
from src.news import _NEWS_CACHE, load_news
from src.ui import _calendar_html, _markets_html, _news_cards_html
from tests.sample_data import SAMPLE_EVENTS
from tests.sample_data import SAMPLE_NEWS, sample_points


def test_calendar_filters_live_shaped_events():
    assert filter_events(SAMPLE_EVENTS, region="United Kingdom")
    assert filter_events(SAMPLE_EVENTS, date_from="2026-09-23")


def test_windows_calendar_uses_minimal_native_curl(monkeypatch):
    executable = r"C:\Windows\System32\curl.exe"
    captured = {}
    monkeypatch.setattr("src.calendar.os.name", "nt")
    monkeypatch.setattr("src.calendar.shutil.which", lambda name: executable)

    def run(command, **kwargs):
        captured["command"] = command
        return subprocess.CompletedProcess(command, 0, stdout=b"BEGIN:VCALENDAR\r\nEND:VCALENDAR", stderr=b"")

    monkeypatch.setattr("src.calendar.subprocess.run", run)
    assert _download_bls_calendar(20).startswith("BEGIN:VCALENDAR")
    assert captured["command"] == [
        executable, "--fail", "--silent", "--show-error", "--location",
        "--user-agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
        "--connect-timeout", "5", "--max-time", "20", BLS_ICS,
    ]


def test_calendar_converts_eastern_release_time_to_utc():
    parsed = _parse_dt("20261002T083000", "America/New_York")
    assert parsed is not None
    assert parsed.strftime("%Y-%m-%d %H:%M %Z") == "2026-10-02 12:30 UTC"


def test_news_failure_falls_back_without_crashing(monkeypatch):
    _NEWS_CACHE.clear()

    def fail(*args, **kwargs):
        raise requests.Timeout("synthetic")

    monkeypatch.setattr("src.news.requests.get", fail)
    news, errors = load_news()
    assert news == []
    assert errors


def test_news_cards_are_clickable():
    all_cards = _news_cards_html(SAMPLE_NEWS, [])
    assert all_cards.count('class="news-card"') == len(SAMPLE_NEWS)
    assert 'target="_blank"' in all_cards
    assert "Federal Reserve policy update" in all_cards


def test_market_board_groups_points_without_a_dataframe():
    board = _markets_html(sample_points())
    assert 'class="market-pulse"' in board
    assert "Policy &amp; Credit" in board
    assert "US Treasury 10Y" in board
    assert "OFFICIAL CLOSE" in board
    assert 'target="_blank"' in board


def test_calendar_uses_clickable_timeline_and_hides_missing_metrics():
    calendar = _calendar_html(SAMPLE_EVENTS)
    assert 'class="calendar-next"' in calendar
    assert 'class="calendar-timeline"' in calendar
    assert "US CPI" in calendar
    assert "unavailable" not in calendar.lower()
    assert 'target="_blank"' in calendar
