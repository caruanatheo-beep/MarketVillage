"""Maven public-source verification; no accounts, local data or cache reads."""
import os

import pytest
import requests

from internships_project import internships as jobs


SLUG = 'mavensecuritiesholdingltd'
COMPANY = 'Maven Securities'


@pytest.mark.skipif(os.environ.get('INTERNSHIPS_MAVEN_LIVE') != '1', reason='Public audit is opt-in')
def test_live_public_verification():
    response = requests.get(f'https://boards-api.greenhouse.io/v1/boards/{SLUG}/jobs',
                            params={'content': 'true'}, timeout=(8, 20))
    response.raise_for_status()
    payload = response.json()
    print('Maven catalogue:', len(payload['jobs']))
    for item in payload['jobs']:
        if jobs._kind(item['title']) and jobs._market_candidate(item['title']):
            print({key: item.get(key) for key in ('id', 'title', 'location', 'absolute_url', 'first_published')})
    response = requests.get('https://www.mavensecurities.com/jobs/', timeout=(8, 20))
    response.raise_for_status()
    import re
    for match in re.findall(r'.{0,90}(?:greenhouse|<link[^>]+icon).{0,190}', response.text, re.I):
        print(match)
    for name in ('sources', 'offers'):
        response = requests.get(f'https://caruanatheo-beep.github.io/Internships-Offres/{name}.json', timeout=(8, 20))
        response.raise_for_status()
        data = response.json()
        rows = data[name]
        print('Public', name, 'updated', data.get('updated'), 'count', len(rows),
              'Maven', [r.get('name', r.get('company')) for r in rows if 'maven' in str(r.get('name', r.get('company', ''))).lower()])
