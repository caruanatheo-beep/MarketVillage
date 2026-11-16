import json
from pathlib import Path
from internships_project import internships as jobs
from internships_project.source_catalog import GROUPS
from internships_project.city_source_strategy import source_priority_request,source_selection_context,attempts_for,CHECKPOINT


def test_tp_icap_brands_share_one_identity_and_ostrum_is_separate():
    for name in ['TP ICAP','Tullett Prebon','ICAP','Liquidnet','Louis Capital Markets']:
        assert jobs._canonical_company(name)=='tpicap'
    assert all(GROUPS[name]=='TP ICAP' for name in ['Tullett Prebon','ICAP','Liquidnet','Louis Capital Markets'])
    assert jobs._canonical_company('Ostrum AM')==jobs._canonical_company('Ostrum Asset Management')
    assert jobs._canonical_company('Ostrum AM') not in {jobs._canonical_company('Natixis'),jobs._canonical_company('BPCE')}


def test_priority_request_preserves_roles_grouping_and_explicit_quant_permission(tmp_path):
    path=tmp_path/'internships_project/data/sacha_source_priorities.json';path.parent.mkdir(parents=True)
    path.write_text(json.dumps({'groups':[
        {'category':'Banques','employers':['Nomura'],'roles':['Rates & Credit Sales']},
        {'category':'Gestion','employers':['Ostrum AM'],'roles':['Portfolio Assistant']},
        {'category':'Quant','employers':['Citadel Securities'],'roles':['Quant Trading']}]}))
    request=source_priority_request(tmp_path)
    for word in ['Nomura','Rates & Credit Sales','Ostrum AM','Portfolio Assistant','Citadel Securities','Quant Trading',
                 'une seule entrée groupe','Louis Capital Markets','entrée dédiée taux/crédit','expressément autorisée']:
        assert word in request
    assert len(request)<=2700 and request in source_selection_context(tmp_path)


def test_realistic_powershell_checkpoint_with_bom_and_structured_methods_is_readable(tmp_path):
    directory=tmp_path/'.city-worktrees'/('a'*32);directory.mkdir(parents=True)
    (directory/CHECKPOINT).write_text(json.dumps([{'source':'TP ICAP','status':'integrated',
        'methods':[{'method':'public_api','result':'verified'}],'reason':'Complete'}]),encoding='utf-8-sig')
    assert attempts_for(tmp_path,'a'*32)[0]['methods']==['public_api']
