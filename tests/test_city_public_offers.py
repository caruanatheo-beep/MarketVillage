"""City consumes public data safely without starting the employer collectors."""
from datetime import datetime, timedelta, timezone

import pytest
import requests

from internships_project import city_offers as feed, city_services, internships
from internships_project.marketdesk_city import refresh_jobs_workflow


def payload(*urls, age=0):
    return {'updated': (datetime.now(timezone.utc) - timedelta(hours=age)).isoformat(),
            'sources': {'unavailable': 0, 'partial': 0, 'retained': 0},
            'offers': [{'title': 'Rates Sales Internship', 'company': 'Bank', 'location': 'Paris',
                        'kind': 'Stage', 'url': url, 'published': datetime.now(timezone.utc).date().isoformat(),
                        'start_month': '2027-06', 'date_label': 'Publiée le 14 novembre'} for url in urls]}


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(feed, '_cached', None)
    monkeypatch.setattr(feed, '_next_check', 0)
    monkeypatch.setattr(feed, '_pending_urls', set())
    monkeypatch.setattr(feed, 'cache_path', lambda: tmp_path / 'public.json')
    monkeypatch.setattr(internships, 'refresh_opportunities', lambda **_: pytest.fail('Must not collect'))
    return tmp_path


def test_public_catalogue_cached_and_new_detection_survives_panel_reads(isolated, monkeypatch):
    data = payload('https://bank.test/one')
    calls = []
    def download():
        calls.append(True)
        return data
    monkeypatch.setattr(feed, '_download', download)
    assert feed.load_catalogue().source == 'public'
    assert feed.load_catalogue().new_urls == frozenset()
    assert len(calls) == 1
    data = payload('https://bank.test/one', 'https://bank.test/two')
    monkeypatch.setattr(feed, '_next_check', 0)
    assert len(feed.load_catalogue().jobs) == 2
    assert feed.load_catalogue(refresh=True).new_urls == {'https://bank.test/two'}
    assert not feed.load_catalogue(refresh=True).new_urls


@pytest.mark.parametrize('invalid', ['empty', 'url', 'date', 'date_type', 'future', 'fields', 'health'])
def test_invalid_feed_never_replaces_last_good_copy(isolated, monkeypatch, invalid):
    data = payload('https://bank.test/one')
    monkeypatch.setattr(feed, '_download', lambda: data)
    feed.load_catalogue()
    saved = feed.cache_path().read_bytes()
    data = payload('https://bank.test/two')
    if invalid == 'empty': data['offers'] = []
    elif invalid == 'url': data['offers'][0]['url'] = 'javascript:alert(1)'
    elif invalid == 'date': data['updated'] = 'yesterday'
    elif invalid == 'date_type': data['updated'] = 123
    elif invalid == 'future': data['updated'] = (datetime.now(timezone.utc)+timedelta(days=1)).isoformat()
    elif invalid == 'fields': del data['offers'][0]['title']
    elif invalid == 'health': data['sources']['unavailable'] = 'unknown'
    result = feed.load_catalogue(refresh=True)
    assert result.warning
    assert result.jobs[0].url == 'https://bank.test/one'
    assert feed.cache_path().read_bytes() == saved
    assert not result.new_urls


def test_offline_restart_uses_saved_public_snapshot(isolated, monkeypatch):
    feed._save(payload('https://bank.test/saved', age=48))
    monkeypatch.setattr(feed, '_download', lambda: (_ for _ in ()).throw(requests.ConnectionError()))
    monkeypatch.setattr(internships, 'load_opportunities', lambda **_: pytest.fail('Public cache exists'))
    result = feed.load_catalogue()
    assert result.source == 'public'
    assert result.metadata()['catalog_stale']
    assert result.warning


def test_local_fallback_no_collection_and_retry_backoff(isolated, monkeypatch):
    monkeypatch.setattr(feed, '_download', lambda: (_ for _ in ()).throw(requests.Timeout()))
    calls = []
    def local(**kwargs):
        calls.append(kwargs)
        return [], [], datetime.now(timezone.utc)
    monkeypatch.setattr(internships, 'load_opportunities', local)
    assert feed.load_catalogue().source == 'local'
    assert feed.load_catalogue().warning
    assert calls == [{'refresh': False}]


def test_older_snapshot_and_duplicates(isolated, monkeypatch):
    data = payload('https://bank.test/one', 'https://bank.test/one')
    monkeypatch.setattr(feed, '_download', lambda: data)
    assert len(feed.load_catalogue().jobs) == 1
    data = payload('https://bank.test/old', age=1)
    assert feed.load_catalogue(refresh=True).jobs[0].url == 'https://bank.test/one'


def test_hugo_and_panel_use_the_same_public_catalogue(isolated, monkeypatch):
    data = payload('https://bank.test/one')
    monkeypatch.setattr(feed, '_download', lambda: data)
    panel = city_services.internship_highlight()
    assert panel['total_count'] == 1 and panel['catalog_source'] == 'public'
    data = payload('https://bank.test/one', 'https://bank.test/two')
    result = refresh_jobs_workflow(detected_today=True)
    assert result['new_count'] == result['today_count'] == 1
    assert result['offers'][0]['url'] == 'https://bank.test/two'
    assert result['catalog_source'] == 'public'
    assert refresh_jobs_workflow(detected_today=True)['new_count'] == 0


def test_inferred_dates_and_source_errors_are_preserved():
    data = payload('https://bank.test/one')
    data['offers'][0]['date_label'] = 'Détectée le 14 novembre'
    data['sources']['partial'] = 2
    result = feed.parse_catalogue(data)
    assert result.jobs[0].published_inferred
    assert len(result.errors) == 2


def test_download_bounds_size_and_does_not_follow_redirects(monkeypatch):
    class Response:
        status_code = 200
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def raise_for_status(self): pass
        def iter_content(self, _): yield b' ' * 101
    def get(url, **kwargs):
        assert url == feed.PUBLIC_URL
        assert kwargs['allow_redirects'] is False
        assert kwargs['timeout'] == (3, 8)
        return Response()
    monkeypatch.setattr(feed.requests, 'get', get)
    monkeypatch.setattr(feed, 'MAX_BYTES', 100)
    with pytest.raises(ValueError): feed._download()
