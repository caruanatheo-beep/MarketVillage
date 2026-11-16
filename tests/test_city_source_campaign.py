from datetime import datetime,timedelta,timezone
import pytest
from internships_project import state_store
from internships_project.city_source_campaign import tick,allowed
from internships_project.city_coding import development_model
from internships_project.marketdesk_city import CityStore

@pytest.fixture
def campaign(tmp_path,monkeypatch):
    monkeypatch.setattr('internships_project.city_source_campaign.source_suggestions',lambda:[])
    monkeypatch.setattr(state_store,'USER_DB_PATH',tmp_path/'users.sqlite3')
    now=datetime.now(timezone.utc)
    state={'username':'alice','started_at':now.isoformat(),'ends_at':(now+timedelta(hours=24)).isoformat(),
           'next_at':now.isoformat(),'status':'running','results':[]}
    return state,CityStore(state_store.USER_DB_PATH),now

def test_scoped_model_and_publication_paths():
    from internships_project.city_worktree import code_path
    assert development_model('internships_engineer')=='gpt-6.1-sol'
    assert development_model('job_hunter')=='gpt-6-luna'
    assert allowed('internships_project/internships.py')
    assert allowed('tests/test_internships_example.py')
    assert allowed('tests/test_source_catalog.py')
    assert allowed('internships_project/source_coverage.py')
    assert allowed('internships_project/SOURCES.md')
    assert not allowed('internships_project/state_store.py')
    assert not allowed('tests/test_internships_../secret.py')
    assert not allowed('.env')
    assert not allowed('.github/workflows/pages.yml')
    assert allowed('internships_project/assets/company_logos/www.bloomberg.com.png')
    assert not allowed('internships_project/assets/company_logos/../secret.png')
    assert not allowed('internships_project/assets/company_logos/example.com.svg')
    assert code_path('internships_project/assets/company_logos/www.bloomberg.com.png')
    assert not code_path('internships_project/assets/company_logos/example.com.svg')


def test_trusted_metadata_helpers_keep_network_trust_but_never_api_secrets(monkeypatch):
    from internships_project.city_source_campaign import _source_helper_environment
    monkeypatch.setenv('NODE_EXTRA_CA_CERTS','test-ca.pem')
    monkeypatch.setenv('USERNAME','windows-user')
    monkeypatch.setenv('OPENAI_API_KEY','private-api-key')
    result=_source_helper_environment()
    assert result['NODE_EXTRA_CA_CERTS']=='test-ca.pem'
    assert result['USERNAME']=='windows-user'
    assert 'OPENAI_API_KEY' not in result

def test_campaign_does_not_overlap_and_stops_queued_work_at_deadline(campaign):
    state,store,now=campaign
    tick(state,store,now)
    task=state['task_id']
    tick(state,store,now+timedelta(hours=3))
    assert state['task_id']==task
    tick(state,store,now+timedelta(hours=24))
    assert state['status']=='completed'
    assert store.task_detail('alice',task)['status']=='cancelled'


def test_continuous_hour_starts_next_mission_while_previous_deployment_is_pending(campaign):
    state,store,now=campaign
    state.update(ends_at=(now+timedelta(hours=1)).isoformat(),
        continuous_until=(now+timedelta(hours=1)).isoformat(),interval_seconds=0)
    tick(state,store,now)
    first=state['task_id']
    store.claim_next()
    store.finish(first,result={'integrated':True,'commit':'a'*40})
    tick(state,store,now+timedelta(minutes=1),publisher=lambda *_:'b'*40)
    tick(state,store,now+timedelta(minutes=2),deployment=lambda _:'pending')
    assert state['task_id']!=first
    assert state['next_at']==(now+timedelta(minutes=2)).isoformat()
    assert state['results'][0]['publication_status']=='pushed; awaiting GitHub Pages'
    second=state['task_id']
    tick(state,store,now+timedelta(hours=1),deployment=lambda _:'pending')
    assert store.task_detail('alice',second)['status']=='cancelled'

