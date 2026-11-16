from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from internships_project import network_discovery, state_store
from internships_project.city_routes import add_city_routes
from internships_project.marketdesk_city import CityStore, CityError


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(state_store, 'USER_DB_PATH', tmp_path/'accounts.sqlite3')
    return CityStore(state_store.USER_DB_PATH)


def message(**changes):
    return {'contact_id':'contact-a', 'recipient_email':'contact@example.invalid',
            'subject':'Échange sur votre métier', 'body':'Bonjour, voici un message de test.',
            'status':'draft', **changes}


def test_sent_reply_and_reminder_keep_the_original_send_date(store):
    draft=store.save_outreach('alice', message())
    assert draft['sent_at']==''
    sent=store.save_outreach('alice', message(id=draft['id'],status='sent',follow_up_at='2026-11-15'))
    follow=store.save_outreach('alice', message(id=draft['id'],status='follow_up',follow_up_at='2026-11-15'))
    assert follow['sent_at']==sent['sent_at']
    reply=store.save_outreach('alice', message(id=draft['id'],status='replied',follow_up_at='2026-11-15'))
    assert reply['follow_up_at']==''
    assert reply['sent_at']==sent['sent_at']
    with pytest.raises(CityError,match='déjà été envoyé'):
        store.save_outreach('alice',message(id=draft['id']))
    assert store.outreach_records('bob')==[]


@pytest.mark.parametrize('fields',[
    {'recipient_email':'bad-address'}, {'subject':'Objet\nAutre ligne'},
    {'status':'sent','recipient_email':''}, {'status':'ready','body':''},
    {'status':'replied'}, {'status':'follow_up'}, {'follow_up_at':'2026-99-99'},
])
def test_invalid_states_never_create_false_sends(store,fields):
    with pytest.raises(CityError):
        store.save_outreach('alice',message(**fields))
    assert store.outreach_records('alice')==[]


def test_empty_draft_is_allowed_and_update_cannot_change_owner_or_contact(store):
    saved=store.save_outreach('alice',message(recipient_email='',subject='',body=''))
    assert saved['status']=='draft'
    with pytest.raises(CityError,match='compte'):
        store.save_outreach('bob',message(id=saved['id']))
    with pytest.raises(CityError,match='remplacé'):
        store.save_outreach('alice',message(id=saved['id'],contact_id='another'))


def test_route_auth_utf8_size_and_archived_contact_updates(store,monkeypatch):
    contacts=[{'id':'contact-a'}]
    monkeypatch.setattr(network_discovery,'list_contacts',lambda _:contacts)
    app=FastAPI()
    add_city_routes(app,lambda request:request.headers.get('x-user'),store,SimpleNamespace(start=lambda:None))
    headers={'x-user':'alice','X-MarketDesk-City':'1'}
    with TestClient(app) as client:
        assert client.post('/city/api/outreach',json=message()).status_code==401
        assert client.post('/city/api/outreach',headers={'x-user':'alice'},json=message()).status_code==403
        response=client.post('/city/api/outreach',headers=headers,json=message(body='é'*9500))
        assert response.status_code==201
        record=response.json()['record']
        contacts.clear()
        assert client.post('/city/api/outreach',headers=headers,json=message()).status_code==400
        edited=client.post('/city/api/outreach',headers=headers,json=message(id=record['id'],notes='Contact archivé, suivi conservé.'))
        assert edited.status_code==200
        assert edited.json()['record']['notes'].startswith('Contact archivé')
        assert client.post('/city/api/outreach',headers={**headers,'x-user':'bob'},json=message(id=record['id'])).status_code==400
