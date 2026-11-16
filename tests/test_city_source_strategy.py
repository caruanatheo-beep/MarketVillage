import json
from datetime import datetime,timedelta,timezone
import pytest
from internships_project.city_source_strategy import (CHECKPOINT,RULES,attempts_for,record_attempts,
    source_key,source_selection_context,set_source_pause,sync_source_controls)


def checkpoint(root,task_id,rows):
    path=root/'.city-worktrees'/task_id/CHECKPOINT
    path.parent.mkdir(parents=True);path.write_text(json.dumps(rows),encoding='utf-8')
    return path


def test_failed_source_is_paused_for_24_hours_with_distinct_attempts(tmp_path):
    identity='a'*32
    checkpoint(tmp_path,identity,[{'source':'Test Bank','status':'blocked',
        'methods':['public API','public API','HTML','browser'],'reason':'API 429, HTML without vacancies'}])
    state={};now=datetime.now(timezone.utc)
    records=record_attempts(state,{'id':identity,'status':'completed'},tmp_path,now)
    assert records[0]['methods']==['public API','HTML','browser']
    assert datetime.fromisoformat(state['source_backoffs']['testbank']['until'])==now+timedelta(hours=24)


def test_daily_blocked_checkpoint_is_visible_without_campaign(tmp_path):
    checkpoint(tmp_path,'a'*32,[{'source':'Test Bank','status':'blocked','methods':['API'],'reason':'No valid response'}])
    assert 'Test Bank' in source_selection_context(tmp_path)
    assert 'Test Bank' not in source_selection_context(tmp_path,datetime.now(timezone.utc)+timedelta(days=2))


def test_manual_stop_and_resume_override_automatic_cooldown(tmp_path):
    checkpoint(tmp_path,'a'*32,[{'source':'Test Bank','status':'blocked','methods':['API'],'reason':'Failure'}])
    set_source_pause(tmp_path,'Test Bank',reason='Not useful now')
    assert 'Not useful now' in source_selection_context(tmp_path)
    set_source_pause(tmp_path,'Test Bank',resume=True)
    assert 'Test Bank' not in source_selection_context(tmp_path)


def test_successful_recovery_clears_automatic_source_backoff(tmp_path):
    checkpoint(tmp_path,'a'*32,[{'source':'Test Bank','status':'selected','methods':['API'],'reason':'Verified vacancy'}])
    state={'source_backoffs':{'testbank':{'source':'Test Bank'}}}
    record_attempts(state,{'id':'a'*32,'status':'completed','result':{'integrated':True}},tmp_path)
    assert not state['source_backoffs']
    assert attempts_for(tmp_path,'a'*32)[0]['status']=='integrated'


def test_integration_failure_does_not_pause_a_verified_source(tmp_path):
    checkpoint(tmp_path,'a'*32,[{'source':'Test Bank','status':'integrated','methods':['API'],'reason':'Verified offers; integration pending'}])
    state={'source_backoffs':{'testbank':{'source':'Test Bank'}}}
    records=record_attempts(state,{'id':'a'*32,'status':'failed'},tmp_path)
    assert records[0]['status']=='selected'
    assert not state['source_backoffs']


def test_research_time_budget_marks_unfinished_exploration_as_blocked(tmp_path):
    checkpoint(tmp_path,'a'*32,[{'source':'Test Bank','status':'exploring','methods':['API','HTML'],
        'started_at':(datetime.now(timezone.utc)-timedelta(minutes=7)).isoformat(),'reason':''}])
    row=attempts_for(tmp_path,'a'*32)[0]
    assert row['status']=='blocked' and 'six minutes' in row['reason']


def test_malformed_or_out_of_scope_checkpoints_are_ignored(tmp_path):
    assert attempts_for(tmp_path,'../private')==[]
    checkpoint(tmp_path,'a'*32,[{'source':'Test','status':'invalid','methods':[]}])
    assert attempts_for(tmp_path,'a'*32)==[]
    with pytest.raises(ValueError):set_source_pause(tmp_path,'x')
    assert source_key('Bank of America (BOFA)')==source_key('Bank of America')


def test_recovery_policy_reuses_connectors_and_bounds_research():
    for expected in ['connecteurs existants','Greenhouse','Workday','trois méthodes','6 minutes',
                     '403 ou 429','dernières minutes',"l'échec API"]:
        assert expected in RULES


def test_manual_pause_is_delivered_to_running_research_without_deleting_work(tmp_path):
    checkpoint(tmp_path,'a'*32,[{'source':'Test Bank','status':'exploring','methods':['API']}])
    directory=tmp_path/'.city-worktrees'/('a'*32)
    work=directory/'collector.py';work.write_text('work preserved')
    set_source_pause(tmp_path,'Test Bank',reason='Try another candidate')
    sync_source_controls(tmp_path,'a'*32)
    assert 'Test Bank' in (directory/'.sacha-source-controls.json').read_text()
    assert work.read_text()=='work preserved'


def test_chat_control_is_available_to_manager_and_sacha_only():
    from pydantic_ai.models.test import TestModel
    from internships_project.city_agents import build_agent
    for agent_id in ('desk_manager','internships_engineer'):
        assert 'control_source_research' in build_agent(agent_id,TestModel())._function_toolset.tools
    assert 'control_source_research' not in build_agent('market_analyst',TestModel())._function_toolset.tools
