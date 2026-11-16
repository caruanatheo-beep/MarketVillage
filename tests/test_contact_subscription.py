import json
from pathlib import Path

import pytest
from internships_project import network_discovery as network, city_coding, state_store
from internships_project.marketdesk_city import CityStore


@pytest.fixture
def store(tmp_path,monkeypatch):
    monkeypatch.setattr(state_store,'USER_DB_PATH',tmp_path/'city.sqlite3')
    return CityStore(state_store.USER_DB_PATH)


@pytest.mark.parametrize('schools',[False,True])
def test_lina_uses_codex_with_public_evidence_for_contacts_and_schools(store,monkeypatch,schools):
    monkeypatch.setattr(city_coding,'codex_binary',lambda:'codex')
    monkeypatch.setattr(city_coding,'codex_environment',lambda:{})
    monkeypatch.setattr(city_coding,'require_chatgpt',lambda *a:None)
    monkeypatch.setattr(city_coding,'require_daily_codex_budget',lambda *a,**kw:None)
    monkeypatch.setattr(city_coding,'record_daily_codex_usage',lambda *a:None)
    monkeypatch.setattr(network.requests,'post',lambda *a,**kw:pytest.fail('No paid API'))
    url='https://www.linkedin.com/in/alice-martin'
    target=dict(id='alice',name='Alice Martin',company='BNP Paribas',linkedin_url=url)
    def execute(command,directory,prompt,env,**kwargs):
        assert 'Tu es Lina' in prompt and '--search' in command
        assert 'forced_login_method="chatgpt"' in command
        if schools:
            records=[dict(id='alice',school='SKEMA',school_source_url=url),
                     dict(id='alice',school='Invented School',school_source_url=url)]
        else:
            records=[dict(name='Alice Martin',role='FX Sales',company='BNP Paribas',source_url=url),
                     dict(name='Invented Person',role='FX Sales',company='BNP Paribas',source_url=url)]
        Path(command[command.index('--output-last-message')+1]).write_text(json.dumps({'contacts':records}))
        return [{'type':'item.completed','item':{'type':'web_search','results':[
            dict(url=url,title='Alice Martin - BNP Paribas',snippet='Alice Martin, FX Sales at BNP Paribas in Paris. Education: Master SKEMA.')]}}]
    monkeypatch.setattr(city_coding,'_execute',execute)
    found,rejected=network.research_contacts('owner',education_targets=[target] if schools else None)
    assert len(found)==1 and rejected==1
    if schools:
        assert found[0]['school']=='SKEMA'
    else:
        assert found[0]['origin']=='lina_public_search' and found[0]['name']=='Alice Martin'


@pytest.mark.parametrize('agent,parameters',[
    ('networker',{'discover_public':True}),
    ('networker',{'operation':'enrich_schools'}),
    ('securities_scout',{'operation':'discover_service_contacts'}),
    ('prime_services_scout',{'operation':'discover_prime_services_contacts'})])
def test_interrupted_contact_search_restarts_once_with_same_task(store,agent,parameters):
    task=store.create_task('owner',agent,'Collect contacts',parameters,auto_run=True)
    with store.db() as db:
        db.execute("UPDATE city_tasks SET status='running',heartbeat_at='2000-01-01' WHERE id=?",(task['id'],))
    assert store.recover_stale()==1
    with store.db() as db:
        row=db.execute('SELECT status,retry_count FROM city_tasks WHERE id=?',(task['id'],)).fetchone()
        assert tuple(row)==('queued',1)
        db.execute("UPDATE city_tasks SET status='running',heartbeat_at='2000-01-01' WHERE id=?",(task['id'],))
    assert store.recover_stale()==1
    with store.db() as db:
        assert db.execute('SELECT status FROM city_tasks WHERE id=?',(task['id'],)).fetchone()[0]=='failed'
