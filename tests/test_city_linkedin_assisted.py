import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from internships_project import network_discovery as network, state_store
from internships_project.marketdesk_city import CityError, CityStore, CityWorker
from internships_project.city_routes import add_city_routes


@pytest.fixture
def contact():
    return {'name':'Alex Martin','role':'Rates Sales','company':'Bank A','location':'Paris',
            'linkedin_url':'https://fr.linkedin.com/in/alex-martin?trk=search',
            'school':'Example University',
            'evidence':'Alex Martin, Rates Sales at Bank A, based in Paris. Education: Example University.'}


def test_selected_profile_is_private_deduplicated_and_never_fetches_linkedin(tmp_path,monkeypatch,contact):
    monkeypatch.setattr(state_store,'USER_DB_PATH',tmp_path/'accounts.sqlite3')
    def no_network(*args,**kwargs):
        raise AssertionError('Assisted import must not make provider or LinkedIn requests')
    monkeypatch.setattr(network.requests,'get',no_network)
    monkeypatch.setattr(network.requests,'post',no_network)
    assert network.import_assisted_contact('alice',contact)['imported']==1
    saved=network.list_contacts('alice')[0]
    assert saved['linkedin_url']=='https://www.linkedin.com/in/alex-martin'
    assert saved['school']=='Example University'
    assert saved['source_type']=='Sélection LinkedIn'
    assert saved['sales_priority']
    contact['role']='FX Sales'
    contact['evidence']=contact['evidence'].replace('Rates Sales','FX Sales')
    assert network.import_assisted_contact('alice',contact)['duplicates']==1
    assert network.list_contacts('alice')[0]['role']=='Rates Sales'
    assert network.list_contacts('bob')==[]


@pytest.mark.parametrize('changes',[
    {'linkedin_url':'https://linkedin.com.evil.invalid/in/alex'},
    {'linkedin_url':'javascript:alert(1)'},
    {'evidence':''},
    {'school':'Invented school'},
    {'name':'X'},
    {'role':[]},
    {'role':'Retail Sales','school':'','evidence':'Alex Martin, Retail Sales at Bank A, based in Paris.'},
])
def test_assisted_import_rejects_invalid_or_unsupported_facts(tmp_path,monkeypatch,contact,changes):
    monkeypatch.setattr(state_store,'USER_DB_PATH',tmp_path/'accounts.sqlite3')
    with pytest.raises(CityError):
        network.import_assisted_contact('alice',{**contact,**changes})


def test_assisted_http_origin_account_and_size_boundaries(tmp_path,monkeypatch,contact):
    monkeypatch.setattr(state_store,'USER_DB_PATH',tmp_path/'accounts.sqlite3')
    store=CityStore(state_store.USER_DB_PATH)
    app=FastAPI()
    add_city_routes(app,lambda req:req.headers.get('x-test-user'),store,CityWorker(store))
    headers={'x-test-user':'alice','X-MarketDesk-City':'1'}
    with TestClient(app) as client:
        url='/city/api/network/assisted'
        assert client.post(url,json=contact).status_code==401
        assert client.post(url,headers={'x-test-user':'alice'},json=contact).status_code==403
        assert client.post(url,headers={**headers,'Origin':'https://evil.invalid'},json=contact).status_code==403
        assert client.post(url,headers=headers,json=contact).status_code==201
        assert client.post(url,headers=headers,json=contact).json()['duplicates']==1
        assert client.post(url,headers=headers,json=[]).status_code==400
        assert client.post(url,headers=headers,json={**contact,'evidence':'x'*9000}).status_code==400
        assert client.get('/city/api/network',headers={'x-test-user':'bob'}).json()['contacts']==[]