def test_publication_requires_integration_and_is_verified(campaign):
    state,store,now=campaign
    tick(state,store,now)
    task=state['task_id']
    store.claim_next()
    store.finish(task,result={'integrated':True,'commit':'a'*40})
    calls=[]
    tick(state,store,now+timedelta(minutes=1),publisher=lambda *a:calls.append(a) or 'b'*40,
         deployment=lambda _: 'pending')
    assert len(calls)==1
    assert state['results'][0]['publication_status']=='pushed; awaiting GitHub Pages'
    tick(state,store,now+timedelta(minutes=7),deployment=lambda _: 'published')
    assert state['results'][0]['publication_status']=='published'

def test_release_conflict_stops_publications(campaign):
    state,store,now=campaign
    tick(state,store,now)
    store.claim_next()
    store.finish(state['task_id'],result={'integrated':True,'commit':'a'*40})
    def conflict(*_):raise ValueError('conflict')
    tick(state,store,now+timedelta(minutes=1),publisher=conflict)
    assert state['publication_blocked']
    tick(state,store,now+timedelta(hours=3))
    assert not state.get('task_id')


def test_daily_shared_source_is_published_before_campaign_and_publication_is_recorded(campaign):
    state,store,now=campaign
    state['started_at']=(now-timedelta(seconds=1)).isoformat()
    tick(state,store,now)
    active=state['task_id']
    daily=store.create_task('other','internships_engineer','Shared source',{'operation':'develop'})
    files=['internships_project/internships.py','internships_project/source_catalog.py']
    with store.db() as db:
        db.execute("UPDATE city_tasks SET status='running' WHERE id=?",(daily['id'],))
    store.finish(daily['id'],result={'integrated':True,'commit':'c'*40,'files':files})
    with store.db() as db:
        db.execute('INSERT INTO city_specialist_schedule VALUES (?,?,?,?)',
                   ('other','develop:morning','today',daily['id']))
    calls=[]
    tick(state,store,now+timedelta(seconds=1),publisher=lambda commit,*_:calls.append(commit) or 'd'*40)
    assert calls==['c'*40] and state['task_id']==active
    assert store.task_detail('other',daily['id'])['result']['publication_status']=='pushed; awaiting GitHub Pages'
    tick(state,store,now+timedelta(seconds=2),deployment=lambda _: 'published')
    assert store.task_detail('other',daily['id'])['result']['publication_status']=='published'
    history=store.coding_history('alice')['tasks']
    assert next(task for task in history if task['id']==daily['id'])['result']['publication_status']=='published'
    assert len(state['results'])==1


def test_private_manual_source_mission_is_not_automatically_published(campaign):
    state,store,now=campaign
    task=store.create_task('other','internships_engineer','Private',{'operation':'develop'})
    store.claim_next()
    store.finish(task['id'],result={'integrated':True,'commit':'c'*40,
        'files':['internships_project/internships.py','internships_project/source_catalog.py']})
    calls=[]
    tick(state,store,now,publisher=lambda *args:calls.append(args))
    assert calls==[] and state.get('task_id')!=task['id']


def test_command_error_identifies_phase_without_exposing_output(monkeypatch):
    from types import SimpleNamespace
    from internships_project import city_source_campaign as module
    monkeypatch.setattr(module.subprocess,'run',lambda *args,**kwargs:
        SimpleNamespace(returncode=1,stderr=b'private credential',stdout=b'private data'))
    with pytest.raises(module.PublicationCommandError) as caught:
        module.command(['git','apply','--check','-'],module.repo_root())
    assert caught.value.operation=='git apply'
    assert 'private' not in str(caught.value) and 'git -c' not in str(caught.value)


def test_completed_predecessor_does_not_delay_verification_of_following_publication(campaign):
    state,store,now=campaign
    state['next_at']=(now+timedelta(hours=2)).isoformat()
    state['results']=[{'task_id':str(index),'public_commit':str(index)*40,
        'publication_status':'pushed; awaiting GitHub Pages'} for index in (1,2)]
    calls=[]
    tick(state,store,now,deployment=lambda revision:calls.append(revision) or 'published')
    assert calls==['1'*40,'2'*40]
    assert all(record['publication_status']=='published' for record in state['results'])

