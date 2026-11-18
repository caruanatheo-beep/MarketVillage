import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock

import pytest

from internships_project import internships
from internships_project.public_safety import assert_public, public_job_url, validate_snapshot
from scripts import build_internships_pages as builder


@pytest.fixture(autouse=True)
def isolated_discovery_history(tmp_path, monkeypatch):
    monkeypatch.setattr(internships, "CACHE_PATH", tmp_path / "cache.json")
    # Each test chooses its own receiver state, independently of the CI deployment setting.
    monkeypatch.delenv("SOURCE_REQUEST_ENDPOINT", raising=False)


@pytest.fixture
def offer():
    return internships.Opportunity("Stage - Analyste Sales", "Banque publique", "Paris", "Stage",
                                   "https://careers.example.com/offre/123", "2026-11-11", 10,
                                   start_period="avril 2027", family="Sales",
                                   description="PRIVATE DESCRIPTION MUST NOT BE PUBLISHED")


@pytest.fixture
def snapshot(monkeypatch, offer):
    loader = Mock(return_value=([offer], ["PRIVATE RAW ERROR"], datetime(2026, 11, 11, tzinfo=timezone.utc)))
    monkeypatch.setattr(internships, "load_opportunities", loader)
    monkeypatch.setattr(internships, "source_checks", lambda: {"test": {"status": "error", "reason": "PRIVATE"}})
    return loader


def test_export_only_public_fields(tmp_path, snapshot):
    output = tmp_path / "site"
    assert builder.build_site(output) == 1
    snapshot.assert_called_once_with(refresh=False)
    payload = (output / "offers.json").read_text(encoding="utf-8")
    assert "PRIVATE" not in payload
    data = json.loads(payload)
    validate_snapshot(data)
    assert data["offers"][0]["title"] == "Analyste Sales"
    assert data["offers"][0]["categories"] == ["Stages Paris"]
    assert data["offers"][0]["start_month"] == "2027-04"
    assert data["offers"][0]["location"] == "Paris · France"
    assert data["offers"][0]["location_source"] == "Paris"
    assert data["sources"]["unavailable"] == 1
    assert {p.name for p in output.iterdir()} >= {"index.html", "site.css", "app.js", "sources.js", "marketdesk-icon.svg", "frosted-glass.webp", "offers.json", "sources.json", ".nojekyll"}
    assert {p.name for p in output.iterdir()} <= {"index.html", "site.css", "app.js", "sources.js", "marketdesk-icon.svg", "frosted-glass.webp", "offers.json", "sources.json", "logos", ".nojekyll"}
    page = (output / "index.html").read_text(encoding="utf-8")
    assert 'site.css?v=' in page and 'app.js?v=' in page and 'sources.js?v=' in page
    catalog=json.loads((output/'sources.json').read_bytes())
    assert catalog['request_endpoint']==''
    assert 'connect-src \'self\';' in page
    assert len(catalog['sources'])>40
    assert all(set(source)=={'name','category','url','feeds','logo','added_on'} for source in catalog['sources'])


def test_public_source_counts_distinguish_partial_and_cached(tmp_path,snapshot,monkeypatch):
    monkeypatch.setattr(internships,'source_checks',lambda:{
        'partial':{'status':'stale','cache_status':'partial'},
        'delayed_partial':{'status':'stale','cache_status':'backoff','error':'collecte incomplète : 1 requête(s)'},
        'cached':{'status':'stale','cache_status':'stale','count':5},
        'unreachable':{'status':'error','cache_status':'none'}})
    builder.build_site(tmp_path/'site')
    assert json.loads((tmp_path/'site/offers.json').read_bytes())['sources']=={
        'checked':4,'unavailable':1,'partial':2,'retained':1}


@pytest.mark.parametrize('form_id',['person@example.com','https://evil.invalid/suggestions','short'])
def test_build_rejects_recipient_addresses_or_invalid_form_config(tmp_path,snapshot,monkeypatch,form_id):
    monkeypatch.setenv('SOURCE_REQUEST_ENDPOINT',form_id)
    with pytest.raises(ValueError,match='source request endpoint'):
        builder.build_site(tmp_path/'site')
    assert not (tmp_path/'site').exists()


def test_public_form_uses_only_receiver_url_and_explicit_csp_allowlist(tmp_path,snapshot,monkeypatch):
    endpoint='https://marketdesk-source-suggestions.source-suggestions.workers.dev/suggestions'
    monkeypatch.setenv('SOURCE_REQUEST_ENDPOINT',endpoint)
    builder.build_site(tmp_path/'site')
    catalog=json.loads((tmp_path/'site/sources.json').read_bytes())
    assert catalog['request_endpoint']==endpoint
    page=(tmp_path/'site/index.html').read_text(encoding='utf-8')
    assert "connect-src 'self' https://marketdesk-source-suggestions.source-suggestions.workers.dev;" in page
    assert "form-action 'none'" in page


