"""Public inventory generated from the same registry as the collectors."""
import re
from datetime import date

from . import internships as jobs
from .public_safety import public_job_url


GROUPS = {
    'Tullett Prebon':'TP ICAP', 'ICAP':'TP ICAP', 'Liquidnet':'TP ICAP', 'Louis Capital Markets':'TP ICAP',
    'Société Générale Careers':'Société Générale',
    'Amundi · portail groupe':'Amundi',
    'BPCE Open Data':'BPCE / Natixis / BRED',
    'Lazard Student Careers':'Lazard', 'Lazard Professional Careers':'Lazard',
    'J.P. Morgan Careers':'J.P. Morgan', 'Goldman Sachs Campus Careers':'Goldman Sachs',
    'Schroders Careers':'Schroders', 'JobTeaser · sitemap':'JobTeaser',
    'Business France VIE':'Business France',
}
EXTRA_URLS = {
    'AQR Capital Management': 'https://careers.aqr.com/',
    'Société Générale Careers':'https://careers.societegenerale.com/',
    'Société Générale':'https://careers.societegenerale.com/',
    'Optiver':'https://optiver.com/working-at-optiver/career-opportunities/',
    'BNP Paribas VIE':'https://group.bnpparibas/emploi-carriere/toutes-offres-emploi/vie',
    'Business France VIE':'https://mon-vie-via.businessfrance.fr/offres',
    'Covéa Finance':'https://coveafinance-recrute.talent-soft.com/',
    'Comgest':'https://cm.comgest.com/fr/about-us/nos-collaborateurs/carrieres/stages',
    'BPCE Open Data':'https://recrutement.bpce.fr/offres-emploi',
    'JobTeaser · sitemap':'https://www.jobteaser.com/fr/job-offers',
    'Groupama AM':'https://www.groupama-am.com/fra/fr/intermediaire/carriere/groupama-asset-management-carriere',
    'AXA':"https://recrutement.axa.fr/recherche-d%27offres",
}
ASSET_MANAGERS = {
    'PIMCO',
    'Fidelity International',
    'Capital Group',
    'AQR Capital Management',
    'Pictet Asset Management',
    'Sienna Investment Managers','Sycomore Asset Management','Point72','Qube Research & Technologies',
    '21shares','WisdomTree','Amundi','Covéa Finance','Comgest','DNCA','Candriam','Groupama AM',
    'Schroders','La Française','Ofi Invest','Tikehau Capital','CFM',
}
TRADING = {'Jump Trading', 'Five Rings', 'DRW', 'Akuna Capital', 'Da Vinci', 'Flow Traders', 'IMC Trading', 'Jane Street', 'Kepler Cheuvreux', 'Marex', 'Maven Securities', 'Optiver', 'Squarepoint Capital', 'Statkraft', 'Susquehanna', 'TP ICAP'}
OTHER = {'Finance Active','Banque de France','Business France','JobTeaser','AXA','Euronext'}
CLIENT_SOLUTIONS = {'Bloomberg', 'FactSet', 'Murex'}

# First live addition, not the collection date. Record new sources here;
# leave the older baseline undated rather than inventing historical dates.
SOURCE_ADDED_ON = {
    'RBC Capital Markets': '2026-11-16',
    'Murex': '2026-11-16',
    'PIMCO': '2026-11-16',
    'Jump Trading': '2026-11-16',
    'Five Rings': '2026-11-16',
    'DRW': '2026-11-16',
    'Fidelity International': '2026-11-16',
    'Capital Group': '2026-11-15',
    'Maven Securities': '2026-11-15',
    'FactSet': '2026-11-15',
    'Squarepoint Capital': '2026-11-15',
    'TP ICAP': '2026-11-15',
    'Morgan Stanley': '2026-11-15',
    'Bank of America': '2026-11-15',
    'Bloomberg': '2026-11-15',
    'AQR Capital Management': '2026-11-15',
    'Susquehanna': '2026-11-15',
    'Akuna Capital': '2026-11-15',
    'Candriam': '2026-11-12',
    'BNY': '2026-11-12',
    'Commerzbank': '2026-11-12',
    'Standard Chartered': '2026-11-12',
    'Citi': '2026-11-14',
    'NatWest Markets': '2026-11-14',
    'Pictet Asset Management': '2026-11-14',
}


def public_source_catalog() -> list[dict]:
    urls = dict(jobs.CAREER_PORTALS)
    urls.update({company:config[0] for company,config in jobs.CAREER_LISTINGS.items()})
    urls.update({company:f'https://{host}/en-US/{site}' for company,(host,tenant,site) in jobs.WORKDAY.items()})
    urls.update({name:f'{host}/hcmUI/CandidateExperience/en/sites/{site}/jobs'
                 for name,(host,site,company) in jobs.ORACLE_CAREER_BOARDS.items()})
    for registry,base in ((jobs.SMARTRECRUITERS,'https://careers.smartrecruiters.com/'),
                          (jobs.GREENHOUSE,'https://job-boards.greenhouse.io/'),
                          (jobs.LEVER,'https://jobs.lever.co/'),(jobs.ASHBY,'https://jobs.ashbyhq.com/')):
        urls.update({company:base+slug for slug,company in registry.items()})
    urls.update(EXTRA_URLS)
    groups = {}
    for name,_,_ in jobs._opportunity_source_tasks():
        url = public_job_url(urls[name])
        group = 'BNP Paribas' if name.startswith('BNP Paribas') else GROUPS.get(name,name)
        if group not in groups:
            category=('Gestion d’actifs' if group in ASSET_MANAGERS else
                      'Information financière & relation clients' if group in CLIENT_SOLUTIONS else
                      'Courtage & trading' if group in TRADING else
                      'Autres sources' if group in OTHER else 'Banques & services titres')
            groups[group]={'name':group,'category':category,'url':url,'feeds':[],
                           'added_on':SOURCE_ADDED_ON.get(group, '')}
        groups[group]['feeds'].append({'name':name,'url':url})
        if name==group:
            groups[group]['url']=url
    return sorted(groups.values(),key=lambda source:source['name'].casefold())


def validate_source_catalog(data: dict) -> None:
    if set(data) != {'updated','sources','request_endpoint'} or not isinstance(data['updated'],str) or not isinstance(data['sources'],list):
        raise ValueError('Invalid public source catalog')
    if data['request_endpoint'] not in ('','https://marketdesk-source-suggestions.source-suggestions.workers.dev/suggestions'):
        raise ValueError('Invalid source request endpoint')
    for source in data['sources']:
        if set(source) - {'added_on'} != {'name','category','url','feeds','logo'}:
            raise ValueError('Unexpected source catalog field')
        added = source.get('added_on', '')
        if not isinstance(added, str) or added and (not re.fullmatch(r'\d{4}-\d{2}-\d{2}', added)
                                                   or date.fromisoformat(added).isoformat() != added):
            raise ValueError('Invalid source addition date')
        if any(not isinstance(source[key],str) or len(source[key])>500 for key in ('name','category','url','logo')):
            raise ValueError('Invalid source catalog value')
        public_job_url(source['url'])
        if source['logo'] and not re.fullmatch(r'logos/[A-Za-z0-9._-]+\.png',source['logo']):
            raise ValueError('Invalid public source logo')
        if not isinstance(source['feeds'],list) or not source['feeds']:
            raise ValueError('Missing source feeds')
        for feed in source['feeds']:
            if set(feed) != {'name','url'} or not isinstance(feed['name'],str) or len(feed['name'])>150 or not isinstance(feed['url'],str) or len(feed['url'])>500:
                raise ValueError('Invalid public source feed')
            public_job_url(feed['url'])