def test_publication_never_pushes_if_candidate_tests_fail(tmp_path,monkeypatch):
    from internships_project import city_source_campaign as module
    monkeypatch.setattr(module,'repo_root',lambda:tmp_path)
    calls=[]
    def execute(args,cwd,**kwargs):
        calls.append(args)
        if args[0]==module.sys.executable:raise RuntimeError('Tests failed')
        if args[1]=='diff-tree':return b'internships_project/internships.py\n'
        if args[1]=='remote' and args[2]=='get-url':return module.REPOSITORY.encode()
        if args[1]=='rev-parse':return b'a'*40
        if args[1]=='diff':return b'public patch'
        if args[1]=='clone':
            target=module.Path(args[-1]);(target/'internships_project').mkdir(parents=True)
            (target/'internships_project/internships.py').write_text('value=1\n')
        return b''
    monkeypatch.setattr(module,'command',execute)
    with pytest.raises(RuntimeError,match='Tests failed'):module.publish('a'*40,tmp_path/'release')
    assert not any(len(args)>1 and args[1]=='push' for args in calls)

@pytest.mark.parametrize('job,conclusion,expected', [('deploy','success','published'),
    ('pages','success','published'),('deploy','failure','failed'),('deploy',None,'pending')])
def test_deployment_recognizes_actual_job_and_does_not_depend_on_email(job,conclusion,expected,monkeypatch):
    import requests
    from types import SimpleNamespace
    from internships_project.city_source_campaign import deployment_status
    def get(url,**kwargs):
        payload=({'jobs':[{'name':job,'conclusion':conclusion}]} if url.endswith('/jobs') else
                 {'workflow_runs':[{'id':42,'name':'Collect and publish public offers',
                                    'status':'completed' if conclusion else 'in_progress',
                                    'conclusion':'failure' if conclusion=='success' else conclusion}]})
        return SimpleNamespace(raise_for_status=lambda:None,json=lambda:payload)
    monkeypatch.setattr(requests,'get',get)
    assert deployment_status('a'*40)==expected

def test_sales_priority_and_suggestions_are_shared_by_daily_and_campaign_requests(monkeypatch):
    from internships_project import city_source_campaign as module
    from internships_project.marketdesk_city import SACHA_DAILY_SOURCE_REQUEST
    from internships_project.city_coding import AUTONOMOUS_FOCUS
    assert AUTONOMOUS_FOCUS['internships_engineer']==SACHA_DAILY_SOURCE_REQUEST
    assert SACHA_DAILY_SOURCE_REQUEST in module.REQUEST
    assert 'sans restriction de nationalité' in module.REQUEST
    assert 'Priorité aux Sales' in module.REQUEST and 'Institutional Sales' in module.REQUEST
    assert module.SUGGESTIONS_URL in module.REQUEST
    monkeypatch.setattr(module,'source_suggestions',lambda:[{'company':'Bank Example','url':'https://example.com/careers','reason':'Sales'}]*100)
    request=module.campaign_request()
    assert len(request)<=3000
    assert 'Bank Example' in request


def test_sacha_prioritizes_target_employers_and_audits_bloomberg_beyond_suggested_filters(monkeypatch):
    from internships_project import city_source_campaign as module
    from internships_project.marketdesk_city import SACHA_DAILY_SOURCE_REQUEST
    policy=SACHA_DAILY_SOURCE_REQUEST
    for employer in ('Bloomberg Analytics & Sales','JPMorgan','Goldman Sachs','Morgan Stanley','BNP Paribas','Nomura'):
        assert employer in policy
    assert 'Pas de repli automatique vers quant' in policy
    for scope in ('asset management','brokers','services titres','Client Service','Product Specialist',
                  'prime brokerage','securities lending','BlackRock','TP ICAP','State Street','CACEIS'):
        assert scope in policy
    assert 'avant les sources découvertes seul' in policy
    assert 'global sans filtres hérités' in policy and 'pagination pertinente' in policy
    assert 'Une page filtrée ou un échec technique' in policy
    assert 'sinon bilan honnête, sans ajout forcé' in policy
    monkeypatch.setattr(module,'source_suggestions',lambda:[{
        'company':'Bloomberg','url':'https://bloomberg.avature.net/careers/SearchJobs/?search=Sales','reason':''}])
    request=module.campaign_request()
    assert len(request)<=3000
    assert '"company": "Bloomberg"' in request
    assert 'COMPANY_ICON_HOSTS' in policy and 'site officiel' in policy


