"""Lina's public leads: evidence, atomic deduplication and daily scheduling."""
from concurrent.futures import ThreadPoolExecutor
import json

import pytest

from internships_project import network_discovery as network, state_store
from internships_project.marketdesk_city import CityStore, CityWorker, CityError


@pytest.mark.parametrize('role,excerpt,expected', [
    ('Fixed Income Sales', '', True), ('Rates Sales', '', True), ('FX Sales', '', True),
    ('Credit Sales', '', True), ('Equity Derivatives Sales', '', True),
    ('Structured Products Sales', '', True), ('Sales Trader', '', True),
    ('Institutional Sales', '', True), ('Liquidity Sales', '', True),
    ('Vendeur produits structurés', '', True), ('Cross Asset Sales', '', True),
    ('Sales', 'Sales on the Global Markets desk in Paris', True),
    ('Trader', 'Used to work in Sales', False), ('Market Risk Analyst', '', False),
    ('Sales', 'Works at a bank in Paris', False), ('Software Sales', '', False),
    ('Cash Management Sales', '', False), ('Salesforce Developer', '', False),
    ('Private Equity Sales', '', False), ('Corporate Treasury Sales', '', False),
])
def test_sales_targeting_requires_a_markets_role(role, excerpt, expected):
    assert network.contact_focus({'role':role, 'source_excerpt':excerpt, 'company':'Bank A'})['sales_priority'] is expected


@pytest.mark.parametrize('role', ['Institutional Sales', 'Treasury Sales'])
def test_ambiguous_sales_requires_a_financial_context(role):
    assert not network.contact_focus({'role':role, 'company':'Example'})['sales_priority']


def test_daily_selection_prioritizes_sales_after_dedup_and_keeps_existing_data(tmp_path, monkeypatch):
    monkeypatch.setattr(state_store, 'USER_DB_PATH', tmp_path / 'users.sqlite3')
    def lead(i, role):
        return network.parse_results(result(name=f'Alex Martin{i}', role=role, slug=f'alex-{i}'), 'Paris')[0]
    sales = [lead(i, 'Fixed Income Sales') for i in range(8)]
    traders = [lead(i+20, 'Trader') for i in range(10)]
    added, _ = network.save_leads('alice', traders+sales, sales_first=True)
    assert len(added) == 10
    assert sum(network.contact_focus(c)['sales_priority'] for c in added) == 8
    # Existing Sales cannot justify adding another ten non-Sales contacts tomorrow.
    added, _ = network.save_leads('alice', traders+sales, sales_first=True)
    assert added == []
    assert len(network.list_contacts('alice')) == 10
    assert sum(c['sales_priority'] for c in network.list_contacts('alice')) == 8


def result(name="Alex Martin", role="Fixed Income Sales", company="Bank A", city="Paris", slug="alex-martin"):
    return f'<div class="result"><a class="result__a" href="https://fr.linkedin.com/in/{slug}?trk=search">{name} - {role} - {company} | LinkedIn</a><a class="result__snippet">{city}. {role} chez {company}.</a></div>'


def test_public_evidence_and_filters():
    html = result() + result(role="Private Equity Analyst", slug="pe") + result(city="London", slug="london")
    contacts = network.parse_results(html, "Paris Sales")
    assert len(contacts) == 1
    c = contacts[0]
    assert (c["name"], c["role"], c["company"]) == ("Alex Martin", "Fixed Income Sales", "Bank A")
    assert c["linkedin_url"] == "https://www.linkedin.com/in/alex-martin"
    assert c["email"] == "" and c["verification_status"] == "À vérifier"
    assert "Paris" in c["source_excerpt"]
    with pytest.raises(ValueError, match="anti-robot"):
        network.parse_results('<form id="challenge-form"></form>', "Paris")
    with pytest.raises(ValueError, match="exploitable"):
        network.parse_results('<h1>Unavailable</h1>', "Paris")
    assert network.linkedin_url("https://linkedin.com.evil.test/in/alex") == ""
    assert network.linkedin_url("https://[invalid") == ""


