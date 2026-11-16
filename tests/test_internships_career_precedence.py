"""Career-site authority survives later aggregator detection and rotating snapshots."""
from dataclasses import asdict,replace
from datetime import datetime,timedelta,timezone
from itertools import permutations
import json

import pytest
from internships_project import internships as m


@pytest.fixture
def offers(tmp_path,monkeypatch):
    monkeypatch.setattr(m,'CACHE_PATH',tmp_path/'offers.json')
    monkeypatch.setattr(m,'_refresh_career_jobs',{})
    direct=m.Opportunity('Stage - ALM Treasury Officer - H/F','BNP Paribas','Paris, France','Stage',
        'https://group.bnpparibas/emploi-carriere/offre-emploi/stage-alm-treasury-officer-h-f-3',
        '2026-11-13',100,start_period='avril 2027',source='Site carrière · group.bnpparibas')
    teaser=m._jobteaser_from_sitemap_url('https://www.jobteaser.com/fr/job-offers/'
        '4d8d3ed2-6102-495e-b66b-65fde0153e45-bnp-paribas-france-stage-alm-treasury-officer-h-f')
    return direct,replace(teaser,published='2026-11-15',published_inferred=True)


def test_later_jobteaser_never_replaces_official_link_or_its_publication(offers):
    direct,teaser=offers
    for source in ('JobTeaser · sitemap','Employeur'):
        for ordered in permutations([direct,replace(teaser,source=source)]):
            assert m._deduplicate_opportunities(list(ordered))==[direct]


def test_withdrawn_career_offer_suppresses_republication_without_resurrection(offers,monkeypatch):
    direct,teaser=offers
    monkeypatch.setattr(m,'_refresh_career_jobs',{direct.url:direct})
    assert m._deduplicate_opportunities([teaser])==[]
    # Distinct cities, contracts and start cohorts are still independent vacancies.
    for other in [replace(teaser,location='London, UK'),replace(teaser,kind='VIE'),
                  replace(teaser,start_period='septembre 2027')]:
        assert m._deduplicate_opportunities([other])==[other]


def test_career_evidence_survives_snapshot_rotation_without_descriptions(offers):
    direct,teaser=offers
    now=datetime(2026,11,14,tzinfo=timezone.utc)
    m._remember_opportunity_snapshot(now,[replace(direct,description='Not needed for identity')],[])
    for index in range(10):
        m._remember_opportunity_snapshot(now+timedelta(hours=index+1),[],[])
    history=m._read_history_document()
    assert len(history['snapshots'])==8
    assert 'description' not in history['career_offers'][direct.url]
    assert m._without_jobteaser_duplicates([teaser],official_history=m._career_jobs_from_history(history))==[]


def test_old_jobteaser_snapshot_cannot_become_career_evidence(offers):
    _,teaser=offers
    payload={'snapshots':[{'jobs':[asdict(replace(teaser,source='Employeur'))]}]}
    assert m._career_jobs_from_history(payload)=={}


def test_loading_cached_republication_respects_persisted_career_evidence(offers):
    direct,teaser=offers
    now=datetime.now(timezone.utc)
    m._remember_opportunity_snapshot(now,[direct],[])
    m._write_cache(now,[teaser],[])
    assert m._read_cache()[1]==[]


def test_public_seed_restores_authority_even_when_collection_cache_exists(offers,tmp_path,monkeypatch):
    from scripts import build_internships_pages as builder
    direct,teaser=offers
    # Use the real exporter shape; the historical seed is authority, not a live job to restore.
    record={'title':direct.title,'company':direct.company,'location':direct.location,
        'location_source':direct.location,'kind':direct.kind,'url':direct.url,'published':direct.published,
        'date_label':'Publiée le 13 novembre 2026','start':direct.start_period,'start_month':'2027-04',
        'family':'Risk / Support','logo':'','categories':['Stages Paris']}
    payload={'updated':'2026-11-14T23:32:22+00:00','generated':'2026-11-14T23:32:22+00:00',
        'sources':{'checked':1,'unavailable':0,'retained':0},'offers':[record]}
    (tmp_path/'public_seed.json').write_text(json.dumps(payload),encoding='utf-8')
    monkeypatch.setattr(builder,'ROOT',tmp_path)
    m._write_cache(datetime.now(timezone.utc),[teaser],[])
    def collect(**kwargs):
        history=m._career_jobs_from_history(m._read_history_document())
        assert direct.url in history
        assert m._without_jobteaser_duplicates([teaser],official_history=history)==[]
        raise RuntimeError('Verified seed reconciliation before collection')
    monkeypatch.setattr(m,'refresh_opportunities',collect)
    with pytest.raises(RuntimeError,match='Verified seed reconciliation'):
        builder.build_site(tmp_path/'site',collect=True)