def test_company_logos_are_verified_pngs_with_bounded_size(tmp_path):
    from PIL import Image
    from internships_project.city_source_campaign import validate_logo
    path=tmp_path/'example.com.png'
    Image.new('RGB',(32,32),'white').save(path)
    validate_logo(path)
    Image.new('RGB',(1191,1191),'white').save(path)
    validate_logo(path)
    Image.new('RGB',(2049,1),'white').save(path)
    with pytest.raises(ValueError,match='small PNG'):validate_logo(path)
    path.write_bytes(b'<svg onload="javascript"></svg>')
    with pytest.raises((ValueError,OSError)):validate_logo(path)


def test_publisher_rejects_logo_with_unreachable_company_key(tmp_path):
    from internships_project.city_source_campaign import validate_logo_binding
    module=tmp_path/'internships.py'
    logo=tmp_path/'careers.bankofamerica.com.png'
    module.write_text("COMPANY_ICON_HOSTS = {'bank of america':'careers.bankofamerica.com'}")
    with pytest.raises(ValueError,match='canonical employer'):validate_logo_binding(logo,module)
    module.write_text("COMPANY_ICON_HOSTS = {'bankofamerica':'careers.bankofamerica.com'}")
    validate_logo_binding(logo,module)

def test_suggestions_reader_is_read_only_and_filters_untrusted_links(monkeypatch):
    import requests,json
    from internships_project import city_source_campaign as module
    class Response:
        status_code=200
        def __enter__(self):return self
        def __exit__(self,*_):pass
        def raise_for_status(self):pass
        def iter_content(self,_):
            yield json.dumps({'suggestions':[
                {'id':'a'*64,'company':'International Bank','url':'https://example.com/careers','reason':'Sales'},
                {'company':'Duplicate','url':'https://example.com/careers','reason':'x'},
                {'company':'Tracking duplicate','url':'https://example.com/careers?utm_source=site&_gl=tracking','reason':'x'},
                {'company':'Local','url':'http://127.0.0.1/','reason':'x'},
                {'company':'Secret','url':'https://example.com/?token=private','reason':'x'},
                {'company':None,'url':'https://example.com/other'}]}).encode()
    def get(url,**kwargs):
        assert url==module.SUGGESTIONS_URL and kwargs['allow_redirects'] is False
        assert kwargs['headers']['Origin']=='https://caruanatheo-beep.github.io'
        return Response()
    monkeypatch.setattr(requests,'get',get)
    proposals=module.source_suggestions()
    assert len(proposals)==1 and proposals[0]['company']=='International Bank'
    assert proposals[0]['id']=='a'*64

def test_suggestions_outage_is_reported_without_blocking_research(monkeypatch):
    from internships_project import city_source_campaign as module
    monkeypatch.setattr(module,'source_suggestions',lambda:(_ for _ in ()).throw(ValueError()))
    text=module.campaign_request()
    assert 'indisponible' in text and len(text)<=3000


def test_archiving_requires_public_employer_and_portal_and_confirms_removal(monkeypatch):
    import requests
    from types import SimpleNamespace
    from internships_project import city_source_campaign as m
    proposals=[{'id':'a'*64,'company':'Bloomberg','url':'https://bloomberg.avature.net/careers/?filter=stage','reason':''},
        {'id':'b'*64,'company':'Bloomberg','url':'https://different.example/jobs','reason':''},
        {'id':'c'*64,'company':'Other employer','url':'https://bloomberg.avature.net/careers/','reason':''}]
    reads=iter([proposals,proposals[1:]])
    monkeypatch.setattr(m,'source_suggestions',lambda:next(reads))
    monkeypatch.setattr(requests,'get',lambda *a,**kw:SimpleNamespace(raise_for_status=lambda:None,
        json=lambda:{'sources':[{'name':'Bloomberg','url':'https://bloomberg.avature.net/careers/','feeds':[]}]}))
    archived=[]
    monkeypatch.setattr(m,'_archive_suggestion_ids',lambda ids:archived.extend(ids))
    assert m.archive_integrated_suggestions()=={'status':'archived','count':1}
    assert archived==['a'*64]