def test_repeat_import_preserves_manual_edits_and_account_isolation(tmp_path, monkeypatch):
    monkeypatch.setattr(state_store, "USER_DB_PATH", tmp_path / "accounts.sqlite3")
    leads = network.parse_results(result(), "Paris")
    added, _ = network.save_leads("alice", leads)
    contacts = state_store.load_user_data("alice", "mail_contacts")
    key = added[0]["id"]
    contacts[key].update(role="Manual correction", notes="Do not replace", verification_status="Confirmé")
    state_store.save_user_data("alice", "mail_contacts", contacts)
    added, duplicates = network.save_leads("alice", leads)
    assert not added and duplicates == 1
    assert state_store.load_user_data("alice", "mail_contacts")[key]["notes"] == "Do not replace"
    assert network.list_contacts("bob") == []
    # A second URL for the same person and establishment must not create another record.
    leads[0]["linkedin_url"] = "https://www.linkedin.com/in/new-slug"
    assert network.save_leads("alice", leads)[0] == []


def test_concurrent_merge_and_ten_new_contact_cap(tmp_path, monkeypatch):
    monkeypatch.setattr(state_store, "USER_DB_PATH", tmp_path / "accounts.sqlite3")
    leads = network.parse_results("".join(result(name=f"Alex Martin{i}", slug=f"alex-{i}") for i in range(16)), "Paris")
    # Pre-create schema before concurrent transactions, just as the running app does.
    state_store.save_user_data("alice", "mail_contacts", {})
    with ThreadPoolExecutor(max_workers=2) as pool:
        batches = list(pool.map(lambda _: network.save_leads("alice", leads), range(2)))
    assert len(batches[0][0]) <= 10 and len(batches[1][0]) <= 10
    assert len(network.list_contacts("alice")) == 16


def test_daily_queue_once_across_workers_restart_pause_and_next_day(tmp_path):
    store = CityStore(tmp_path / "city.sqlite3")
    store.ensure_agents("alice")
    with ThreadPoolExecutor(max_workers=3) as pool:
        assert sum(pool.map(lambda _: store.enqueue_network_daily(), range(3))) == 1
    task = store.claim_next()
    assert task["agent_id"] == "networker" and json.loads(task["parameters_json"])["discover_public"]
    store.finish(task["id"], result={"count": 0})
    assert CityStore(store.path).enqueue_network_daily() == 0
    # A manual search bypasses today's schedule but concurrent clicks enqueue once.
    with ThreadPoolExecutor(max_workers=3) as pool:
        assert sum(pool.map(lambda _: store.enqueue_network_daily('alice', manual=True), range(3))) == 1
    manual_task = store.claim_next()
    store.finish(manual_task['id'], result={'count':0})
    assert store.enqueue_network_daily() == 0
    store.network_schedule("alice", False)
    with store.db() as db:
        db.execute("UPDATE city_network_schedule SET last_day='2000-01-01'")
    assert store.enqueue_network_daily() == 0
    store.network_schedule("alice", True)
    assert store.enqueue_network_daily() == 1
    assert store.network_schedule("bob")["last_task_id"] == ""


def test_complete_worker_collection_no_llm_and_no_duplicate_second_day(tmp_path, monkeypatch):
    monkeypatch.setenv("MARKETDESK_NETWORK_SEARCH_MODE", "public")
    monkeypatch.setattr(state_store, "USER_DB_PATH", tmp_path / "city.sqlite3")
    monkeypatch.setattr(network, "search_public", lambda q: network.parse_results(result(), q))
    store = CityStore(state_store.USER_DB_PATH)
    store.ensure_agents("alice")
    store.enqueue_network_daily("alice")
    assert CityWorker(store).run_once()
    schedule = store.network_schedule("alice")
    assert schedule["status"] == "completed" and schedule["report"]["count"] == 1
    assert len(network.list_contacts("alice")) == 1
    with store.db() as db:
        db.execute("UPDATE city_network_schedule SET last_day='2000-01-01'")
    store.enqueue_network_daily("alice")
    assert CityWorker(store).run_once()
    assert store.network_schedule("alice")["report"]["count"] == 0
    assert len(network.list_contacts("alice")) == 1