def test_empty_or_contaminated_build_is_refused(tmp_path, monkeypatch):
    output = tmp_path / "site"
    monkeypatch.setattr(internships, "load_opportunities", lambda **kw: ([], [], datetime.now(timezone.utc)))
    with pytest.raises(ValueError, match="No offers"):
        builder.build_site(output)
    assert not output.exists()
    output.mkdir()
    (output / ".env").write_text("PRIVATE")
    with pytest.raises(ValueError, match="empty"):
        builder.build_site(output)


def test_key_in_offer_blocks_export_without_printing_it(tmp_path, snapshot, offer):
    from dataclasses import replace
    key = "sk-" + "proj-" + "a" * 60
    snapshot.return_value = ([replace(offer, title=key)], [], datetime.now(timezone.utc))
    with pytest.raises(ValueError) as error:
        builder.build_site(tmp_path / "site")
    assert key not in str(error.value)
    assert not (tmp_path / "site").exists()


def test_environment_credential_is_detected_even_with_unknown_format(monkeypatch):
    key = "unusual-provider-credential-123456"
    monkeypatch.setenv("CUSTOM_AI_API_KEY", key)
    with pytest.raises(ValueError):
        assert_public(key.encode(), "test")


@pytest.mark.parametrize("url", ["javascript:alert(1)", "http://example.com/job", "https://user:pass@example.com/job",
                                 "https://127.0.0.1/job", "https://example.com/job?api_key=abc", "https://metadata.google.internal/job"])
def test_untrusted_links_are_refused(url):
    with pytest.raises(ValueError):
        public_job_url(url)


def test_unknown_personal_field_is_refused(tmp_path, snapshot):
    builder.build_site(tmp_path / "site")
    data = json.loads((tmp_path / "site/offers.json").read_bytes())
    data["offers"][0]["cv"] = "PRIVATE"
    with pytest.raises(ValueError, match="unexpected offer fields"):
        validate_snapshot(data)


def test_collection_never_sends_email(tmp_path, monkeypatch, offer):
    collect = Mock(return_value=([offer], [], datetime.now(timezone.utc)))
    monkeypatch.setattr(internships, "refresh_opportunities", collect)
    monkeypatch.setattr(internships, "CACHE_PATH", tmp_path / "cache.json")
    builder.build_site(tmp_path / "site", collect=True)
    collect.assert_called_once_with(force=False, notify_email=False, fail_if_busy=True)


def test_manual_collection_bypasses_source_cache(tmp_path, monkeypatch, offer):
    collect = Mock(return_value=([offer], [], datetime.now(timezone.utc)))
    monkeypatch.setattr(internships, "refresh_opportunities", collect)
    monkeypatch.setattr(internships, "CACHE_PATH", tmp_path / "cache.json")
    builder.build_site(tmp_path / "site", collect=True, force=True)
    collect.assert_called_once_with(force=True, notify_email=False, fail_if_busy=True)


def test_manual_refresh_also_rechecks_jobteaser_sitemap(tmp_path, monkeypatch, offer):
    from dataclasses import asdict
    import requests
    cached = tmp_path / "jobteaser.json"
    cached.write_text(json.dumps({"version": 3, "updated": datetime.now(timezone.utc).isoformat(),
                                  "jobs": [asdict(offer)]}), encoding="utf-8")
    monkeypatch.setattr(internships, "JOBTEASER_CACHE_PATH", cached)
    network = Mock(side_effect=requests.RequestException("unavailable"))
    monkeypatch.setattr(internships.requests, "get", network)
    monkeypatch.setattr(internships, "_force_source_refresh", False)
    assert internships._jobteaser_jobs()
    network.assert_not_called()
    monkeypatch.setattr(internships, "_force_source_refresh", True)
    assert internships._jobteaser_jobs()  # Retain the previous offers if the public source fails.
    network.assert_called_once()


def test_frontend_has_no_external_services_or_unsafe_html():
    source = (builder.SITE_ROOT / "app.js").read_text(encoding="utf-8")
    assert "innerHTML" not in source and "eval(" not in source and "document.write" not in source
    assert "textContent" in source
    html = (builder.SITE_ROOT / "index.html").read_text(encoding="utf-8")
    assert "Content-Security-Policy" in html and "default-src 'none'" in html
    assert "unsafe-inline" not in html and "unsafe-eval" not in html