@pytest.mark.parametrize('catalog', [[],None])
def test_local_integration_or_failed_catalog_never_archives_a_proposal(monkeypatch,catalog):
    import requests
    from types import SimpleNamespace
    from internships_project import city_source_campaign as m
    monkeypatch.setattr(m,'source_suggestions',lambda:[{'id':'a'*64,'company':'Bloomberg',
        'url':'https://bloomberg.avature.net/careers/','reason':''}])
    monkeypatch.setattr(requests,'get',lambda *a,**kw:SimpleNamespace(raise_for_status=lambda:None,
        json=lambda:{'sources':catalog}))
    monkeypatch.setattr(m,'_archive_suggestion_ids',lambda ids:pytest.fail('Unpublished source archived'))
    if catalog is None:
        with pytest.raises(ValueError):m.archive_integrated_suggestions()
    else:
        assert m.archive_integrated_suggestions()['count']==0


def test_unconfirmed_archive_is_reported_as_failure(monkeypatch):
    import requests
    from types import SimpleNamespace
    from internships_project import city_source_campaign as m
    monkeypatch.setattr(m,'source_suggestions',lambda:[{'id':'a'*64,'company':'Bloomberg',
        'url':'https://bloomberg.avature.net/careers/','reason':''}])
    monkeypatch.setattr(requests,'get',lambda *a,**kw:SimpleNamespace(raise_for_status=lambda:None,
        json=lambda:{'sources':[{'name':'Bloomberg','url':'https://bloomberg.avature.net/careers/'}]}))
    monkeypatch.setattr(m,'_archive_suggestion_ids',lambda ids:None)
    with pytest.raises(RuntimeError,match='not confirmed'):m.archive_integrated_suggestions()


def test_archiving_matches_employer_acronym_but_keeps_other_recommendations(monkeypatch):
    import requests
    from types import SimpleNamespace
    from internships_project import city_source_campaign as m
    proposals=[{'id':'a'*64,'company':'Bank of America (BOFA)','url':'https://careers.bankofamerica.com/en-us/students/job-search','reason':''},
        {'id':'b'*64,'company':'Morgan Stanley','url':'https://www.morganstanley.com/careers/','reason':''}]
    reads=iter([proposals,proposals[1:]])
    monkeypatch.setattr(m,'source_suggestions',lambda:next(reads))
    monkeypatch.setattr(requests,'get',lambda *a,**kw:SimpleNamespace(raise_for_status=lambda:None,
        json=lambda:{'sources':[{'name':'Bank of America','url':'https://careers.bankofamerica.com/en-us/students/job-search'}]}))
    archived=[]
    monkeypatch.setattr(m,'_archive_suggestion_ids',lambda ids:archived.extend(ids))
    assert m.archive_integrated_suggestions()['count']==1
    assert archived==['a'*64]


def test_approved_corporate_lead_archives_only_after_exact_employer_is_public(monkeypatch,tmp_path):
    import json
    import requests
    from types import SimpleNamespace
    from internships_project import city_source_campaign as m
    data=tmp_path/'internships_project/data'
    data.mkdir(parents=True)
    (data/'sacha_source_priorities.json').write_text(json.dumps({'recommendation_urls':{
        'Ostrum AM':'https://www.ostrum.com/en/our-people',
        'Mirova':'https://www.mirova.com/en/join-us'}}))
    monkeypatch.setattr(m,'repo_root',lambda:tmp_path)
    proposals=[{'id':'a'*64,'company':'Ostrum AM','url':'https://www.ostrum.com/en/our-people'},
        {'id':'b'*64,'company':'Mirova','url':'https://www.mirova.com/en/join-us'},
        {'id':'c'*64,'company':'Ostrum AM','url':'https://different.example/jobs'}]
    reads=iter([proposals,proposals[1:]])
    monkeypatch.setattr(m,'source_suggestions',lambda:next(reads))
    monkeypatch.setattr(requests,'get',lambda *a,**kw:SimpleNamespace(raise_for_status=lambda:None,
        json=lambda:{'sources':[{'name':'Ostrum Asset Management','url':'https://jobs.example/ostrum'},
                               {'name':'BPCE / Natixis / BRED','url':'https://jobs.example/bpce'}]}))
    archived=[]
    monkeypatch.setattr(m,'_archive_suggestion_ids',lambda ids:archived.extend(ids))
    assert m.archive_integrated_suggestions()=={'status':'archived','count':1}
    assert archived==['a'*64]