def test_all_sources_blocked_are_reported_not_an_empty_success(monkeypatch):
    monkeypatch.setenv("MARKETDESK_NETWORK_SEARCH_MODE", "public")
    monkeypatch.setattr(network, "search_public", lambda q: (_ for _ in ()).throw(ValueError("Source bloquée")))
    with pytest.raises(CityError, match="indisponible"):
        network.discover_contacts("alice")


def test_ai_results_require_real_search_sources_and_paris_evidence():
    url = "https://www.linkedin.com/in/alex-martin"
    record = {"name": "Alex Martin", "role": "Rates Sales", "company": "Bank A", "location": "Paris",
              "linkedin_url": url, "source_url": url, "evidence": "Alex Martin, Rates Sales at Bank A, Paris", "notes": ""}
    data = {"output": [{"type": "web_search_call", "status": "completed", "action": {"type": "search", "sources": [{"url": url}]}},
                       {"type": "message", "content": [{"type": "output_text", "text": json.dumps({"contacts": [record]})}]}]}
    assert len(network.validate_research(data)[0]) == 1
    record['source_url'] = "https://www.linkedin.com/in/invented"
    data['output'][1]['content'][0]['text'] = json.dumps({"contacts": [record]})
    assert network.validate_research(data) == ([], 1)
    data['output'] = data['output'][1:]
    with pytest.raises(ValueError, match="recherche Web"):
        network.validate_research(data)


def test_web_research_tokens_and_search_actions_are_costed(tmp_path, monkeypatch):
    from decimal import Decimal
    from internships_project import llm_usage
    monkeypatch.setattr(state_store, "USER_DB_PATH", tmp_path / "usage.sqlite3")
    response = {"model": "gpt-5.4-mini-2026-03-17", "usage": {
        "input_tokens": 1000, "output_tokens": 100, "input_tokens_details": {"cached_tokens": 0}},
        "output": [{"type": "web_search_call", "action": {"type": "search"}},
                   {"type": "web_search_call", "action": {"type": "open_page"}}]}
    with llm_usage.llm_user("alice"):
        llm_usage.record_response("lina_contact_discovery", "gpt-5.4-mini", response)
    assert llm_usage.usage_report()['estimated_usd'] == Decimal('0.01120')


