from types import SimpleNamespace
import pytest
from internships_project import internships as m


def test_catalogue_continues_past_400_and_preserves_initial_total(monkeypatch):
    offsets=[]
    def post(url,json,**kwargs):
        offset=json['offset'];offsets.append(offset)
        rows=[dict(title='Comptable CDI',locationsText='Paris',externalPath=f'/job/Paris/Role_{i}') for i in range(offset,min(441,offset+20))]
        if offset==440:rows[0]['title']='Rates Sales Intern'
        return SimpleNamespace(raise_for_status=lambda:None,json=lambda:{'total':441 if offset==0 else 0,'jobPostings':rows})
    monkeypatch.setattr(m.requests,'post',post)
    monkeypatch.setattr(m.requests,'get',lambda *a,**k:SimpleNamespace(raise_for_status=lambda:None,json=lambda:{'jobPostingInfo':{}}))
    monkeypatch.setattr(m,'_cached_detail',lambda j:None)
    found=m._workday_jobs('ING',m.WORKDAY['ING'])
    assert offsets==list(range(0,441,20))
    assert len(found)==1 and found[0].url.endswith('Role_440')


def test_repeating_page_is_not_treated_as_complete(monkeypatch):
    rows=[dict(title='Comptable CDI',locationsText='Paris',externalPath=f'/job/Paris/Role_{i}') for i in range(20)]
    monkeypatch.setattr(m.requests,'post',lambda *a,**k:SimpleNamespace(raise_for_status=lambda:None,json=lambda:{'total':40,'jobPostings':rows}))
    with pytest.raises(ValueError,match='répétée'):
        m._workday_jobs('ING',m.WORKDAY['ING'])
