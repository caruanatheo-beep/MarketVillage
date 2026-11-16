"""City reads the public Internships catalogue; collectors remain independent."""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import tempfile
import threading
import time
from urllib.parse import urlsplit

import requests

from . import internships

PUBLIC_URL = 'https://caruanatheo-beep.github.io/Internships-Offres/offers.json'
MAX_BYTES = 6_000_000
_lock = threading.RLock()
_cached = None
_next_check = 0.0
_pending_urls: set[str] = set()


@dataclass(frozen=True)
class Catalogue:
    jobs: list
    errors: list[str]
    updated: datetime
    source: str
    warning: str = ''
    new_urls: frozenset[str] = frozenset()

    def metadata(self) -> dict:
        stale = datetime.now(timezone.utc) - self.updated > timedelta(hours=36)
        warning = self.warning
        if stale:
            warning = (warning + ' Catalogue de plus de 36 heures.').strip()
        return {'catalog_source': self.source, 'catalog_url': PUBLIC_URL,
                'catalog_stale': stale, 'catalog_warning': warning}


def cache_path() -> Path:
    return internships.CACHE_PATH.with_name('city_public_offers.json')


def parse_catalogue(data: dict) -> Catalogue:
    if not isinstance(data, dict) or not isinstance(data.get('offers'), list) or not data['offers']:
        raise ValueError('Empty or invalid public catalogue')
    if not isinstance(data.get('updated'), str):
        raise ValueError('Missing catalogue date')
    updated = datetime.fromisoformat(data['updated'].replace('Z', '+00:00'))
    if updated.tzinfo is None or updated > datetime.now(timezone.utc) + timedelta(minutes=5):
        raise ValueError('Invalid catalogue date')
    jobs, seen = [], set()
    for record in data['offers']:
        if not isinstance(record, dict):
            raise ValueError('Invalid offer')
        if any(not isinstance(record.get(key), str) or not record[key].strip()
               for key in ('title', 'company', 'url', 'kind', 'location')):
            raise ValueError('Missing offer fields')
        url = urlsplit(record['url'])
        if url.scheme not in {'http', 'https'} or not url.hostname or url.username or url.password:
            raise ValueError('Invalid offer URL')
        if record['url'] in seen:
            continue
        seen.add(record['url'])
        for key in ('published', 'start_month', 'start', 'family', 'date_label'):
            if not isinstance(record.get(key, ''), str):
                raise ValueError('Invalid offer metadata')
        jobs.append(internships.Opportunity(
            record['title'], record['company'], record['location'], record['kind'],
            record['url'], record.get('published', ''), 0,
            start_period=record.get('start_month') or record.get('start', ''),
            family=record.get('family', ''), source='Internships en ligne',
            published_inferred=record.get('date_label', '').casefold().startswith('détect')))
    sources = data.get('sources', {})
    if not isinstance(sources, dict):
        raise ValueError('Invalid source health')
    errors = []
    for key in ('unavailable', 'partial', 'retained'):
        count = sources.get(key, 0)
        if not isinstance(count, int) or isinstance(count, bool) or count < 0:
            raise ValueError('Invalid source count')
        errors.extend([f'Source publique : {key}'] * min(count, 1000))
    return Catalogue(jobs, errors, updated, 'public')


def _download() -> dict:
    # A fixed URL, no cookies, no credentials, no redirects to another service.
    with requests.get(PUBLIC_URL, timeout=(3, 8), stream=True, allow_redirects=False) as response:
        response.raise_for_status()
        if response.status_code != 200:
            raise ValueError('Unexpected catalogue response')
        body = bytearray()
        started = time.monotonic()
        for chunk in response.iter_content(65536):
            body.extend(chunk)
            if len(body) > MAX_BYTES or time.monotonic() - started > 12:
                raise ValueError('Catalogue size or time limit exceeded')
        return json.loads(body)


def _save(data: dict) -> None:
    path = cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                         prefix='city-offers-', suffix='.tmp', delete=False) as handle:
            temporary = Path(handle.name)
            json.dump(data, handle, ensure_ascii=False)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def load_catalogue(*, refresh: bool = False) -> Catalogue:
    global _cached, _next_check
    with _lock:
        if not refresh and _cached is not None and time.monotonic() < _next_check:
            return replace(_cached, new_urls=frozenset())
        previous = _cached if _cached is not None and _cached.source == 'public' else None
        if previous is None:
            try:
                path = cache_path()
                if path.stat().st_size <= MAX_BYTES:
                    previous = parse_catalogue(json.loads(path.read_text(encoding='utf-8')))
            except (OSError, ValueError, KeyError, TypeError):
                pass
        try:
            data = _download()
            current = parse_catalogue(data)
            if previous is not None and current.updated < previous.updated:
                raise ValueError('Public catalogue moved backwards')
            if previous is not None:
                current = replace(current, new_urls=frozenset(j.url for j in current.jobs)
                                  - frozenset(j.url for j in previous.jobs))
            try:
                _save(data)
            except OSError:
                current = replace(current, warning='Copie locale du catalogue non enregistrée.')
            _pending_urls.update(current.new_urls)
            _cached, _next_check = current, time.monotonic() + 300
        except (requests.RequestException, ValueError, KeyError, TypeError, OSError):
            warning = 'Site Internships indisponible ou catalogue invalide ; dernière copie conservée.'
            if previous is not None:
                _cached = replace(previous, warning=warning, new_urls=frozenset())
            else:
                jobs, errors, updated = internships.load_opportunities(refresh=False)
                _cached = Catalogue(jobs, errors, updated, 'local',
                                    'Site Internships indisponible ; repli sur le cache local.')
            _next_check = time.monotonic() + 60
        discovered = frozenset(_pending_urls) if refresh and not _cached.warning else frozenset()
        if refresh and not _cached.warning:
            _pending_urls.clear()
        return replace(_cached, new_urls=discovered)
