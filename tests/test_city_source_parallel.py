"""Disjoint campaign lanes retain a single integration/publication pipeline."""
import json
from datetime import datetime,timedelta,timezone
import pytest
from internships_project import city_source_campaign as campaign,city_source_strategy as strategy,state_store
from internships_project.marketdesk_city import CityStore

@pytest.fixture
def parallel(tmp_path,monkeypatch):
    now=datetime.now(timezone.utc)
    monkeypatch.setattr(state_store,'USER_DB_PATH',tmp_path/'accounts.db')
    monkeypatch.setattr(campaign,'repo_root',lambda:tmp_path)
    monkeypatch.setattr(campaign,'source_suggestions',lambda:[])
    data=tmp_path/'internships_project/data';data.mkdir(parents=True)
    priorities={'groups':[{'category':'Sources','employers':['Nomura','FactSet'],'roles':['Sales']}],
        'assignment_ends_at':(now+timedelta(hours=1)).isoformat(),
        'assignments':{'internships_engineer':['FactSet'],'quality_engineer':['Nomura']}}
    (data/'sacha_source_priorities.json').write_text(json.dumps(priorities))
    state={'username':'alice','started_at':now.isoformat(),'ends_at':priorities['assignment_ends_at'],
        'continuous_until':priorities['assignment_ends_at'],'next_at':now.isoformat(),'interval_seconds':0,
        'status':'running','results':[],'employers':['FactSet'],
        'second_lane':{'agent_id':'quality_engineer','employers':['Nomura'],'next_at':now.isoformat(),'status':'running'}}
    return tmp_path,state,CityStore(state_store.USER_DB_PATH),now

def test_parallel_lanes_claim_together_with_disjoint_requests(parallel):
    root,state,store,now=parallel
    campaign.tick(state,store,now)
    first=store.claim_next();second=store.claim_next()
    assert {first['agent_id'],second['agent_id']}=={'internships_engineer','quality_engineer'}
    for task in (first,second):
        parameters=json.loads(task['parameters_json'])
        text=parameters['request']
        if task['agent_id']=='quality_engineer':
            assert 'Nomura' in text and 'FactSet' not in text
            assert parameters['source_campaign_lane']=='B'
        else:assert 'FactSet' in text and 'Nomura' not in text
        context=strategy.source_selection_context(root,agent_id=task['agent_id'])
        assert ('FactSet' in context)==(task['agent_id']=='internships_engineer')

def test_parallel_deadline_cancels_both_queued_lanes(parallel):
    root,state,store,now=parallel
    campaign.tick(state,store,now)
    ids=[state['task_id'],state['second_lane']['task_id']]
    campaign.tick(state,store,now+timedelta(hours=2))
    assert state['status']=='completed'
    assert all(store.task_detail('alice',task)['status']=='cancelled' for task in ids)

def test_parallel_publication_follows_integration_finish_order(parallel):
    root,state,store,now=parallel
    campaign.tick(state,store,now)
    first=store.claim_next();second=store.claim_next()
    store.finish(second['id'],result={'integrated':True,'commit':'b'*40})
    store.finish(first['id'],result={'integrated':True,'commit':'a'*40})
    with store.db() as db:
        db.execute('UPDATE city_tasks SET finished_at=? WHERE id=?',((now-timedelta(seconds=2)).isoformat(),second['id']))
        db.execute('UPDATE city_tasks SET finished_at=? WHERE id=?',((now-timedelta(seconds=1)).isoformat(),first['id']))
    calls=[]
    campaign.tick(state,store,now,publisher=lambda commit,_:calls.append(commit) or commit)
    assert calls==['b'*40,'a'*40]
    assert len(state['results'])==2

def test_overlapping_assignment_is_rejected(parallel):
    root,state,store,now=parallel
    path=root/'internships_project/data/sacha_source_priorities.json'
    config=json.loads(path.read_text());config['assignments']['quality_engineer']=['FactSet']
    path.write_text(json.dumps(config))
    with pytest.raises(ValueError,match='Overlapping'):strategy.source_priority_request(root,agent_id='internships_engineer')


def test_source_reinforcement_does_not_change_other_quality_missions():
    from internships_project.city_coding import development_profile,development_model
    assert development_profile('quality_engineer',{'operation':'develop'})=='quality_engineer'
    assert development_profile('quality_engineer',{'source_campaign_lane':'B'})=='quality_engineer'
    profile=development_profile('quality_engineer',{'source_campaign_lane':'B','source_campaign':'session'})
    assert profile=='internships_engineer'
    assert development_model(profile)==development_model('internships_engineer')


def test_publication_failure_blocks_both_lanes_without_losing_branches(parallel):
    root,state,store,now=parallel
    campaign.tick(state,store,now)
    for commit in ('a','b'):
        task=store.claim_next()
        store.finish(task['id'],result={'integrated':True,'commit':commit*40,'branch':'preserved/'+commit})
    def blocked(*args):raise ValueError('Conflict')
    campaign.tick(state,store,now,publisher=blocked)
    assert state['publication_blocked']
    assert len(state['results'])==2
    assert all(row['publication_status']=='blocked' for row in state['results'])
    assert store.claim_next() is None


def test_heartbeat_controls_and_proposals_keep_only_assigned_employers(parallel,monkeypatch):
    root,state,store,now=parallel
    campaign.tick(state,store,now)
    (root/'internships_project/data/sacha_source_campaign.json').write_text(json.dumps(state))
    for agent,task in [('internships_engineer',state['task_id']),('quality_engineer',state['second_lane']['task_id'])]:
        directory=root/'.city-worktrees'/task;directory.mkdir(parents=True)
        (directory/strategy.CHECKPOINT).write_text('[]')
        strategy.sync_source_controls(root,task)
        context=json.loads((directory/'.sacha-source-controls.json').read_text(encoding='utf-8'))['selection']
        assert ('FactSet' in context)==(agent=='internships_engineer')
        assert ('Nomura' in context)==(agent=='quality_engineer')
    monkeypatch.setattr(campaign,'source_suggestions',lambda:[
        {'company':'Nomura','url':'https://nomura.com/','reason':'Bank'},
        {'company':'FactSet','url':'https://factset.com/','reason':'Data'}])
    request=campaign.campaign_request(priority='Source assignment',employers=['FactSet'])
    assert 'FactSet' in request and 'Nomura' not in request
