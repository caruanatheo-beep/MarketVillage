import pytest

from internships_project import internships as jobs
from internships_project.source_catalog import public_source_catalog, validate_source_catalog


def test_catalog_exactly_covers_active_collectors_and_groups_related_portals():
    catalog=public_source_catalog()
    feeds=[feed['name'] for source in catalog for feed in source['feeds']]
    assert set(feeds)=={name for name,_,_ in jobs._opportunity_source_tasks()}
    assert len(feeds)==len(set(feeds))
    assert len(catalog)<len(feeds)
    assert {'Commerzbank','Standard Chartered','Candriam','BNY'} <= {source['name'] for source in catalog}
    assert not any('Palatine' in source['name'] for source in catalog)
    bnp=next(source for source in catalog if source['name']=='BNP Paribas')
    assert len(bnp['feeds'])>=4
    assert next(source for source in catalog if source['name']=='Candriam')['category']=='Gestion d’actifs'


@pytest.mark.parametrize('endpoint',['https://evil.invalid/suggestions','https://user@example.com/suggestions',None,
    'https://marketdesk-source-suggestions.source-suggestions.workers.dev.evil.invalid/suggestions'])
def test_catalog_rejects_unknown_receivers_and_email_addresses(endpoint):
    source={**public_source_catalog()[0],'logo':''}
    with pytest.raises(ValueError):
        validate_source_catalog({'updated':'2026-11-14','sources':[source],'request_endpoint':endpoint})


def test_catalog_accepts_only_deployed_receiver():
    source={**public_source_catalog()[0],'logo':''}
    validate_source_catalog({'updated':'2026-11-14','sources':[source],
        'request_endpoint':'https://marketdesk-source-suggestions.source-suggestions.workers.dev/suggestions'})


def test_catalog_rejects_extra_private_fields_and_unsafe_links():
    source={**public_source_catalog()[0],'logo':''}
    for patch in ({'password':'private'},{'url':'http://localhost/'},{'logo':'logos/../../private.png'}):
        with pytest.raises(ValueError):
            validate_source_catalog({'updated':'2026-11-14','sources':[{**source,**patch}],'request_endpoint':''})


def test_source_addition_dates_are_persistent_and_unknown_baseline_stays_undated():
    first = {s['name']:s['added_on'] for s in public_source_catalog()}
    assert first == {s['name']:s['added_on'] for s in public_source_catalog()}
    assert first['Citi'] == first['Pictet Asset Management'] == first['NatWest Markets'] == '2026-11-14'
    assert first['Candriam'] == first['BNY'] == '2026-11-12'
    assert first['BNP Paribas'] == ''


@pytest.mark.parametrize('added', ['2026-02-30', '14/11/2026', None, 20261114])
def test_catalog_rejects_invalid_addition_date(added):
    source = {**public_source_catalog()[0], 'logo':'', 'added_on':added}
    with pytest.raises(ValueError):
        validate_source_catalog({'updated':'2026-11-14','sources':[source],'request_endpoint':''})