def test_network_routes_are_private_and_require_browser_origin(tmp_path, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from internships_project.city_routes import add_city_routes
    monkeypatch.setattr(state_store, "USER_DB_PATH", tmp_path / "city.sqlite3")
    network.save_leads("alice", network.parse_results(result(), "Paris"))
    store = CityStore(state_store.USER_DB_PATH)
    app = FastAPI()
    add_city_routes(app, lambda req: req.headers.get("x-test-user"), store, CityWorker(store))
    with TestClient(app) as client:
        assert client.get('/city/api/network').status_code == 401
        assert len(client.get('/city/api/network', headers={'x-test-user': 'alice'}).json()['contacts']) == 1
        assert client.get('/city/api/network', headers={'x-test-user': 'bob'}).json()['contacts'] == []
        assert client.post('/city/api/network', headers={'x-test-user': 'alice'}, json={'enabled': False}).status_code == 403
        headers = {'x-test-user':'alice', 'X-MarketDesk-City':'1'}
        assert client.post('/city/api/network', headers={**headers, 'Origin':'https://other.test'}, json={'collect':True}).status_code == 403
        assert client.post('/city/api/network', headers=headers, json={'enabled':'yes'}).status_code == 400
        assert client.post('/city/api/network', headers=headers, json={'enabled':False}).json()['schedule']['enabled'] is False
        assert store.enqueue_network_daily('alice') == 0
        # Manual searches remain available with daily automation paused.
        assert client.post('/city/api/network', headers=headers, json={'collect':True}).json()['queued'] == 1
        first = store.claim_next()
        assert first['username'] == 'alice'
        assert client.post('/city/api/network', headers=headers, json={'collect':True}).json()['queued'] == 0
        store.finish(first['id'], result={'count':0})
        assert client.post('/city/api/network', headers=headers, json={'collect':True}).json()['queued'] == 1
        second = store.claim_next()
        assert second['id'] != first['id']
        store.finish(second['id'], error='Temporary API failure')
        assert client.post('/city/api/network', headers=headers, json={'collect':True}).json()['queued'] == 1
        assert store.network_schedule('alice')['enabled'] is False
        assert store.snapshot('bob')['tasks'] == []


def test_ai_daily_mission_saves_contacts_and_attributes_cost_without_real_api(tmp_path, monkeypatch):
    monkeypatch.setattr(state_store, "USER_DB_PATH", tmp_path / "city.sqlite3")
    monkeypatch.setenv("OPENAI_API_KEY", "test-only-not-a-real-key")
    monkeypatch.delenv("MARKETDESK_NETWORK_SEARCH_MODE", raising=False)
    url = 'https://www.linkedin.com/in/alex-martin'
    data = {"status":"completed", "model":"gpt-5.4-mini", "usage":{
        "input_tokens":1000,"output_tokens":100,"input_tokens_details":{"cached_tokens":0}}, "output":[
        {"type":"web_search_call","status":"completed","action":{"type":"search","sources":[{"url":url}]}},
        {"type":"message","content":[{"type":"output_text","text":json.dumps({"contacts":[{
            "name":"Alex Martin","role":"Rates Sales","company":"Bank A","location":"Paris",
            "source_url":url,"linkedin_url":url,"evidence":"Alex Martin, Rates Sales at Bank A in Paris","notes":""}]})}]}]}
    class Response:
        status_code = 200
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def iter_content(self, size): yield json.dumps(data).encode()
    calls=[]
    def post(url, **kwargs):
        calls.append(kwargs['json'])
        return Response()
    monkeypatch.setattr(network.requests, 'post', post)
    store=CityStore(state_store.USER_DB_PATH)
    store.ensure_agents('alice')
    assert store.enqueue_network_daily('alice') == 1
    assert CityWorker(store).run_once()
    assert store.network_schedule('alice')['report']['count'] == 1
    assert len(network.list_contacts('alice')) == 1
    assert calls[0]['model'] == 'gpt-5.4-mini' and calls[0]['tools'][0]['type'] == 'web_search'
    assert calls[0]['max_tool_calls'] == 4 and calls[0]['store'] is False
    with store.db() as db:
        task=db.execute("SELECT api_cost_usd FROM city_tasks WHERE agent_id='networker'").fetchone()
        assert float(task[0]) > 0.01
    assert store.enqueue_network_daily('alice') == 0 and len(calls) == 1


@pytest.mark.parametrize('error,expected', [
    (network.requests.ConnectTimeout('sensitive-detail'), 'délai'),
    (network.requests.ReadTimeout('sensitive-detail'), 'délai'),
    (network.requests.ConnectionError('sensitive-detail'), 'accès réseau'),
    (network.requests.RequestException('sensitive-detail'), 'Erreur de transport'),
])
def test_research_transport_errors_are_specific_safe_and_not_retried(tmp_path, monkeypatch, error, expected):
    monkeypatch.setattr(state_store, 'USER_DB_PATH', tmp_path/'private.sqlite3')
    monkeypatch.setenv('OPENAI_API_KEY','test-key-never-sent')
    calls=[]
    def fail(*args, **kwargs):
        calls.append(1)
        raise error
    monkeypatch.setattr(network.requests,'post',fail)
    with pytest.raises(CityError) as caught:
        network.research_contacts('alice')
    assert expected in str(caught.value)
    assert 'Rechercher maintenant' in str(caught.value)
    assert 'sensitive-detail' not in str(caught.value)
    assert caught.value.__cause__ is error
    assert calls == [1]
