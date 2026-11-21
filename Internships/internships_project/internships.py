"""Public employer career feeds for markets internships and early careers."""

from __future__ import annotations

import html
import base64
import json
import logging
import os
import re
import threading
import time
import unicodedata
from difflib import SequenceMatcher
from functools import lru_cache
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, replace
from datetime import date, datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
from urllib.parse import parse_qsl, unquote, urljoin, urlparse
from xml.etree import ElementTree

import requests


SMARTRECRUITERS = {
    "SocieteGenerale4": "Société Générale",
    "SiennaInvestmentManagers": "Sienna Investment Managers",
    "SycomoreAssetManagement": "Sycomore Asset Management",
    "Statkraft1": "Statkraft",
    "Financeactive": "Finance Active",
}
GREENHOUSE = {
    "xtxmarketstechnologies": "XTX Markets",
    "wehrtyou": "Hudson River Trading",
    "marketaxesscorporation": "MarketAxess",
    "jumptrading": "Jump Trading",
    "fiveringsllc": "Five Rings",
    "drweng": "DRW",
    "mavensecuritiesholdingltd": "Maven Securities",
    "squarepointcapital": "Squarepoint Capital",
    "aqr": "AQR Capital Management",
    "akunacapital": "Akuna Capital",
    "point72": "Point72",
    "janestreet": "Jane Street",
    "imc": "IMC Trading",
    "flowtraders": "Flow Traders",
    "quberesearchandtechnologies": "Qube Research & Technologies",
    "21shares": "21shares",
    "davinciderivatives": "Da Vinci",
}
LEVER = {
    "wisdomtree-2": "WisdomTree",
}
ASHBY = {}
WORKDAY = {
    "S&P Global Market Intelligence": ("spgi.wd5.myworkdayjobs.com", "spgi", "SPGI_Careers"),
    "LSEG": ("lseg.wd3.myworkdayjobs.com", "lseg", "Careers"),
    "Mizuho": ("mizuho.wd1.myworkdayjobs.com", "mizuho", "mizuhoamericas"),
    "RBC Capital Markets": ("rbc.wd3.myworkdayjobs.com", "rbc", "RBCEARLYTALENT1"),
    "Murex": ("murex.wd3.myworkdayjobs.com", "murex", "MurexCareerPage1"),
    "PIMCO": ("pimco.wd1.myworkdayjobs.com", "pimco", "pimco-careers"),
    "FactSet": ("factset.wd108.myworkdayjobs.com", "factset", "FactSetCareers"),
    "Capital Group": ("capgroup.wd1.myworkdayjobs.com", "capgroup", "capitalgroupcareers"),
    "TP ICAP": ("tp.wd107.myworkdayjobs.com", "tp", "TP-ICAP"),
    "Citi": ("citi.wd5.myworkdayjobs.com", "citi", "2"),
    "NatWest Markets": ("rbs.wd3.myworkdayjobs.com", "rbs", "RBS"),
    "BBVA": ("bbva.wd3.myworkdayjobs.com", "bbva", "BBVA"),
    "ING": ("ing.wd3.myworkdayjobs.com", "ing", "ICSGBLCOR"),
    "Deutsche Bank": ("db.wd3.myworkdayjobs.com", "db", "DBWebsite"),
    "Barclays": ("barclays.wd3.myworkdayjobs.com", "barclays", "External_Career_Site_Barclays"),
    "Santander CIB": ("santander.wd3.myworkdayjobs.com", "santander", "SantanderCareers"),
    "MUFG": ("mufgub.wd3.myworkdayjobs.com", "mufgub", "MUFG-Careers"),
    "Euronext": ("hrhub.wd3.myworkdayjobs.com", "hrhub", "Euronext_Career_Page"),
    "Rothschild & Co": ("rothschildandco.wd3.myworkdayjobs.com", "rothschildandco", "Rothschildandco_Lateral"),
    "CIBC Capital Markets": ("cibc.wd3.myworkdayjobs.com", "cibc", "campus"),
    "TD Securities": ("td.wd3.myworkdayjobs.com", "td", "TD_Bank_Careers"),
    "OCBC Global Markets": ("ocbc.wd102.myworkdayjobs.com", "ocbc", "External"),
}
CAREER_PORTALS = {
    "Morgan Stanley": "https://www.morganstanley.com/careers/career-opportunities-search",
    "Morgan Stanley Campus": "https://morganstanley.tal.net/vx/lang-en-GB/mobile-0/brand-2/candidate/jobboard/vacancy/1/adv/",
    "Bank of America": "https://careers.bankofamerica.com/en-us/students/job-search",
    "Bloomberg": "https://bloomberg.avature.net/careers/SearchJobs/",
    "Susquehanna": "https://careers.sig.com/institutional-sales/jobs",
    "Pictet Asset Management": "https://career5.successfactors.eu/career?company=banquepict",
    "BBVA": "https://bbva.wd3.myworkdayjobs.com/en-US/BBVA",
    "ING": "https://careers.ing.com/en",
    "JobTeaser · recherche publique": "https://www.jobteaser.com/fr/job-offers?locale=fr",
    "BNP Paribas": "https://group.bnpparibas/emploi-carriere/toutes-offres-emploi",
    "BNP Paribas Asset Management": "https://group.bnpparibas/emploi-carriere/toutes-offres-emploi/bnp-paribas-asset-management",
    "BNP Paribas CIB": "https://careers.cib.bnpparibas/job-contract-type/internship/",
    "BNP Paribas Graduate": "https://group.bnpparibas/emploi-carriere/toutes-offres-emploi/graduate-programme-cdi",
    "BNP Paribas APAC": "https://bnppapply.tal.net/candidate/jobboard/vacancy/3/adv/",
    "Crédit Agricole CIB": "https://jobs.ca-cib.com/offre-de-emploi/liste-offres.aspx?mode=layer&lcid=1036",
    "Amundi": "https://jobs.amundi.com/offre-de-emploi/liste-toutes-offres.aspx?lcid=1036",
    "Groupe Crédit Agricole": "https://www.groupecreditagricole.jobs/",
    "BPCE / Natixis / BRED": "https://recrutement.bpce.fr/offres-emploi",
    "Crédit Mutuel / CIC": "https://recrutement.creditmutuel.fr/fr/nos_offres.html",
    "Crédit Mutuel Arkéa": "https://recrutement.arkea.com/accueil.aspx",
    "Fortuneo": "https://recrutement.arkea.com/accueil.aspx",
    "La Banque Postale": "https://www.labanquepostale.com/candidats/offres-d-emploi/nos-offres-d-emploi.reg-2285.html",
    "La Banque Postale Asset Management": "https://www.lbpam.com/fr/carrieres/liste-des-postes",
    "ODDO BHF": "https://www.oddo-bhf.com/careers/",
    "Rothschild & Co": "https://www.rothschildandco.com/en-gb/careers/",
    "UBS": "https://www.ubs.com/global/en/careers/search-jobs.html",
    "Santander CIB": "https://santander.wd3.myworkdayjobs.com/en-US/SantanderCareers",
    "CIBC Capital Markets": "https://cibc.wd3.myworkdayjobs.com/en-US/campus",
    "TD Securities": "https://td.wd3.myworkdayjobs.com/en-US/TD_Bank_Careers",
    "OCBC Global Markets": "https://ocbc.wd102.myworkdayjobs.com/en-US/External",
    "Bpifrance": "https://talents.bpifrance.fr/metier/finances/finances-direction-financiere-et-activites-de-marche/",
    "Banque Transatlantique": "https://www.banquetransatlantique.com/fr/nos_offres.html",
    "CCF": "https://www.groupeccf.fr/espace-candidats",
    "Crédit Coopératif": "https://www.credit-cooperatif.coop/votre-banque/une-autre-banque-est-possible/nous-rejoindre/",
    "Banque de France": "https://www.banque-france.fr/fr/rejoignez-la-banque-de-france",
    "Caisse des Dépôts": "https://www.caissedesdepots.fr/nous-rejoindre/comment-nous-rejoindre/trouver-un-stage-ou-un-apprentissage",
    "Neuflize OBC": "https://www.neuflizeobc.fr/fr/contact/carriere.html",
    "Banque Delubac & Cie": "https://www.delubac.com/carrieres/offres-emploi/",
    "Banque Richelieu": "https://banquerichelieu.com/recrutements",
    "Milleis Banque Privée": "https://www.milleis.fr/relation-reinventee/recrutement.html",
    "Bourse Direct": "https://groupe.boursedirect.fr/recrutement",
    "Portzamparc": "https://group.bnpparibas/emploi-carriere/toutes-offres-emploi",
    "La Financière de l'Échiquier": "https://www.lfde.com/fr-fr/nous-connaitre/carrieres/",
    "Marex": "https://www.marex.com/careers/career-opportunities",
    "Kepler Cheuvreux": "https://keplercheuvreux.teamtailor.com/jobs",
    "TP ICAP": "https://tpicap.com/tpicap/careers",
    "Aurel BGC": "https://www.bgcg.com/careers/",
    "Tradition Paris": "https://www.tradition.com/careers/launching-your-career.aspx",
    "CACEIS": "https://jobs.caceis.com/pages/offre/listeoffre.aspx?lcid=1036",
    "Ofi Invest": "https://ofi-invest.com/fr/carriere/nos-offres",
    "Tikehau Capital": "https://tikehau-capital-career.talentview.io/jobs",
    "CFM": "https://jobs.cfm.com/go/Internship/9276655/",
    "DNCA": "https://www.dnca-investments.com/carrieres",
    "Candriam": "https://jobs.candriam.com/Pages/Offre/ListeOffre.aspx?LCID=2057",
    "Commerzbank": "https://jobs.commerzbank.com/index.php?ac=search_result",
    "Standard Chartered": "https://jobs.standardchartered.com/search/",
    "BNY": "https://eofe.fa.us2.oraclecloud.com/hcmUI/CandidateExperience/en/sites/BNY-Careers/jobs",
}
CAREER_LISTINGS = {
    "BlackRock": ("https://careers.blackrock.com/category/students-and-graduates-jobs/45831/9022304/1",
                  "careers.blackrock.com", "/job/"),
    "SMBC": ("https://careers.smbcgroup.com/search/?q=&sortColumn=referencedate&sortDirection=desc",
             "careers.smbcgroup.com", "/smbc/job/"),
    "Intesa Sanpaolo IMI CIB": ("https://jobs.intesasanpaolo.com/search/?q=IMI+CIB&sortColumn=referencedate&sortDirection=desc",
                              "jobs.intesasanpaolo.com", "/job/"),
    "Nomura": (
        "https://nomuracampus.tal.net/vx/lang-en-GB/mobile-0/appcentre-ext/brand-4/candidate/jobboard/vacancy/1/adv/",
        "nomuracampus.tal.net", "/vx/lang-en-GB/mobile-0/appcentre-1/brand-4/candidate/so/pm/1/pl/1/opp/"),
    "Fidelity International": (
        "https://fidelityinternational.tal.net/vx/lang-en-GB/mobile-0/brand-5/candidate/jobboard/vacancy/1/adv/",
        "fidelityinternational.tal.net", "/vx/lang-en-GB/mobile-0/brand-5/candidate/so/pm/1/pl/1/opp/"),
    "HSBC Continental Europe": ("https://apply.careers.hsbc.com/search/?q=stage&locationsearch=Paris",
                                 "apply.careers.hsbc.com", "/job/"),
    "La Française": ("https://recrutement.creditmutuel.fr/fr/nos_offres.html?socs=39|4962|1499|1497|4963|4965|5007|5008|1496&tc=3",
                     "recrutement.creditmutuel.fr", "/fr/offre.html"),
    "Crédit Agricole Titres": ("https://catitres.teamtailor.com/jobs",
                              "catitres.teamtailor.com", "/jobs/"),
    "Crédit Mutuel / CIC": ("https://recrutement.creditmutuel.fr/fr/nos_offres.html?offres=true&tc=3",
                            "recrutement.creditmutuel.fr", "/fr/offre.html"),
    "Marex": ("https://www.marex.com/careers/career-opportunities",
              "www.marex.com", "/careers/career-opportunities/"),
    "Kepler Cheuvreux": ("https://keplercheuvreux.teamtailor.com/jobs",
                        "keplercheuvreux.teamtailor.com", "/jobs/"),
    "CACEIS": ("https://jobs.caceis.com/pages/offre/listeoffre.aspx?lcid=1036",
               "jobs.caceis.com", "/offre-de-emploi/"),
    "CFM": ("https://jobs.cfm.com/go/Internship/9276655/", "jobs.cfm.com", "/job/"),
    "La Banque Postale": ("https://www.labanquepostale.com/candidats/offres-d-emploi/nos-offres-d-emploi.ct-1645.html",
                          "www.labanquepostale.com", "/candidats/offres-d-emploi/nos-offres-d-emploi.job-"),
    "Amundi · portail groupe": ("https://groupecreditagricole.jobs/fr/nos-offres/mot-cles/Amundi/",
                               "groupecreditagricole.jobs", "/fr/nos-offres-emploi/"),
    "Ofi Invest": ("https://ofiinvestassetmanagement.flatchr.io/fr/company/ofiinvestassetmanagement/",
                   "ofiinvestassetmanagement.flatchr.io", "/fr/company/ofiinvestassetmanagement/vacancy/"),
}
ODDO_ALTAYS_LISTING = "https://recrutement.altays-progiciels.com/oddo/en/recherche.html"
ORACLE_CAREER_BOARDS = {
    "Tradeweb": ("https://ecnf.fa.us2.oraclecloud.com", "CX", "Tradeweb"),
    "Edmond de Rothschild AM": ("https://evht.fa.ocs.oraclecloud.eu", "CX_2001", "Edmond de Rothschild AM"),
    "BNY": ("https://eofe.fa.us2.oraclecloud.com", "BNY-Careers", "BNY"),
    "Lazard Student Careers": (
        "https://icbpjb.fa.ocs.oraclecloud.com",
        "LazardStudentCareers",
        "Lazard",
    ),
    "Lazard Professional Careers": (
        "https://icbpjb.fa.ocs.oraclecloud.com",
        "LazardProfessionalCareers",
        "Lazard",
    ),
    "J.P. Morgan Careers": (
        "https://jpmc.fa.oraclecloud.com",
        "CX_1001",
        "J.P. Morgan",
    ),
    "Goldman Sachs Campus Careers": (
        "https://hdpc.fa.us2.oraclecloud.com",
        "CampusHiring",
        "Goldman Sachs",
    ),
    "Schroders Careers": (
        "https://ekbq.fa.em2.oraclecloud.com",
        "CX_2",
        "Schroders",
    ),
}
VIE_SEEDS = (
    (245487, "Junior Trader", "Blue Cube", "London", "2026-11-11", "janvier 2027"),
    (247265, "Market Analyst Western and Central Europe", "Euronext", "Milan", "2026-11-19", "janvier 2027"),
    (246859, "VIE Credit Risk Analyst", "Engie Global Markets", "Madrid", "2026-11-07", "décembre 2026"),
)
HUBS = ("paris", "london", "londres", "new york", "singapore", "singapour", "hong kong", "zurich", "zürich",
        "geneva", "genève", "amsterdam", "frankfurt", "francfort", "tokyo", "chicago", "dublin", "milan", "madrid", "luxembourg",
        "lisbon", "lisboa", "stockholm")
PARIS_AREA = ("paris", "la defense", "la défense", "puteaux", "courbevoie",
              "fontenay-sous-bois", "île-de-france", "ile-de-france")
_MARKET_ROLE = re.compile(
    r"\b(?:trading|trader|sales|structur\w*|derivat\w*|derive\w*|"
    r"fixed income|rates|forex|fx|quant\w*|equity|equities|bond\w*|"
    r"commodit\w*|markets?|finance de marches?|analyste des marches|marches? (?:financiers?|de capitaux|actions?|"
    r"obligataires?|monetaires?|des changes)|asset management|equity research|"
    r"credit desk|credit trading|credit derivatives|market risk|risques? de marches?|"
    r"salle des marches|dcm|ecm|alm|broker|broking|pricing|valuation|valorisation|negociat\w*|"
    r"portfolio management|portfolio manager|portfolio analytics|portfolio engineering|"
    r"portfolio construction|gestion de portefeuille\w*|gerant de portefeuille\w*|"
    r"multi.?gestion|obligataire\w*|gestions? (?:de )?(?:taux|actions|diversifiee|monetaire)|"
    r"fund manag(?:er|ement)|commercial.{0,20}clients institutionnels|"
    r"securities (?:lending|financ(?:e|ing))|prets?.?emprunts? (?:de )?titres|"
    r"market research|recherche de marche|execution|negociation|buy.side|"
    r"treasury sales|liquidity sales|stir|repo|repurchase|fx swaps?)\b", re.IGNORECASE,
)
_NON_MARKET_ROLE = re.compile(
    r"\b(?:private equity|capital investissement|venture capital|growth equity|"
    r"leveraged finance|project finance|financement de projet|investment banking|"
    r"corporate finance|finance d.entreprise|mergers? and acquisitions?|m\s*&\s*a|"
    r"transaction banking|transaction services|trade finance|irb|retail credit|credit retail|"
    r"risque de credit|(?:back|middle)[ -]?office(?:r)?s?|administrat\w*|accounting|comptabilit\w*|"
    r"corporate treasury|tresorerie d.entreprise|payment\w*|payments?|settlement|"
    r"kyc|compliance|conformit\w*|fund accounting|fund dealing|"
    r"(?:collateral|processing|operations|forex) officer|post.trade|post.marche|"
    r"reconciliation|rapprochement|issuers? servicing|securities (?:lending|financing) officer|"
    r"fund (?:controller|execution officer)|gestionnaire.{0,30}fixed income|"
    r"juriste|juridique|legal counsel|audit|controls? governance|expressions? of interest|talent pool|"
    r"(?:markets?|clearing|treasury|branch) operations|operations (?:analyst|intern|trainee|associate)|gestionnaire.{0,30}operations|"
    r"consumer financial services|retail banking|branch.{0,30}(?:trainee|banker)|"
    r"financial reporting|reporting financier|cont[r]?ole(?:ur)? de gestion|actifs (?:non cotes|prives)|dette privee|"
    r"immobilier\w*|real estate|property management)\b", re.IGNORECASE,
)
_MACRO_RESEARCH = re.compile(r"\b(?:recherche en macroeconomie|macroeconomic research)\b", re.I)
_CORPORATE_ROLE = re.compile(
    r"\b(?:financements? structures?|structured (?:export )?finance|credit corporate|"
    r"corporate credit|corporate lending|equity and debt advisory|debt advisory|acquisition finance)\b", re.I,
)
_MARKET_DESK = re.compile(
    r"\b(?:trading|trader|sales|market risk|risques? de marche|dcm|ecm|"
    r"debt capital markets|equity capital markets|securiti[sz]ation|titrisation)\b", re.I,
)
_lock = threading.Lock()
_history_lock = threading.Lock()
_cache: tuple[datetime, list["Opportunity"], list[str]] | None = None
_refresh_worker: threading.Thread | None = None
_hourly_worker: threading.Thread | None = None
_source_counts: dict[str, int] = {}
_source_checks: dict[str, dict] = {}
_last_attempt: datetime | None = None
_refresh_guard = threading.Lock()
_source_cache_lock = threading.RLock()
_source_job_cache: dict[str, dict] = {}
_source_job_cache_path: Path | None = None
_force_source_refresh = False
_refresh_previous_jobs: dict[str, "Opportunity"] = {}
_refresh_career_jobs: dict[str, "Opportunity"] = {}
_refresh_first_seen: dict[str, str] = {}
CACHE_REFRESH_SECONDS = 3600
# Career feeds are independent and I/O-bound. Twelve outer workers reduce
# queueing while keeping source-level concurrency explicitly bounded.
SOURCE_COLLECTION_WORKERS = 12
CACHE_PATH = Path(os.getenv("INTERNSHIPS_DATA_DIR", str((Path(__file__).resolve().parents[2] / "internships_project" / "data" if Path(__file__).resolve().parents[1].name == "Internships" else Path(__file__).resolve().parent / "data")))) / "internships_cache.json"
JOBTEASER_CACHE_PATH = CACHE_PATH.with_name("jobteaser_sitemap_cache.json")
CACHE_SECONDS = CACHE_REFRESH_SECONDS
PUBLIC_UPDATE_DELAY_SECONDS = 3 * 3600
JOBTEASER_CACHE_SECONDS = 24 * 3600
SOURCE_RETRY_BASE_SECONDS = 15 * 60
SOURCE_RETRY_MAX_SECONDS = 6 * 3600
SOURCE_CONNECTOR_VERSIONS = {
    "Société Générale Careers": 5, "BNP Paribas": 8, "BNP Paribas CIB": 5,
    "Amundi": 3, "Crédit Agricole CIB": 2, "Crédit Mutuel Arkéa": 2, "Covéa Finance": 2,
    "DNCA": 2, "BNP Paribas Asset Management": 8, "BNP Paribas VIE": 8,
    "BNP Paribas Graduate": 5,
    "ODDO BHF": 2, "La Banque Postale": 2,
    **{name: 6 for name in WORKDAY},
    **{name: 4 for name in GREENHOUSE.values()},
    **{name: 2 for name in LEVER.values()},
    **{name: 2 for name in SMARTRECRUITERS.values()},
    **{name: 5 for name in ORACLE_CAREER_BOARDS},
    "Banque de France": 2,
    "AXA": 2,
    "BBVA": 6,
    "ING": 6,
    "Optiver": 3,
    "JobTeaser · sitemap": 2,
    "HSBC Continental Europe": 3,
    "CFM": 2,
    "Santander CIB": 8,
}
JOBTEASER_INDEX = "https://assets-cf.jobteaser.com/sitemaps/sitemap.xml"
JOBTEASER_EMPLOYERS = {
    "bpifrance": "Bpifrance",
    "bnp-paribas-asset-management": "BNP Paribas Asset Management",
    "bnp-paribas-france": "BNP Paribas",
    "bnp-paribas": "BNP Paribas",
    "societe-generale": "Société Générale",
    "credit-agricole-cib": "Crédit Agricole CIB",
    "credit-mutuel-arkea": "Crédit Mutuel Arkéa",
    "natixis": "Natixis",
    "amundi": "Amundi",
    "caceis": "CACEIS",
    "oddo-bhf": "ODDO BHF",
    "marex": "Marex",
    "kepler-cheuvreux": "Kepler Cheuvreux",
    "hsbc-continental-europe": "HSBC Continental Europe",
    "deutsche-bank": "Deutsche Bank",
    "barclays": "Barclays",
    "euronext": "Euronext",
    "bred": "BRED",
    "la-banque-postale": "La Banque Postale",
    "rothschild-and-co": "Rothschild & Co",
    "lazard": "Lazard",
    "lazard-freres-gestion": "Lazard Frères Gestion",
    "tikehau-capital": "Tikehau Capital",
    "carmignac": "Carmignac",
    "sycomore-asset-management": "Sycomore Asset Management",
    "groupama-asset-management": "Groupama AM",
    "covea-finance": "Covéa Finance",
    "point72": "Point72",
    "flow-traders": "Flow Traders",
    "jane-street": "Jane Street",
    "optiver": "Optiver",
}
JOBTEASER_CITIES = {
    "la-defense": "La Défense", "paris": "Paris", "london": "London",
    "londres": "Londres", "frankfurt": "Frankfurt", "francfort": "Francfort",
    "new-york": "New York", "hong-kong": "Hong Kong", "singapore": "Singapore",
    "singapour": "Singapour", "geneve": "Genève", "geneva": "Geneva",
    "zurich": "Zurich", "amsterdam": "Amsterdam", "milan": "Milan",
    "madrid": "Madrid", "dublin": "Dublin", "luxembourg": "Luxembourg",
    "lisbonne": "Lisbonne", "lisbon": "Lisbon",
}

# Brand icons are requested from the employer's own site. If an icon is absent,
# the card keeps its initials; no third-party logo service receives the visit.
COMPANY_ICON_HOSTS = {
    "ostrum": "www.ostrum.com",
    "labanquepostaleam": "www.lbpam.com",
    'spglobalmarketintelligence': 'www.spglobal.com',
    'lseg': 'www.lseg.com',
    'mizuho': 'www.mizuhogroup.com',
    'tradeweb': 'www.tradeweb.com',
    'edmondderothschildam': 'www.edmond-de-rothschild.com',
    'xtxmarkets': 'www.xtxmarkets.com',
    'hudsonrivertrading': 'www.hudsonrivertrading.com',
    'marketaxess': 'www.marketaxess.com',
    'blackrock': 'careers.blackrock.com',
    'smbc': 'www.smbcgroup.com',
    'intesasanpaoloimicib': 'group.intesasanpaolo.com',
    'mirova': 'www.mirova.com',
    'cpram': 'cpram.com',
    'icedataservices': 'www.ice.com',
    'marketsecurities': 'www.market-securities.com',

    "nomura": "www.nomura.com",
    "rbccapitalmarkets": "jobs.rbc.com",
    "murex": "www.murex.com",
    "pimco": "www.pimco.com",
    "jumptrading": "www.jumptrading.com",
    "fiverings": "fiverings.com",
    "drw": "www.drw.com",
    "fidelityinternational": "careers.fidelityinternational.com",
    "factset": "www.factset.com",
    "capitalgroup": "www.capitalgroup.com",
    "mavensecurities": "www.mavensecurities.com",
    "squarepointcapital": "www.squarepoint-capital.com",
    "tpicap": "tpicap.com",
    "morganstanley": "www.morganstanley.com",
    "bankofamerica": "careers.bankofamerica.com",
    "bloomberg": "bloomberg.avature.net",
    "akunacapital": "akunacapital.com",
    "susquehanna": "sig.com",
    "aqrcapitalmanagement": "www.aqr.com",
    "21shares": "www.21shares.com",
    "axa": "www.axa.com",
    "bpcenatixisbred": "www.groupebpce.com",
    "businessfrance": "www.businessfrance.fr",
    "comgest": "www.comgest.com",
    "creditagricoletitres": "www.ca-titres.fr",
    "davinci": "www.davincitrading.com",
    "financeactive": "www.financeactive.com",
    "groupamaam": "www.groupama-am.com",
    "jobteaser": "www.jobteaser.com",
    "lafrancaise": "www.la-francaise.com",
    "natixisciblondon": "www.natixis.com",
    "ofiinvest": "www.ofi-invest.com",
    "santandercib": "www.santander.com",
    "tdsecurities": "www.tdsecurities.com",
    "wisdomtree": "www.wisdomtree.eu",
    "citi": "www.citigroup.com",
    "natwestmarkets": "www.natwest.com",
    "pictetassetmanagement": "www.pictet.com",
    "bbva": "www.bbva.com",
    "ing": "www.ing.com",
    "ubs": "www.ubs.com",
    "societegenerale": "www.societegenerale.com",
    "bnpparibas": "group.bnpparibas",
    "bnpparibasam": "www.bnpparibas-am.com",
    "creditagricolecib": "www.ca-cib.com",
    "amundi": "www.amundi.com",
    "caceis": "www.caceis.com",
    "natixis": "www.natixis.com",
    "bred": "www.bred.fr",
    "creditmutuelcic": "www.creditmutuel.fr",
    "cic": "www.cic.fr",
    "creditmutuelarkea": "www.arkea.com",
    "marex": "www.marex.com",
    "keplercheuvreux": "www.keplercheuvreux.com",
    "deutschebank": "www.db.com",
    "barclays": "home.barclays",
    "santander": "www.santander.com",
    "mufg": "www.mufg.jp",
    "euronext": "www.euronext.com",
    "rothschildandco": "www.rothschildandco.com",
    "lazard": "www.lazard.com",
    "point72": "www.point72.com",
    "janestreet": "www.janestreet.com",
    "optiver": "optiver.com",
    "imctrading": "www.imc.com",
    "flowtraders": "www.flowtraders.com",
    "amundiintermediation": "www.amundi.com",
    "natixiscibhongkong": "www.natixis.com",
    "rothschildco": "www.rothschildandco.com",
    "bpcevie": "www.groupebpce.com",
    "banquedefrance": "www.banque-france.fr",
    "bpifrance": "www.bpifrance.fr",
    "cfm": "www.cfm.com",
    "cibccapitalmarkets": "www.cibc.com",
    "coveafinance": "www.covea-finance.fr",
    "creditmutuelam": "www.creditmutuel-am.eu",
    "dnca": "www.dnca-investments.com",
    "gieaxa": "www.axa.com",
    "goldmansachs": "www.goldmansachs.com",
    "hsbccontinentaleurope": "www.hsbc.com",
    "candriam": "jobs.candriam.com",
    "commerzbank": "jobs.commerzbank.com",
    "standardchartered": "jobs.standardchartered.com",
    "bny": "www.bny.com",
    "jpmorgan": "www.jpmorgan.com",
    "labanquepostale": "www.labanquepostale.com",
    "ocbcglobalmarkets": "www.ocbc.com",
    "oddobhf": "www.oddo-bhf.com",
    "quberesearchtechnologies": "www.qube-rt.com",
    "schroders": "www.schroders.com",
    "siennainvestmentmanagers": "www.sienna-im.com",
    "statkraft": "www.statkraft.com",
    "sycomoreassetmanagement": "www.sycomore-am.com",
    "tikehaucapital": "www.tikehaucapital.com",
    "bluecube": "www.blockchain.com",
}
COMPANY_LOGO_DIR = Path(__file__).parent / "assets" / "company_logos"


@dataclass(frozen=True)
class Opportunity:
    title: str
    company: str
    location: str
    kind: str
    url: str
    published: str
    score: int
    start_period: str = ""
    family: str = ""
    deadline: str = ""
    checked_at: str = ""
    source: str = "Employeur"
    published_inferred: bool = False
    description: str = ""
    employment: str | None = None


def _normalized_offer_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or "").casefold())
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", normalized)).strip()


def _canonical_location(location: str) -> str:
    aliases = {"singapour": "singapore", "londres": "london",
               "francfort": "frankfurt", "geneve": "geneva"}
    display = _display_offer_location(location)
    normalized = location if display == "Non précisé" else display
    return " ".join(aliases.get(word, word) for word in _normalized_offer_text(normalized).split())


def _cached_detail(job: Opportunity) -> Opportunity | None:
    """Reuse a previously read description when its public offer metadata is unchanged."""
    previous = _refresh_previous_jobs.get(job.url)
    if not previous or not (previous.description or previous.start_period):
        return None
    same = (
        _canonical_title(job.title) == _canonical_title(previous.title)
        and _canonical_company(job.company) == _canonical_company(previous.company)
        and _normalized_offer_text(job.location) == _normalized_offer_text(previous.location)
        and job.kind == previous.kind
        and (not job.published or not previous.published or job.published == previous.published)
    )
    if not same:
        return None
    return replace(
        job,
        start_period=job.start_period or _recovered_start_period(previous),
        description=job.description or previous.description,
    )


@lru_cache(maxsize=128)
def _local_company_icon(host: str) -> str:
    # Bundled images avoid blocked hotlinks and any network work while rendering cards.
    for filename, mime in ((f"{host}.png", "image/png"), ("default.svg", "image/svg+xml")):
        try:
            payload = (COMPANY_LOGO_DIR / filename).read_bytes()
        except OSError:
            continue
        return f"data:{mime};base64," + base64.b64encode(payload).decode("ascii")
    return ""


def _company_icon(company: str) -> str:
    return _local_company_icon(COMPANY_ICON_HOSTS.get(_canonical_company(company), "default"))


def _plain_text(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", value or ""))).strip()


def _canonical_title(title: str) -> str:
    text = unicodedata.normalize("NFKD", title.casefold())
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = re.sub(r"^(?:(?:stage|internship|intern|v\.?i\.?e\.?)\s*[:\-–]\s*)+", "", text)
    text = re.sub(r"\s*\(v\.?i\.?e\.?\)\s*$", "", text)
    text = text.replace("marchs", "marches")
    return re.sub(r"\W+", "", text)


def _cross_source_title(title: str) -> str:
    """Normalize optional internship prefixes for direct-site/JobTeaser matching."""
    text = unicodedata.normalize("NFKD", title.casefold())
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = re.sub(r"^(?:(?:stage|stagiaire|internship|intern)\b\W*(?:\d+\s*(?:mois|months?)\b\W*)?)+", "", text)
    text = re.sub(r"\b(?:[hf]\W+[hf]|f\W+m\W+d|all genders)\b", "", text)
    text = re.sub(r"\b(?:et|and)\b", "", text)
    return re.sub(r"\W+", "", text)


def _jobteaser_duplicate(job: Opportunity, official: list[Opportunity]) -> bool:
    """Prefer a direct posting when a sitemap URL describes the same vacancy.

    JobTeaser slugs can name the parent group instead of the hiring affiliate.
    Keep that exception explicit: sharing a corporate group alone is not enough.
    """
    company = _canonical_company(job.company)
    # Older sitemap caches included the employer suffix in the vacancy title.
    parsed = _jobteaser_from_sitemap_url(job.url)
    title = _cross_source_title(parsed.title if parsed else job.title)
    for other in official:
        other_company = _canonical_company(other.company)
        affiliate = (company, other_company) == ("natixis", "mirova")
        if company != other_company and not affiliate:
            continue
        if job.kind != other.kind:
            continue
        if job.location and other.location:
            same_location = (
                _normalized_offer_text(job.location) == _normalized_offer_text(other.location)
                or (_is_paris(job.location) and _is_paris(other.location))
            )
            if not same_location:
                continue
        if job.start_period and other.start_period and start_month(job.start_period) != start_month(other.start_period):
            continue
        other_title = _cross_source_title(other.title)
        if affiliate:
            if title == other_title:
                return True
        elif SequenceMatcher(None, title, other_title).ratio() >= .9:
            return True
    return False


def _is_jobteaser(job: Opportunity) -> bool:
    # Exported/legacy snapshots can lose the source label; the URL still identifies the aggregator.
    return (job.source.casefold().startswith("jobteaser")
            or urlparse(job.url).hostname in {"jobteaser.com", "www.jobteaser.com"})


def _without_jobteaser_duplicates(jobs: list[Opportunity], *, official_history: dict[str, Opportunity] | None = None) -> list[Opportunity]:
    history = _refresh_career_jobs if official_history is None else official_history
    # Historical postings are matching evidence only. Never resurrect a withdrawn career offer.
    official = [job for job in jobs if not _is_jobteaser(job)] + list(history.values())
    # Most direct postings belong to a different employer or contract. Index
    # those dimensions once so fuzzy title matching only runs on plausible pairs.
    by_company_kind: dict[tuple[str, str], list[Opportunity]] = {}
    for job in official:
        by_company_kind.setdefault((_canonical_company(job.company), job.kind), []).append(job)

    def possible_matches(job: Opportunity) -> list[Opportunity]:
        company = _canonical_company(job.company)
        candidates = list(by_company_kind.get((company, job.kind), ()))
        # Explicit corporate-group exception used by _jobteaser_duplicate.
        if company == "natixis":
            candidates.extend(by_company_kind.get(("mirova", job.kind), ()))
        return candidates

    return [job for job in jobs if not _is_jobteaser(job)
            or not _jobteaser_duplicate(job, possible_matches(job))]


def _canonical_company(company: str) -> str:
    text = unicodedata.normalize("NFKD", company.casefold())
    text = "".join(char for char in text if not unicodedata.combining(char))
    compact = re.sub(r"\W+", "", text)
    for variants, canonical in (
        (("tpicap", "tullettprebon", "icap", "liquidnet", "louiscapitalmarkets"), "tpicap"),
        (("bnpparibasassetmanagement", "bnpparibasam"), "bnpparibasam"),
        (("bnpparibascib", "bnpparibas"), "bnpparibas"),
        (("societegenerale", "societegenerale4"), "societegenerale"),
        (("creditagricolecib", "cacib"), "creditagricolecib"),
        (("ostrumassetmanagement", "ostrumam", "ostrum"), "ostrum"),
        (("cprassetmanagement", "cpram"), "cpram"),
        (("amundiassetmanagement", "amundi"), "amundi"),
        (("bftinvestmentmanagers", "bftim"), "bftim"),
        (("natixiscib", "natixis"), "natixis"),
        (("oddobhf", "oddo"), "oddobhf"),
        (("creditmutuelassetmanagement", "creditmutuelam"), "creditmutuelam"),
        (("arkeaassetmanagement", "arkeaam"), "arkeaam"),
        (("aurelbgc", "aurelbgcsa"), "aurelbgc"),
        (("traditiontsaf", "tsafotc"), "tsaf"),
        (("rothschildcoassetmanagement", "rothschildandcoassetmanagement", "rothschildcoredburn", "redburn"), "rothschildandco"),
        (("lazardassetmanagement", "lazardfreresgestion"), "lazard"),
    ):
        if compact in variants:
            return canonical
    if compact.startswith("bnpparibasmissionhandicap"):
        return "bnpparibas"
    if compact.startswith("natixiscibfrance"):
        return "natixis"
    return compact


_MONTH = (r"janvier|février|fevrier|mars|avril|mai|juin|juillet|août|aout|septembre|"
          r"octobre|novembre|décembre|decembre|january|february|march|april|may|june|july|"
          r"august|september|october|november|december")
_PERIOD = (rf"(?:(?:entre\s+)?(?:{_MONTH})\s*(?:/|ou|et|à)\s*(?:{_MONTH})\s+\d{{4}}|"
           rf"20\d{{2}}[-/]\d{{2}}[-/]\d{{2}}|\d{{1,2}}[/.\-]\d{{1,2}}[/.\-]\d{{4}}|"
           rf"(?:\d{{1,2}}(?:er|st|nd|rd|th)?\s+)?(?:{_MONTH})\s+\d{{4}}|"
           rf"(?:{_MONTH})\s+\d{{1,2}}(?:st|nd|rd|th)?[,]?\s+\d{{4}})")
_START = re.compile(
    rf"\b(?:date de d[ée]but(?: (?:du |de )?(?:stage|contrat))?|d[ée]but (?:du |de )stage|"
    rf"date (?:pr[ée]vue de )?prise de (?:poste|fonction)|prise de (?:poste|fonction)|"
    rf"d[ée]marrage(?: du stage)?|[àa] pourvoir|[àa] partir (?:de|du|d['’])|dès|"
    rf"date d['’]entr[ée]e|start(?:ing)? date|starting (?:in|on|from)|starts (?:in|on)|beginning (?:in|on)|begins in|commence en)"
    rf"(?:\s+(?:souhait[ée]e?|pr[ée]vue?|pr[ée]visionnelle?))?\s*[:|\-–]*\s*"
    rf"(?:(?:le|en|au|pour|from|in|dès|[àa] partir (?:de|du)|of|[àa] pr[ée]voir)\s+)?"
    rf"(?P<period>{_PERIOD}|asap|dès que possible|imm[ée]diatement|immediate(?:ly)?)(?!\w)",
    re.IGNORECASE,
)
_MONTH_NAMES = ("janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
                "septembre", "octobre", "novembre", "décembre")
_MONTH_ALIASES = {
    "fevrier": 2, "aout": 8, "decembre": 12,
    **{name: index for index, name in enumerate(_MONTH_NAMES, 1)},
    **{name: index for index, name in enumerate((
        "january", "february", "march", "april", "may", "june", "july", "august",
        "september", "october", "november", "december"), 1)},
}


def _start_period(text: str) -> str:
    plain = _plain_text(text)
    for match in _START.finditer(plain):
        period = match.group("period")
        if re.fullmatch(r"asap|dès que possible|imm[ée]diatement|immediate(?:ly)?", period, re.I):
            return "Dès que possible"
        if start_month(period):
            return period
    # An explicitly labelled programme interval may share its year at the end.
    # Keep graduation years and unlabelled seasonal titles out of start dates.
    interval = re.search(
        rf"\bprogram(?:me)? dates\s*:\s*(\d{{1,2}})(?:st|nd|rd|th)?\s+({_MONTH})"
        rf"\s*[-–—]\s*(\d{{1,2}})(?:st|nd|rd|th)?\s+({_MONTH})\s+(20\d{{2}})\b",
        plain, re.I)
    if interval:
        try:
            first = date(int(interval[5]), _MONTH_ALIASES[interval[2].casefold()], int(interval[1]))
            last = date(int(interval[5]), _MONTH_ALIASES[interval[4].casefold()], int(interval[3]))
            if first <= last:
                return first.isoformat()
        except ValueError:
            pass
    return ""


def _title_period(title: str) -> str:
    """A month in an early-career title is an explicit advertised cohort period."""
    english = ("January", "February", "March", "April", "May", "June", "July",
               "August", "September", "October", "November", "December")
    abbreviations = {month[:3].casefold(): month for month in english}
    month_pattern = rf"(?:{_MONTH}|{'|'.join(abbreviations)})"
    interval = re.search(rf"\b({month_pattern})\.?\s*(?:to|[-–]|au)\s*({month_pattern})\.?\s+(20\d{{2}})\b",
                         title, re.IGNORECASE)
    if interval:
        first = abbreviations.get(interval[1].casefold(), interval[1])
        last = abbreviations.get(interval[2].casefold(), interval[2])
        year = int(interval[3]) - int(_MONTH_ALIASES[first.casefold()] > _MONTH_ALIASES[last.casefold()])
        return f"{first} {year}"
    match = re.search(rf"\b({month_pattern})\.?\s+(20\d{{2}})\b", title, re.IGNORECASE)
    return f"{abbreviations.get(match[1].casefold(), match[1])} {match[2]}" if match else ""


def _recovered_start_period(job: Opportunity) -> str:
    title_period = _title_period(job.title)
    old_title_month = re.search(rf"\b(?:{_MONTH})\s+\d{{4}}\b", job.title, re.IGNORECASE)
    if (title_period and old_title_month and job.start_period == old_title_month[0]
            and start_month(title_period) != start_month(job.start_period)):
        return title_period
    return job.start_period or _start_period(job.description) or title_period


def start_month(period: str) -> str:
    """Return a start month only when the advertised date is valid."""
    text = period.strip().casefold()
    date_match = re.search(r"\b(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{4})\b", text)
    if date_match:
        try:
            parsed = date(int(date_match.group(3)), int(date_match.group(2)), int(date_match.group(1)))
        except ValueError:
            return ""
        return parsed.isoformat()[:7]
    iso_match = re.search(r"\b(20\d{2})[-/](\d{2})(?:[-/](\d{2}))?\b", text)
    if iso_match:
        try:
            parsed = date(int(iso_match.group(1)), int(iso_match.group(2)), int(iso_match.group(3) or 1))
        except ValueError:
            return ""
        return parsed.isoformat()[:7]
    written_day = re.search(rf"\b(\d{{1,2}})(?:er|st|nd|rd|th)?\s+({_MONTH})\s+(20\d{{2}})\b", text)
    english_day = re.search(rf"\b({_MONTH})\s+(\d{{1,2}})(?:st|nd|rd|th)?[,]?\s+(20\d{{2}})\b", text)
    if written_day or english_day:
        match = written_day or english_day
        day, month = (match[1], match[2]) if written_day else (match[2], match[1])
        try:
            return date(int(match[3]), _MONTH_ALIASES[month], int(day)).isoformat()[:7]
        except ValueError:
            return ""
    month_match = re.search(rf"\b({_MONTH})\s+(20\d{{2}})\b", text)
    if month_match:
        return f"{month_match.group(2)}-{_MONTH_ALIASES[month_match.group(1)]:02d}"
    return ""


def _priority_start(job: Opportunity) -> bool:
    """Rank explicitly advertised April–September 2027 starts first."""
    return "2027-04" <= start_month(job.start_period) <= "2027-09"


def _publication_sort_value(published: str) -> int:
    """Sort unknown or impossible publication dates after valid dates."""
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", published):
        return 0
    try:
        return date.fromisoformat(published).toordinal()
    except ValueError:
        return 0


def _opportunity_relevance(job: Opportunity) -> float:
    """Combine role/location (50), target window (35), and start proximity (15)."""
    role = 50 * max(0, min(job.score, 115)) / 115
    window = 35 if _priority_start(job) else 0
    month = start_month(job.start_period)
    timing = 0
    if month:
        year, number = map(int, month.split("-"))
        distance = abs((year - 2027) * 12 + number - 4)
        timing = max(0, 15 - 2.5 * distance)
    return round(role + window + timing, 6)


def _opportunity_sort_key(job: Opportunity) -> tuple:
    published = _publication_sort_value(job.published)
    return (-_opportunity_relevance(job), -published, job.company.casefold(),
            job.title.casefold(), job.url.casefold())


def _recent_sort_key(job: Opportunity) -> tuple:
    published = _publication_sort_value(job.published)
    return (-published, -job.score, job.company.casefold(), job.title.casefold(), job.url.casefold())


def _offer_search_text(value: str) -> str:
    """Normalize search text while preserving letters from non-Latin alphabets."""
    text = unicodedata.normalize("NFKD", value.casefold())
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"[\W_]+", " ", text).strip()


def matching_opportunities(jobs: list[Opportunity], category: str = "Toutes", query: str = "",
                           family: str = "Tous métiers", earliest: str = "Toutes dates",
                           seen_urls: list[str] | None = None, tracking: dict | None = None,
                           only_new: bool = False, hide_dismissed: bool = True,
                           weekly: bool = False, today: date | None = None,
                           daily: bool = False, sort_by: str = "pertinence") -> list[Opportunity]:
    """Return the full filtered and stably sorted result set before pagination."""
    query_terms = _offer_search_text(query or "").split()
    today = today or datetime.now(timezone.utc).date()
    seen = set(seen_urls or [])
    dismissed = {url for url, entry in (tracking or {}).items()
                 if isinstance(entry, dict) and normalize_status(entry.get("status")) == "Écartée"}
    filtered = [job for job in jobs if (
        category == "Toutes" or
        (category == "Stages Paris" and job.kind == "Stage" and _is_paris(job.location)) or
        (category == "Stages International" and job.kind == "Stage" and _is_international_location(job.location)) or
        (category == "VIE" and job.kind == "VIE") or
        (category == "Graduate" and job.kind == "Graduate")
    ) and (family.startswith("Tous ") or job.family == family or (family == "Sales / Trading / Structuring" and job.family in {"Sales", "Trading / Structuring"}))
      and (earliest == "Toutes dates" or (start_month(job.start_period) and start_month(job.start_period) >= earliest))
      and all(term in _offer_search_text(f"{job.title} {job.company} {job.location}")
              for term in query_terms)
      and (not only_new or job.url not in seen)
      and (not hide_dismissed or job.url not in dismissed)
      and (not weekly or _published_this_week(job.published, today))
      and (not daily or job.published == today.isoformat())]
    return sorted(filtered, key=_recent_sort_key if sort_by == "recent" else _opportunity_sort_key)


def _is_paris(location: str) -> bool:
    text = _offer_search_text(location)
    return any(_offer_search_text(place) in text for place in PARIS_AREA + (
        "montrouge", "levallois-perret", "boulogne-billancourt", "saint-denis",
        "saint-quentin-en-yvelines", "issy-les-moulineaux",
    ))


def _is_international_location(location: str) -> bool:
    text = "".join(char for char in unicodedata.normalize("NFKD", location.casefold())
                   if not unicodedata.combining(char))
    region_text = _offer_search_text(location)
    french_regions = (
        "auvergne-rhone-alpes", "bourgogne-franche-comte", "bretagne", "centre-val de loire",
        "corse", "grand est", "hauts-de-france", "normandie", "nouvelle-aquitaine",
        "occitanie", "pays de la loire", "provence-alpes-cote d'azur", "ile-de-france",
        "île-de-france",
    )
    if (not text or _is_paris(location) or "france" in text or re.search(r"(?:,\s*fr|\bfrance)\s*$", text)
            or any(_offer_search_text(region) in region_text for region in french_regions)):
        return False
    return any(hub in text for hub in HUBS if hub != "paris") or bool(
        re.search(r"[,·]\s*[a-z][a-z .'-]{1,40}$", text)
    )


def _plausible_location(location: str) -> bool:
    if not location or len(location) > 120:
        return False
    return not bool(re.search(
        r"veuillez s[ée]lectionner|tout d[ée]selectionner|d[ée]tail de l.offre|description du poste|flux rss",
        location, re.IGNORECASE,
    ))


def _clean_job_location(location: str, title: str = "") -> str:
    """Recover only explicitly captured place text, including in old snapshots."""
    if not location.strip():
        return ""
    value = _plain_text(location)
    # Legacy whole-page matches sometimes began at <title>, before the real h1.
    if title and title.casefold() in value.casefold():
        value = value[value.casefold().rfind(title.casefold()) + len(title):]
    value = re.sub(r"^(?:(?:Apply(?: for this job)?|Postuler|Je postule)\b[\s:|–-]*)+", "", value.strip(), flags=re.I)
    value = re.split(r"\s*,\s*(?:Front Office|Back Office|Middle Office|Capital Markets|Marex Solutions|Full-Time|Part-Time)\b",
                     value, maxsplit=1, flags=re.I)[0]
    value = re.sub(r"\s*,\s*", ", ", value).strip(" ,|–-")
    if not _plausible_location(value):
        return ""
    if re.search(
        r"\b(?:careers?|career opportunities|apply|postuler|internship|full-time|front office)\b", value, re.I
    ):
        return "Non précisé"
    return location if value == _plain_text(location) else value


def _header_job_location(parts: list[str], title: str) -> str:
    """Read the workplace immediately after an offer heading, skipping its CTA."""
    for index, part in enumerate(parts):
        if part != title:
            continue
        for value in parts[index + 1:index + 4]:
            if re.fullmatch(r"Apply(?: for this job)?|Postuler|Je postule", value, re.I):
                continue
            value = re.split(r"\s+(?:Salary|Reference)\b", value, maxsplit=1, flags=re.I)[0]
            if not re.fullmatch(r"[\wÀ-ÿ ,.'’()/–-]+", value) or re.match(
                r"(?:Reference|Salary|Responsibilities|About|Description|Internship)\b", value, re.I
            ):
                break
            location = _clean_job_location(value, title)
            if location and location != "Non précisé":
                return location
            break
    return ""


def _market_relevant(title: str, company: str = "") -> bool:
    normalized = unicodedata.normalize("NFKD", title.casefold())
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    if _CORPORATE_ROLE.search(normalized) and not _MARKET_DESK.search(normalized):
        return False
    if re.search(r"\bmarketing\b", normalized) and not re.search(
        r"\b(?:sales|trading|trader|structur\w*|pricing)\b", normalized
    ):
        return False
    if _MARKET_ROLE.search(normalized) and not _NON_MARKET_ROLE.search(normalized):
        return True
    if company == "Comgest" and re.search(
        r"financial analyst\s*[-–]?\s*talent program|assistant\W+.{0,20}risk manager", normalized
    ):
        return True
    return False


def _junior_analyst(title: str) -> bool:
    return bool(re.search(
        r"\b(?:junior|jr)\b.{0,60}\banalyst(?:e)?\b|\banalyst(?:e)?\b.{0,60}\b(?:junior|jr)\b",
        " ".join(title.split()), re.I)) and not re.search(
            r"\b(?:senior|sr|lead|principal|vice president|director|directeur)\b", title, re.I)


def _market_candidate(title: str) -> bool:
    """A generic junior analyst needs its detail before deciding desk relevance."""
    normalized = unicodedata.normalize("NFKD", title.casefold())
    normalized = "".join(c for c in normalized if not unicodedata.combining(c))
    return _market_relevant(title) or bool(_MACRO_RESEARCH.search(normalized)) or (_junior_analyst(title)
        and not _NON_MARKET_ROLE.search(normalized) and not _CORPORATE_ROLE.search(normalized))


def _experienced_junior(context: str) -> bool:
    number = r"(?:[3-9]|\d{2,}|three|four|five|trois|quatre|cinq)"
    years = number + r"\s*(?:\+|[-–]\s*\d+)?\s*(?:years?|ans?)\b"
    experience = r"[^.!?;\n]{0,45}\b(?:experience|expérience)\b"
    return bool(re.search(
        r"\b(?:at least|minimum(?: of)?|requires?|must have|au moins|minimum de)\s+" + years + experience
        + r"|\b" + years + experience + r"\s+(?:is\s+)?(?:required|minimum|obligatoire)\b"
        + r"|\b(?:experience|expérience)\s+(?:de|of)\s+" + years + r"\s+(?:minimum|required|obligatoire)\b", context, re.I))


def _asset_management_sales_support(title: str, context: str) -> bool:
    if (re.fullmatch(r"Business Development Analyst\s*[-–]\s*U\.?S\.?\s+Institutional", title.strip(), re.I)
            and re.search(r"join our Institutional\s*&\s*Global Consultant Relations Team", context, re.I)
            and re.search(r"\b(?:investment|asset) management\b", context, re.I)):
        return True
    return bool(re.search(r"\b(?:client relationship|relationship (?:support|management)|client coverage)\b", title, re.I)
        and re.search(r"\b(?:asset management|investment management)\b", context, re.I)
        and re.search(r"\b(?:join|support)\w*\b.{0,100}\b(?:sales|distribution) (?:desk|team)\b", context, re.I))


def _market_relevant_with_context(title: str, context: str = "") -> bool:
    """Allow investment-team roles only when an official description confirms context."""
    normalized = unicodedata.normalize("NFKD", context.casefold())
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    normalized_title = unicodedata.normalize("NFKD", title.casefold())
    normalized_title = "".join(char for char in normalized_title if not unicodedata.combining(char))
    if _NON_MARKET_ROLE.search(normalized_title):
        return False
    if _CORPORATE_ROLE.search(normalized_title) and not _MARKET_DESK.search(normalized_title):
        return False
    if _MACRO_RESEARCH.search(normalized_title):
        return bool(re.search(r"global research|mouvements de marches|financial markets", normalized))
    # A job's own team can disqualify a generic title; merely collaborating
    # with Middle Office (or a group offering it) must not exclude a desk role.
    if re.search(
        r"(?:au sein (?:du|de la|de l['’])|rattache\w* (?:au|a la|a l['’])|"
        r"(?:integrer\w*|rejoind\w*) (?:notre|le|la|l['’])|(?:you will join|joining) (?:our|the))\s*"
        r"(?:(?:departement|direction|service|equipe|team|division)\s+(?:(?:de|du|des)\s+)?)?"
        r"(?:real estate fund management|middle[ -]?office|back[ -]?office|corporate finance|operations|fund accounting|custody|settlements)",
        normalized,
    ):
        return False
    if _market_relevant(title):
        return True
    if _asset_management_sales_support(title, context):
        return True
    if not re.search(r"\b(?:analyst\w*|gerant\w*|risk manag(?:er|ement)|investment|portfolio|tresor\w*)\b", normalized_title):
        return False
    company_analysis = "" if _junior_analyst(title) else r"financial analysis of companies|"
    confirmed = re.search(
        r"equity investment teams|analysts?\s*/\s*portfolio managers?|"
        + company_analysis +
        r"cash and executions? on (?:the )?different markets|cash.*executions?.{0,60}marches|"
        r"portfolio liquidity|liquidite des portefeuilles|classes d.actifs liquides|risque des portefeuilles|"
        r"market risk|risk management.*(?:markets?|portfolios?)|"
        r"credit analyst.{0,100}(?:issuer|bond|fixed income)|"
        r"analyste.{0,80}credit.{0,100}(?:obligat|obligation|bond)|"
        r"analyses? credit.{0,120}(?:emetteur|obligataire|obligations)",
        normalized,
    )
    if _junior_analyst(title) and not confirmed:
        return bool(re.search(
            r"global markets front office|(?:sales|trading|structuring|fixed income|equity research|quantitative research) (?:desk|team)|"
            r"(?:public|listed) (?:equities|markets)|gestion (?:actions|obligataire|taux)", normalized))
    return bool(confirmed)


def _excluded_employer(company: str) -> bool:
    """Only the user's explicit Palatine exclusion; no inferred affiliations."""
    normalized = unicodedata.normalize("NFKD", company.casefold())
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    return bool(re.search(r"\bpalatine\b", normalized))


def _family(title: str, context: str = "") -> str:
    if re.search(r"\banalytics\s*(?:&|and)\s*sales\b", title, re.I):
        return "Client Service / Financial Solutions"
    if _asset_management_sales_support(title, context):
        return "Sales"
    title = unicodedata.normalize("NFKD", title.casefold())
    title = "".join(char for char in title if not unicodedata.combining(char))
    if (re.search(r"\bsyndicat\w*.*portfolio management\b", title)
            and re.search(r"bond syndication|(?:loans and|debt capital markets|distribution of).*bonds", context, re.I)):
        return "Capital Markets"
    if re.search(
        r"\b(?:ecm|dcm)\b|equity capital markets|debt capital markets|"
        r"capital markets? origination|primary (?:bond|debt|equity|capital) markets?|"
        r"bond syndicat\w*|syndicat\w*.{0,35}(?:bond|obligat)|"
        r"(?:bond|obligat).{0,35}syndicat\w*|marche primaire",
        title,
    ):
        return "Capital Markets"
    if re.search(r"\bsales\b|\bsale\b|\bvente\w*\b|commercial client", title):
        return "Sales"
    if re.search(r"\btrading\b|\btrader\b|\btrade execution\b|\bstructur\w*\b|\bpricing\b|\bderivat\w*\b|\bfx\b|\brates\b", title):
        return "Trading / Structuring"
    if (re.search(r"\bmarkets (?:intern\w*|graduate\w*)\b", title)
            and re.search(r"\btrading\b", context, re.I)):
        return "Trading / Structuring"
    if re.search(
        r"asset management|portfolio|fund management|investment management|"
        r"gestion d.?actifs|gestion de portefeuille|gestions? (?:de )?(?:actions|taux|diversifiee|monetaire)|"
        r"asset allocation|fund manager",
        title,
    ):
        return "Asset Management"
    if any(term in title for term in ("quant", "research", "recherche", "analyst", "investment", "portfolio")):
        return "Quant / Research"
    return "Risk / Support"


def _kind(title: str, employment: str = "") -> str | None:
    text = f"{title} {employment}".casefold()
    if re.search(r"\b(?:apprenticeship|alternance)\b", text):
        return None
    summer = bool(re.search(r"\bsummer (?:analyst|associate)\b", title, re.I))
    junior = _junior_analyst(title) and not re.search(r"\b(?:intern(?:ship)?s?|stages?|stagiaires?|trainee|off[ -]cycle)\b", text, re.I)
    graduate = bool(re.search(
        r"\b(?:graduates?|new grads?|new analyst|analyst program(?:me)?|"
        r"international talent program(?:me)?|traineeprogramm)\b", text, re.I)
        or re.search(r"\bfull[ -]?time (?:analyst|associate)\b.{0,90}\b20\d{2}\b", title, re.I) or junior)
    if re.search(r"\b(?:cdi|cdd|permanent(?: contract)?)\b", employment, re.I) and (not graduate or summer):
        return None
    if re.search(r"\bv\.?i\.?e\b", text):
        return "VIE"
    if summer:
        return "Stage"
    if graduate:
        return "Graduate"
    if re.search(r"\b(?:intern(?:ship)?s?|stages?|stagiaires?|trainee|seasonal employee|"
                 r"off[ -]cycle|summer analyst|summer associate)\b", text):
        return "Stage"
    return None


def _morgan_stanley_kind(title: str, employment: str, description: str) -> str | None:
    """An Analyst title alone does not establish an early-career contract."""
    kind = _kind(title, employment)
    if kind in ("Stage", "VIE"):
        return kind
    if not kind and (not _morgan_stanley_sales_candidate(title)
            or not re.search(r"\banalyst\b", title, re.I)
            or re.search(r"\b(?:senior|sr|director|vice president|manager|head|lead|apprenticeship|alternance)\b",
                         title + " " + employment, re.I)):
        return None
    experience = list(re.finditer(
        r"\b(\d+)\s*(?:[-–—]\s*(\d+))?\s*(\+)?\s*years?\b"
        r"[^.!?;\n]{0,45}\bexperience\b", description, re.I))
    if (any(int(match[2] or match[1]) > 2 or match[3] for match in experience)
            or _experienced_junior(description)):
        return None
    if kind:
        return kind
    # The existing Graduate family also contains explicitly junior analysts.
    # Preserve the employer's title and employmentType, and recheck this evidence
    # when deduplicating/caching instead of fabricating a graduate contract.
    if experience or re.search(r"\b(?:entry[ -]level|recent graduates?|no (?:prior )?experience required)\b",
                               description, re.I):
        return "Graduate"
    return None


def _tp_icap_kind(title: str, employment: str = "", context: str = "") -> str | None:
    """Keep institutional brokerage early careers separate from group support roles."""
    if (not re.search(r"\b(?:sales|brokers?|broking)\b", title, re.I)
            or re.search(r"\b(?:senior|manager|director|head|retail|corporate|operations|support|gas|power)\b", title, re.I)
            or _experienced_junior(context)):
        return None
    if re.search(r"\b(?:junior|trainee)\s+broker\b|\bbroker\s+trainee\b", title, re.I):
        return "Graduate"
    return _kind(title, employment)


def _factset_client_solutions(title: str) -> bool:
    return bool(re.search(r"\bclient solutions\b", title, re.I)) and not re.search(
        r"\b(?:senior|sr|manager|director|head|lead|engineer)\b", title, re.I)


def _factset_kind(title: str, employment: str = "", context: str = "") -> str | None:
    if _experienced_junior(context):
        return None
    kind = _kind(title, employment)
    if kind:
        return kind
    if (_factset_client_solutions(title) and re.search(r"\bassociate\b", title, re.I)
            and re.search(r"\b(?:entry[ -]level|recent graduates?|"
                          r"6[ -]month long foundational training program)\b", context, re.I)):
        return "Graduate"
    return None


def _pimco_client_role(title: str) -> bool:
    return bool(re.search(r"\b(?:account (?:analyst|manager)|client management|"
                          r"(?:psg )?product (?:analyst|specialist|strategist))\b", title, re.I))


def _pimco_relevant(title: str, context: str = "", *, candidate: bool = False) -> bool:
    # These channels and operational programmes are outside institutional distribution.
    if (_NON_MARKET_ROLE.search(title) or re.search(
            r"\b(?:wealth|retail|private family|private strategies|operations|"
            r"trade support|software|technology|compliance|corporate)\b", title, re.I)):
        return False
    if _pimco_client_role(title):
        if not context:
            return candidate  # Listing only; the live description must confirm the role.
        return bool(re.search(r"\b(?:client relationships?|client servic\w*|client communication|"
                              r"product strategy|distribution)\b", context, re.I)
                    and re.search(r"\b(?:portfolio|investment strategies|financial markets?)\b", context, re.I))
    return _market_relevant_with_context(title, context)


def _murex_relevant(title: str, context: str = "", *, candidate: bool = False) -> bool:
    """Select client-facing markets solutions, not software or operations roles."""
    if (not re.search(r"\b(?:trading|fixed income|rates|fx|client solutions)\b", title, re.I)
            or re.search(r"\b(?:senior|sr|lead|head|manager|director|engineer|developer|"
                         r"operations|back office|retail|corporate)\b", title, re.I)):
        return False
    if not context:
        return candidate  # A listing is only a candidate until its live detail is read.
    return bool(not _experienced_junior(context)
        and re.search(r"\b(?:client support|client-facing|client solutions|client requirements|"
                      r"client.s requirements)\b", context, re.I)
        and re.search(r"\b(?:financial instruments|foreign exchange|fixed income|"
                      r"derivatives|swaps|bonds)\b", context, re.I))


def _rbc_relevant(title: str, context: str = "", *, candidate: bool = False) -> bool:
    """RBC campus markets desks, with live evidence for debt origination."""
    if (_NON_MARKET_ROLE.search(title) or re.search(
            r"\b(?:senior|sr|director|head|lead|vice president|retail|corporate|wealth|"
            r"operations|reporting|control|securitization|software|developer|quant|research)\b",
            title, re.I) or not re.search(
            r"\b(?:sales|trading|broker|rates|credit|fx|repo|dcm|debt capital markets|"
            r"origination|treasury solutions)\b", title, re.I)):
        return False
    if not context:
        return candidate
    if _experienced_junior(context):
        return False
    if re.search(r"\borigination\b", title, re.I):
        return bool(re.search(r"\b(?:fixed income origination|debt capital markets|"
                              r"debt transactions|bond syndication)\b", context, re.I))
    return bool(re.search(r"\b(?:fixed income|equities|equity products|foreign exchange|"
                          r"derivatives|currencies|institutional clients|repo)\b", context, re.I))


FINANCIAL_DATA_EMPLOYERS = frozenset({'S&P Global Market Intelligence','LSEG','Tradeweb','ICE Data Services','MarketAxess'})


def _opportunity(title: str, company: str, location: str, employment: str,
                 url: str, published: str, start_period: str = "",
                 role_context: str = "", *, defer_junior_context: bool = False) -> Opportunity | None:
    title = title.strip()
    location = _clean_job_location(location, title)
    kind = (_tp_icap_kind(title, employment, role_context) if company == "TP ICAP" else
            _factset_kind(title, employment, role_context) if company == "FactSet" or company in FINANCIAL_DATA_EMPLOYERS else
            _morgan_stanley_kind(title, employment, role_context)
            if company == "Morgan Stanley" else _kind(title, employment))
    market = (_rbc_relevant(title, role_context, candidate=defer_junior_context)
              if company == "RBC Capital Markets" else
              _murex_relevant(title, role_context, candidate=defer_junior_context)
              if company == "Murex" else
              _pimco_relevant(title, role_context, candidate=defer_junior_context)
              if company == "PIMCO" else _market_relevant_with_context(title, role_context))
    if (company == "FactSet" or company in FINANCIAL_DATA_EMPLOYERS) and _factset_client_solutions(title):
        market = True
        if defer_junior_context and not role_context and re.search(r"\bassociate\b", title, re.I):
            kind = kind or "Graduate"  # Candidate only; the live detail must confirm early careers.
    if company == 'S&P Global Market Intelligence' and not defer_junior_context:
        if not re.search(r'market intelligence',role_context,re.I):
            return None
    pending_junior = defer_junior_context and not role_context and _junior_analyst(title) and _market_candidate(title)
    if (not kind or not (market or pending_junior) or _excluded_employer(company) or not _plausible_location(location)
            or kind == "Graduate" and _junior_analyst(title) and _experienced_junior(role_context)):
        return None
    parsed = urlparse(url)
    if not is_trusted_offer_url(url):
        return None
    paris = _is_paris(location)
    market_focus = any(term in title.casefold() for term in (
        "trading", "trader", "sales", "structur", "fixed income", "rates", "fx", "derivative", "dérivé"
    ))
    score = (100 if paris and kind == "Stage" else 70 if paris else 45) + (15 if market_focus else 0)
    family = _family(title, role_context)
    if company == "PIMCO" and _pimco_client_role(title):
        family = "Asset Management" if re.search(r"\bproduct\b", title, re.I) else "Client Service / Financial Solutions"
    elif company == "Murex" or (company == "FactSet" or company in FINANCIAL_DATA_EMPLOYERS) and _factset_client_solutions(title):
        family = "Client Service / Financial Solutions"
    elif company == "RBC Capital Markets" and re.search(r"\borigination\b", title, re.I):
        family = "Capital Markets"
    return Opportunity(title, company, location, kind, url, published[:10], score, start_period,
                       family, "", datetime.now(timezone.utc).date().isoformat(), employment=employment)


def is_trusted_offer_url(url: str) -> bool:
    """Accept HTTPS job URLs only from career and provider hosts used by connectors."""
    allowed_hosts = {
        "jobs.smartrecruiters.com", "boards.greenhouse.io", "job-boards.greenhouse.io", "job-boards.eu.greenhouse.io",
        "jobs.lever.co", "jobs.eu.lever.co", "jobs.ashbyhq.com",
        "careers.societegenerale.com", "mon-vie-via.businessfrance.fr",
        "group.bnpparibas", "careers.cib.bnpparibas", "bnppapply.tal.net", "fidelityinternational.tal.net", "jobs.ca-cib.com", "recrutement.creditmutuel.fr",
        "jobs.amundi.com", "www.jobs.amundi.com", "recrutement.arkea.com",
        "career5.successfactors.eu",
        "www.recrutement.arkea.com",
        "www.marex.com", "keplercheuvreux.teamtailor.com", "catitres.teamtailor.com",
        "recrutement.bpce.fr", "jobs.caceis.com", "tikehau-capital-career.talentview.io", "jobs.cfm.com",
        "cm.comgest.com", "coveafinance-recrute.talent-soft.com",
        "www.labanquepostale.com", "icbpjb.fa.ocs.oraclecloud.com",
        "groupecreditagricole.jobs",
        "jpmc.fa.oraclecloud.com", "hdpc.fa.us2.oraclecloud.com", "ekbq.fa.em2.oraclecloud.com",
        "ofiinvestassetmanagement.flatchr.io", "recrutement.altays-progiciels.com",
        "www.groupama-gan-recrute.com", "bdf.wd103.myworkdayjobs.com",
        "recrutement.axa.fr",
        "www.dnca-investments.com", "jobs.ubs.com", "www.optiver.com",
        "jobs.candriam.com", "eofe.fa.us2.oraclecloud.com",
        "jobs.commerzbank.com", "jobs.standardchartered.com", "apply.careers.hsbc.com",
        "www.akunacapital.com", "akunacapital.com", "careers.sig.com",
        "careers.aqr.com", "bloomberg.avature.net", "careers.bankofamerica.com",
        "morganstanley.eightfold.ai", "morganstanley.tal.net", "nomuracampus.tal.net",
        *(board[0] for board in WORKDAY.values()),
        *(config[1] for config in CAREER_LISTINGS.values()),
        *(urlparse(board[0]).hostname for board in ORACLE_CAREER_BOARDS.values()),
        "www.hudsonrivertrading.com", "www.marketaxess.com",
        "careers.ice.com", "marketsecurities.bamboohr.com",
        "www.lbpam.com",
    }
    try:
        parsed = urlparse(url)
        port = parsed.port
    except (TypeError, ValueError):
        return False
    return (parsed.scheme == "https" and parsed.hostname in allowed_hosts and
            parsed.username is None and parsed.password is None and not port)


def _smart_jobs(slug: str, company: str) -> list[Opportunity]:
    url = f"https://api.smartrecruiters.com/v1/companies/{slug}/postings"
    jobs: list[Opportunity] = []
    offset = 0
    seen: set[str] = set()
    while True:
        response = requests.get(
            url, params={"limit": 100, "offset": offset, "destination": "PUBLIC"}, timeout=(8, 20)
        )
        response.raise_for_status()
        payload = response.json()
        rows = payload.get("content") or []
        identities = {str(item.get("id") or "") for item in rows}
        total = payload.get("totalFound")
        if rows and (not identities - seen or "" in identities):
            raise ValueError("Pagination SmartRecruiters sans progression")
        seen.update(identities)
        if not rows and isinstance(total, int) and len(seen) < total:
            raise ValueError("Catalogue SmartRecruiters incomplet")
        for item in rows:
            location = item.get("location") or {}
            employment = (item.get("typeOfEmployment") or {}).get("label", "")
            job = _opportunity(
                str(item.get("name") or ""), company,
                str(location.get("fullLocation") or location.get("city") or ""), employment,
                f"https://jobs.smartrecruiters.com/{slug}/{item.get('id', '')}",
                str(item.get("releasedDate") or ""),
            )
            if job:
                jobs.append(replace(job, source=f"SmartRecruiters Â· {company}"))
        if not rows or isinstance(total, int) and len(seen) >= total:
            break
        offset += len(rows)
    def enrich(job: Opportunity) -> Opportunity:
        reused = _cached_detail(job)
        if reused and reused.description:
            return replace(reused, source=job.source)
        try:
            detail = requests.get(
                f"{url}/{job.url.rsplit('/', 1)[-1]}", timeout=(8, 20)
            )
            detail.raise_for_status()
            sections = (detail.json().get("jobAd") or {}).get("sections") or {}
            body = " ".join(str(section.get("text") or "") for section in sections.values())
            return replace(job, start_period=_start_period(body) or _title_period(job.title),
                           description=_plain_text(body)[:12_000])
        except (requests.RequestException, ValueError, TypeError, AttributeError):
            return job
    # Keep every matching offer, but fetch full descriptions only for the most
    # relevant ones. Large boards can otherwise trigger hundreds of HTTP calls.
    selected = sorted(range(len(jobs)), key=lambda index: -jobs[index].score)[:50]
    with ThreadPoolExecutor(max_workers=4, thread_name_prefix="job-detail") as pool:
        enriched = dict(zip(selected, pool.map(enrich, (jobs[index] for index in selected))))
    return [enriched.get(index, job) for index, job in enumerate(jobs)]


def _greenhouse_jobs(slug: str, company: str) -> list[Opportunity]:
    url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"
    response = requests.get(url, params={"content": "true"}, timeout=(8, 20))
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict) or not isinstance(payload.get("jobs"), list):
        raise ValueError("Catalogue public Greenhouse invalide")
    # The public list endpoint is unpaginated. When supplied, total must account
    # for the complete response; a truncated catalogue is not an empty success.
    if "meta" in payload:
        meta = payload["meta"]
        if (not isinstance(meta, dict) or type(meta.get("total")) is not int
                or meta["total"] != len(payload["jobs"])):
            raise ValueError("Catalogue public Greenhouse incomplet")

    def calendar_date(value: object) -> str:
        try:
            return date.fromisoformat(str(value or "")[:10]).isoformat()
        except ValueError:
            return ""

    today = datetime.now(timezone.utc).date().isoformat()
    jobs: list[Opportunity] = []
    for item in payload["jobs"]:
        if not isinstance(item, dict):
            raise ValueError("Annonce publique Greenhouse invalide")
        if item.get("location") is not None and not isinstance(item["location"], dict):
            raise ValueError("Localisation publique Greenhouse invalide")
        # first_published is a posting date; updated_at is only a modification.
        published = calendar_date(item.get("first_published"))
        if published > today:
            published = ""
        deadline = calendar_date(item.get("application_deadline"))
        if deadline and deadline < today:
            continue
        description = _plain_text(html.unescape(str(item.get("content") or "")))
        title = str(item.get("title") or "").strip()
        employment = ""
        offer_url = str(item.get("absolute_url") or "")
        if slug in {"squarepointcapital", "drweng", "fiveringsllc", "jumptrading"}:
            identity = str(item.get("id") or "")
            location = item.get("location")
            if (not re.fullmatch(r"[1-9][0-9]*", identity) or not title or not description
                    or not isinstance(location, dict) or not str(location.get("name") or "").strip()):
                name = "Squarepoint" if slug == "squarepointcapital" else company
                raise ValueError(f"Annonce publique {name} incomplète")
            if slug == "squarepointcapital" and re.search(r"\b(?:infrastructure|desktop|platform|retail)\b", title, re.I):
                continue  # IT infrastructure and retail are outside desk roles.
            # Use the verified provider permalink for these employer sites,
            # rather than trusting an arbitrary URL supplied by a public row.
            offer_url = f"https://job-boards.greenhouse.io/{slug}/jobs/{identity}"
        if slug == "jumptrading":
            # The verified campus feed also contains AI and software roles.
            # A Campus full-time quantitative role explicitly targets new grads.
            if (not re.search(r"\b(?:quantitative (?:trader|researcher)|rates trading|trading assistant)\b", title, re.I)
                    or re.search(r"\b(?:senior|experienced|lead|manager|engineer|operations)\b", title, re.I)):
                continue
            if title.startswith("Campus ") and re.search(r"\(Full-Time\)$", title, re.I):
                employment = "Graduate"
        if slug == "fiveringsllc":
            if re.search(r"\b(?:experienced|lateral|software|operations|engineer)\b", title, re.I):
                continue
            # The official campus-hire title explicitly identifies new graduates;
            # retain that title and use the existing Graduate display category.
            if re.fullmatch(r"Campus Full Time 20\d{2} - Quantitative Trader(?: - .+)?", title, re.I):
                employment = "Graduate"
        if slug == "aqr":
            # AQR's summer BD programme also places interns in US Wealth.
            # Publish only the explicitly institutional, confirmed junior role.
            # The existing Graduate family also contains junior analyst jobs.
            if (not _asset_management_sales_support(title, description)
                    or not re.search(r"\b[01]\s*[-–]\s*2\s+years? of relevant post-undergraduate experience\b",
                                     description, re.I)
                    or _experienced_junior(description)):
                continue
            identity = str(item.get("id") or "")
            if not re.fullmatch(r"[1-9][0-9]*", identity):
                raise ValueError("Identifiant public AQR invalide")
            # The feed repeats gh_jid; a fixed employer URL avoids duplicates
            # and never follows an arbitrary URL supplied by a public row.
            offer_url = f"https://careers.aqr.com/jobs?gh_jid={identity}"
            employment = "Graduate"
        job = _opportunity(
            title, company,
            str((item.get("location") or {}).get("name") or "").strip(), employment,
            offer_url, published,
            _start_period(description) or _title_period(str(item.get("title") or "")),
            role_context=description,
        )
        if job:
            job = replace(job, description=description[:12_000], deadline=deadline)
            jobs.append(replace(job, source=f"Site carrière · Greenhouse · {company}"))
    return _deduplicate_opportunities(jobs) if slug in {"squarepointcapital", "drweng", "fiveringsllc", "jumptrading"} else jobs


def _optiver_jobs(_slug: str = "", _company: str = "") -> list[Opportunity]:
    """Read Optiver's replacement public catalogue, including all result pages."""
    candidates: dict[str, Opportunity] = {}
    seen: set[str] = set()
    search_failures = 0
    for offset in range(0, 1024, 16):
        try:
            for attempt in range(2):
                try:
                    response = requests.get("https://www.optiver.com/en/api/v1/jobs",
                                            params={"from": offset, "size": 16}, timeout=(8, 25))
                    break
                except (requests.Timeout, requests.ConnectionError):
                    if attempt:
                        raise
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
                raise ValueError("Catalogue public Optiver invalide")
            rows = payload["items"]
            total = int(payload["totalCount"])
            before = len(seen)
            for item in rows:
                url = urljoin("https://www.optiver.com", str(item.get("href") or ""))
                parsed = urlparse(url)
                if parsed.scheme != "https" or parsed.hostname != "www.optiver.com" or not parsed.path.startswith("/join-us/jobs/"):
                    continue
                seen.add(url)
                if item.get("experience") not in {"Graduate", "Internship"} and not _junior_analyst(str(item.get("title") or "")):
                    continue
                job = _opportunity(str(item.get("title") or ""), "Optiver", str(item.get("location") or ""),
                                   item["experience"], url, "", defer_junior_context=True)
                if job:
                    candidates[url] = replace(job, source="Site carrière · Optiver")
            if len(seen) >= total:
                break
            if len(seen) == before:
                raise ValueError("Pagination Optiver sans nouveaux résultats")
        except (requests.RequestException, ValueError, KeyError, TypeError):
            if not seen:
                raise
            search_failures += 1
            break
    else:
        search_failures += 1

    def enrich(job: Opportunity) -> Opportunity:
        reused = _cached_detail(job)
        if reused and reused.description:
            return reused
        try:
            detail = requests.get(job.url, timeout=(8, 20))
            detail.raise_for_status()
            structured = _jsonld_jobposting(detail.text)
            description = _plain_text(str(structured.get("description") or ""))
            return replace(job, description=description[:12_000],
                           start_period=_start_period(description) or _title_period(job.title),
                           published=_jsonld_job_posted(detail.text))
        except (requests.RequestException, ValueError, TypeError):
            return job  # The current official catalogue already confirms this vacancy.

    with ThreadPoolExecutor(max_workers=4, thread_name_prefix="optiver-detail") as pool:
        found = [job for job in pool.map(enrich, candidates.values()) if _eligible_offer(job)]
    if search_failures:
        raise _PartialSourceError(found, [], search_failures=search_failures)
    return found


def _lever_jobs(slug: str, company: str) -> list[Opportunity]:
    """Read the employer's published postings from Lever's public job-board API."""
    response = requests.get(
        f"https://api.lever.co/v0/postings/{slug}", params={"mode": "json"}, timeout=(8, 20)
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, list):
        raise ValueError("Réponse Lever invalide")
    jobs: list[Opportunity] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        categories = item.get("categories") or {}
        hosted_url = str(item.get("hostedUrl") or "")
        description = " ".join((
            str(item.get("descriptionPlain") or ""),
            str(item.get("additionalPlain") or ""),
        ))
        created_at = item.get("createdAt")
        published = ""
        if isinstance(created_at, (int, float)):
            try:
                published = datetime.fromtimestamp(created_at / 1000, timezone.utc).date().isoformat()
            except (OverflowError, OSError, ValueError):
                published = ""
        job = _opportunity(
            str(item.get("text") or ""), company,
            str(categories.get("location") or ""),
            str(categories.get("commitment") or ""), hosted_url, published,
            _start_period(description) or _title_period(str(item.get("text") or "")),
            role_context=_plain_text(description),
        )
        if job:
            job = replace(job, description=_plain_text(description)[:12_000])
            jobs.append(replace(job, source=f"Site carrière · Lever · {company}"))
    return jobs


def _ashby_jobs(slug: str, company: str) -> list[Opportunity]:
    """Read only publicly listed roles from Ashby's public job-board API."""
    response = requests.get(
        f"https://api.ashbyhq.com/posting-api/job-board/{slug}", timeout=(8, 20)
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict) or not isinstance(payload.get("jobs", []), list):
        raise ValueError("Réponse Ashby invalide")
    jobs: list[Opportunity] = []
    for item in payload.get("jobs", []):
        if not isinstance(item, dict) or item.get("isListed") is False:
            continue
        description = str(item.get("descriptionPlain") or "")
        job = _opportunity(
            str(item.get("title") or ""), company,
            str(item.get("location") or ""), str(item.get("employmentType") or ""),
            str(item.get("jobUrl") or ""), str(item.get("publishedAt") or ""),
            _start_period(description) or _title_period(str(item.get("title") or "")),
            role_context=_plain_text(description),
        )
        if job:
            job = replace(job, description=_plain_text(description)[:12_000])
            jobs.append(replace(job, source=f"Site carrière · Ashby · {company}"))
    return jobs


def _socgen_jobs(_slug: str = "", _company: str = "") -> list[Opportunity]:
    """Read Société Générale's global public offer index, not only its French feed."""
    listing_url = "https://careers.societegenerale.com/en/Technical/all-job-offers"
    response = requests.get(listing_url, timeout=(8, 25))
    response.raise_for_status()
    listing = _CareerHTML()
    listing.feed(response.text)
    candidates: dict[str, str] = {}
    for href, label in listing.links:
        url = urljoin(listing_url, href)
        parsed = urlparse(url)
        title = re.sub(r"\s+", " ", _plain_text(label)).strip()
        if (parsed.scheme == "https" and parsed.hostname == "careers.societegenerale.com"
                and parsed.path.startswith("/en/job-offers/") and _market_candidate(title)):
            candidates[url] = title
    if not candidates:
        raise ValueError("catalogue mondial Société Générale lisible, mais aucun lien marchés détecté")

    hub_pattern = "|".join(re.escape(hub) for hub in sorted(HUBS, key=len, reverse=True))

    def read_detail(item: tuple[str, str]) -> Opportunity | None:
        url, fallback_title = item
        try:
            detail = requests.get(url, timeout=(8, 20))
            detail.raise_for_status()
            page = _CareerHTML()
            page.feed(detail.text)
            text = " ".join(page.parts)
            title = next((heading for heading in page.headings if _market_relevant(heading)), fallback_title)
            location_match = re.search(
                rf"\b({hub_pattern})(?:\s*,\s*[^,]+){{0,2}}\s+(?=Salary\b|Reference\s+[A-Z0-9]+\b)",
                text, re.IGNORECASE,
            )
            location = location_match.group(0).strip() if location_match else ""
            if not location:
                marker = re.search(r"\b(?:Salary|Reference\s+[A-Z0-9]+)\b", text, re.IGNORECASE)
                before_marker = text[:marker.start()].strip() if marker else ""
                title_end = before_marker.rfind(title)
                if title_end >= 0:
                    before_marker = before_marker[title_end + len(title):].strip()
                generic_location = re.search(
                    r"([^,\n]{1,35}(?:,\s*[^,\n]{1,35}){1,2})\s*$", before_marker
                )
                location = generic_location.group(1).strip() if generic_location else ""
            publication_match = re.search(r"Publication date\s+(\d{4})/(\d{2})/(\d{2})", text, re.IGNORECASE)
            published = (f"{publication_match.group(1)}-{publication_match.group(2)}-{publication_match.group(3)}"
                         if publication_match else "")
            start_match = re.search(r"Start date\s+(\d{4})/(\d{2})/(\d{2})", text, re.IGNORECASE)
            start_period = (datetime.strptime(start_match.group(0).split()[-1], "%Y/%m/%d").strftime("%B %Y")
                            if start_match and start_month(start_match.group(0)) else "")
            structured = _jsonld_jobposting(detail.text)
            location = (_labelled_job_location(page.parts) or _structured_job_location(structured)
                        or _header_job_location(page.parts, title) or location)
            start_period = (start_period or _start_period(text) or _structured_job_start(structured)
                            or _start_period(str(structured.get("description") or "")) or _title_period(title))
            contract_match = re.search(
                r"\b(Internship|V\.I\.E\.|VIE|Graduate(?:\s+Programme|\s+Program)?|Trainee)\b",
                re.split(r"Responsibilities|Profile required|Business insight", text, maxsplit=1)[0], re.IGNORECASE,
            )
            employment = str(structured.get("employmentType") or (contract_match.group(1) if contract_match else ""))
            job = _opportunity(title, "Société Générale", location, employment, url, published,
                               start_period, role_context=text)
            if not job:
                return None
            return replace(job, source="Société Générale Careers", description=text[:12_000])
        except (requests.RequestException, ValueError, TypeError):
            return None

    with ThreadPoolExecutor(max_workers=6, thread_name_prefix="socgen-detail") as pool:
        return [job for job in pool.map(read_detail, candidates.items()) if job]


class _CareerHTML(HTMLParser):
    """Extract visible text, job headings and links from public career pages."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.headings: list[str] = []
        self.primary_headings: list[str] = []
        self.links: list[tuple[str, str]] = []
        self.events: list[tuple[str, str, str]] = []
        self._skip = 0
        self._heading: list[str] | None = None
        self._heading_tag: str | None = None
        self._anchor: tuple[str, list[str]] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"head", "script", "style", "nav", "footer"}:
            self._skip += 1
        if self._skip:
            return
        if re.fullmatch(r"h[1-6]", tag):
            self._heading = []
            self._heading_tag = tag
        elif tag == "a":
            href = dict(attrs).get("href")
            if href:
                self._anchor = (href, [])

    def handle_data(self, data: str) -> None:
        if self._skip or not data.strip():
            return
        self.parts.append(data.strip())
        if self._heading is not None:
            self._heading.append(data.strip())
        if self._anchor is not None:
            self._anchor[1].append(data.strip())

    def handle_endtag(self, tag: str) -> None:
        if tag in {"head", "script", "style", "nav", "footer"}:
            self._skip = max(0, self._skip - 1)
            return
        if self._skip:
            return
        if tag == self._heading_tag and self._heading is not None:
            heading = " ".join(self._heading)
            self.headings.append(heading)
            if tag == "h1":
                self.primary_headings.append(heading)
            self.events.append(("heading", "", heading))
            self._heading = None
            self._heading_tag = None
        elif tag == "a" and self._anchor is not None:
            href, parts = self._anchor
            label = " ".join(parts)
            self.links.append((href, label))
            self.events.append(("link", href, label))
            self._anchor = None


def _jsonld_jobposting(page_html: str) -> dict:
    """Return the first official JobPosting JSON-LD object, if present."""
    scripts = re.findall(
        r'<script\b[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        page_html, flags=re.IGNORECASE | re.DOTALL,
    )
    def find(node: object) -> dict:
        if isinstance(node, list):
            return next((value for item in node if (value := find(item))), {})
        if not isinstance(node, dict):
            return {}
        kinds = node.get("@type")
        if kinds == "JobPosting" or isinstance(kinds, list) and "JobPosting" in kinds:
            return node
        return find(node.get("@graph"))
    for raw in scripts:
        try:
            if posting := find(json.loads(raw)):
                return posting
        except (TypeError, ValueError):
            continue
    return {}


def _jsonld_job_posted(page_html: str) -> str:
    """Use only a JobPosting datePosted from the employer's structured page data."""
    today = datetime.now(timezone.utc).date()
    raw = str(_jsonld_jobposting(page_html).get("datePosted") or "")[:10]
    try:
        value = date.fromisoformat(raw)
        return value.isoformat() if value <= today else ""
    except ValueError:
        return ""


def _structured_job_location(posting: dict) -> str:
    """Read JobPosting workplaces, never the hiring organisation's address."""
    locations = posting.get("jobLocation") or []
    if not isinstance(locations, list):
        locations = [locations]
    places: list[str] = []
    for place in locations:
        if not isinstance(place, dict):
            continue
        address = place.get("address") or {}
        if isinstance(address, str):
            label = address.strip()
        elif isinstance(address, dict):
            country = address.get("addressCountry") or ""
            if isinstance(country, dict):
                country = country.get("name") or country.get("identifier") or ""
            fields = [address.get("addressLocality"), address.get("addressRegion"), country]
            label = ", ".join(dict.fromkeys(value.strip() for value in fields if isinstance(value, str) and value.strip()))
        else:
            label = ""
        if _plausible_location(label) and label not in places:
            places.append(label)
    return " / ".join(places)


def _labelled_job_location(parts: list[str]) -> str:
    """Keep field boundaries so a city is not mixed with the following heading."""
    labels = (r"(?:Ville|City|Lieu(?: de travail)?)", r"(?:Localisation(?: du poste)?|Locations?)")
    boundary = (r"Critères|Niveau|Référence|Date|Type de contrat|Contrat|Métier|"
                r"Zone géographique|Ville|Lieu|Localisation|Postuler|Je postule|"
                r"Description|Missions|Profil|Department|Employment|Salary|About|Apply")
    for label in labels:
        for index, part in enumerate(parts):
            match = re.match(rf"^{label}\b\s*[:|]*\s*(.*)$", part, re.I)
            if not match:
                continue
            value = match[1].strip()
            if not value and index + 1 < len(parts):
                value = parts[index + 1].strip()
            if _normalized_offer_text(value) in {"all", "any", "tous", "toutes", "select", "select all"}:
                continue
            value = re.split(rf"\b(?:{boundary})\b|\(Ce lien s'ouvre", value, maxsplit=1, flags=re.I)[0].strip(" |,:")
            if _plausible_location(value) and not re.search(r"https?://|[.!?;] |\b(?:recherche|recrute|sélectionner)\b", value, re.I):
                return value
    return ""


def _structured_job_start(posting: dict) -> str:
    raw = posting.get("jobStartDate")
    if isinstance(raw, str):
        # ISO timestamps belong to jobStartDate; datePosted/validThrough do not.
        candidate = raw.split("T", 1)[0].strip()
        if start_month(candidate):
            return candidate
    return "Dès que possible" if posting.get("jobImmediateStart") is True else ""


def _career_publication_date(raw: str) -> str:
    """Keep a career offer usable when its displayed publication date is invalid."""
    named = re.fullmatch(r"(\d{1,2})\s+([A-Za-zÀ-ÿ]{3,})\.?\s+(\d{4})", raw.strip())
    if named:
        months = {number for name, number in _MONTH_ALIASES.items()
                  if name.startswith(named[2].casefold())}
        if len(months) != 1:
            return ""
        raw = f"{named[1]}/{months.pop()}/{named[3]}"
    try:
        value = datetime.strptime(raw.replace(".", "/"), "%d/%m/%Y").date()
        return value.isoformat() if value <= datetime.now(timezone.utc).date() else ""
    except ValueError:
        return ""


def _talnet_fields(page_html: str) -> dict[str, str]:
    form = re.search(r'<form\b[^>]*class=["\'][^"\']*\bform-view\b[^"\']*["\'][^>]*>(.*?)</form>',
                     page_html, re.I | re.S)
    if not form:
        return {}
    sections = re.split(r'<span\b[^>]*class=["\']hform_lbl_text["\'][^>]*>\s*([^<]+?)\s*</span>',
                        form[1], flags=re.I)
    fields = {}
    for label, raw in zip(sections[1::2], sections[2::2]):
        field = _CareerHTML()
        field.feed(raw)
        fields[label.casefold()] = " ".join(field.parts).strip()
    return fields


def _nomura_detail(url: str, page_html: str, page: _CareerHTML,
                   fallback_title: str = "") -> Opportunity | None:
    """Read only this Tal.net vacancy's fields, never related vacancies or navigation."""
    text = " ".join(page.parts)
    if re.search(r"no longer (?:accepting applications|available)|(?:vacancy|opportunity) (?:is )?closed", text, re.I):
        return None
    if (fallback_title and page.primary_headings
            and _canonical_title(page.primary_headings[0]) != _canonical_title(fallback_title)):
        raise ValueError("Fiche Nomura sans annonce correspondante")
    fields = _talnet_fields(page_html)
    if not fields or not page.primary_headings:
        raise ValueError("Fiche Nomura incomplète")
    title = page.primary_headings[0]
    description = fields.get("job description", "")
    location = fields.get("location", "")
    programme = fields.get("program type", "")
    if not description or not _plausible_location(location) or not programme:
        raise ValueError("Fiche Nomura sans description, lieu ou contrat")
    identity = re.search(r"/opp/(\d+)-", url)
    apply_links = re.findall(r'<form\b[^>]*action=["\']([^"\']+)["\']', page_html, re.I)
    if not identity or not any(
            (parsed := urlparse(html.unescape(link))).scheme == "https"
            and parsed.hostname == "nomuracampus.tal.net"
            and parsed.path.endswith(f"/opp/{identity[1]}/apply/en-GB") for link in apply_links):
        raise ValueError("Fiche Nomura sans candidature ouverte vérifiable")
    deadline_match = re.search(r"Application Deadline:\s*(\d{2}/\d{2}/\d{4})", page_html, re.I)
    deadline = ""
    if deadline_match:
        try:
            deadline = datetime.strptime(deadline_match[1], "%d/%m/%Y").date().isoformat()
        except ValueError as exc:
            raise ValueError("Échéance Nomura invalide") from exc
        if date.fromisoformat(deadline) < datetime.now(timezone.utc).date():
            return None
    # This board also contains insight events, technology and support programmes.
    if (not re.search(r"internship|graduate|full.time|\bVIE\b", programme, re.I)
            or re.search(r"\b(?:senior|director|head|operations|fsops|digital office|quants?|strats?|technology|retail|corporate)\b", title, re.I)
            or not re.search(r"\b(?:sales|trading|structur\w*|global markets|rates|credit|dcm)\b", title, re.I)):
        return None
    # Some live descriptions advertise two cohorts then retain an older start
    # date in their body. Preserve the text without choosing a misleading date.
    start = "" if re.search(r"following (?:start )?dates", description, re.I) else _start_period(description)
    posting = _jsonld_jobposting(page_html)
    published = (_jsonld_job_posted(page_html) if posting.get("title")
        and _canonical_title(str(posting["title"])) == _canonical_title(title) else "")
    job = _opportunity(title, "Nomura", location, programme, url,
        published, start, role_context=description)
    family = ("Sales" if job and job.family == "Risk / Support"
        and re.search(r"(?:work with|join).{0,40}\b(?:structured |fixed income )?sales team\b", description, re.I)
        else job.family if job else "")
    return replace(job, kind='Stage' if re.search(r'internship',programme,re.I) else job.kind,
        description=description[:12_000], deadline=deadline, family=family,
        source="Site carrière · Nomura") if job else None


def _career_detail(url: str, company: str, fallback_title: str = "",
                   html_override: str | None = None) -> Opportunity | None:
    portal_company = company
    if html_override is None:
        response = requests.get(url, timeout=(8, 20))
        if company in {"Fidelity International", "Nomura"} and response.status_code in (404, 410):
            return None
        response.raise_for_status()
        page_html = response.text
    else:
        page_html = html_override
    page = _CareerHTML()
    page.feed(page_html)
    text = " ".join(page.parts)
    if company == "Nomura":
        return _nomura_detail(url, page_html, page, fallback_title)
    if company == "Fidelity International":
        # Tal.net's visible job fields are authoritative; navigation, unrelated
        # programmes and the programme year cannot supply missing offer data.
        if re.search(r"no longer (?:accepting applications|available)|(?:vacancy|opportunity) (?:is )?closed", text, re.I):
            return None
        labels = [part.casefold() for part in page.parts]
        if not page.primary_headings or "job description" not in labels or "programme" not in labels:
            raise ValueError("Fiche Fidelity incomplète")
        begin = labels.index("job description") + 1
        end = labels.index("programme", begin)
        description_parts = page.parts[begin:end]
        description = " ".join(description_parts)
        programme = page.parts[end + 1] if end + 1 < len(page.parts) else ""
        title = page.primary_headings[0]
        if re.search(r"\b(?:senior|sr|director|head|principal|lead)\b", title, re.I):
            return None
        location = _labelled_job_location(description_parts)
        if not location:
            # The actual offer heading explicitly names the programme's city.
            place = re.search(r"\s[-–]\s([^-–]+)$", title)
            location = place[1].strip() if place else ""
        if (not description or programme not in {"Internship", "Graduate", "MBA Internship", "Working Student"}
                or not _plausible_location(location)):
            raise ValueError("Fiche Fidelity incomplète")
        start = _start_period(description)
        if not start:
            explicit = re.search(rf"\binternship\b.{{0,100}}?\bfrom\s+(?:early\s+)?({_MONTH})\s+(20\d{{2}})", description, re.I)
            if explicit:
                start = f"{explicit[1]} {explicit[2]}"
        if not start:
            interval = re.search(rf"\bDuration\s*:\s*\d+\s+Months?\s*\(\s*({_MONTH})\s+to\s+({_MONTH})\s+(20\d{{2}})\s*\)", description, re.I)
            if interval:
                start = _title_period(f"{interval[1]} to {interval[2]} {interval[3]}")
        job = _opportunity(title, company, location, programme, url,
            _jsonld_job_posted(page_html), start, role_context=description)
        return replace(job, description=description[:12_000],
            source="Site carrière · Fidelity International") if job else None
    explicit_start = ""
    offer_text = text.split("Détail de l'offre", 1)[-1]
    if company == "BNP Paribas" and "cette offre est déjà pourvue" in text.casefold():
        return None
    if company == "Crédit Mutuel / CIC" and "CREDIT INDUSTRIEL ET COMMERCIAL" in text:
        company = "CIC"
    if portal_company in {"Crédit Mutuel / CIC", "La Française"} and "Crédit Mutuel Asset Management" in text:
        company = "Crédit Mutuel AM"
    if company == "Crédit Mutuel Arkéa":
        if "Arkéa Banque Entreprises" in offer_text or "ARKEA Banque Entreprises" in offer_text:
            company = "Arkéa Banque Entreprises et Institutionnels"
        elif "Federal Finance Gestion" in offer_text:
            company = "Federal Finance Gestion"
        elif "Arkéa Asset Management" in offer_text:
            company = "Arkéa AM"
    if company == "Amundi":
        for marker, employer in (("CPR Asset Management", "CPR AM"),
                                 ("BFT Investment Managers", "BFT IM"),
                                 ("Société Générale Gestion", "Société Générale Gestion"),
                                 ("Étoile Gestion", "Étoile Gestion"),
                                 ("Amundi Intermédiation", "Amundi Intermédiation")):
            if marker in text:
                company = employer
                break
    if company == "Ofi Invest":
        for marker, employer in (("Ofi Invest Intermediation Services", "Ofi Invest Intermediation Services"),
                                 ("Ofi Invest Asset Management", "Ofi Invest AM"),
                                 ("Ofi Invest Real Estate", "Ofi Invest Real Estate"),
                                 ("SWEN Capital Partners", "SWEN Capital Partners")):
            if marker.casefold() in text.casefold():
                company = employer
                break
    if company == "BPCE / Natixis / BRED" and "Banque Palatine" in text:
        return None
    if company == "BPCE / Natixis / BRED" and "Natixis CIB" in text:
        company = "Natixis CIB"
    if company == "BPCE / Natixis / BRED":
        for marker, employer in (("Banque Palatine", "Banque Palatine"),
                                 ("Ostrum Asset Management", "Ostrum Asset Management"),
                                 ("DNCA Finance", "DNCA"),
                                 ("BRED Banque Populaire", "BRED"),
                                 ("Natixis TradEx Solutions", "Natixis TradEx Solutions")):
            if marker in text:
                company = employer
                break
    if _excluded_employer(company):
        return None
    structured = _jsonld_jobposting(page_html)
    if portal_company == "Amundi · portail groupe":
        organization = structured.get("hiringOrganization") or {}
        if not isinstance(organization, dict) or _canonical_company(str(organization.get("name") or "")) != "amundi":
            return None
        company = "Amundi"
    structured_title = str(structured.get("title") or "").strip()
    if portal_company == "Candriam":
        fallback_title = re.sub(r"^\d{4}-\d+\s*[-–]\s*", "", fallback_title)
    # Related vacancies must never replace this posting's actual title.
    primary = next((heading for heading in page.primary_headings
                    if _normalized_offer_text(heading) not in {"career opportunities", "careers", "offres d emploi"}), "")
    title = structured_title or primary or fallback_title
    if not title:
        title = next((heading for heading in page.headings if _market_candidate(heading)), "")
    deadline = str(structured.get("validThrough") or "")[:10]
    try:
        if deadline and date.fromisoformat(deadline) < datetime.now(timezone.utc).date():
            return None
    except ValueError:
        deadline = ""
    if portal_company == "Candriam":
        title = next((heading for heading in page.headings if _canonical_title(heading) == _canonical_title(fallback_title)), fallback_title)
    if not _market_relevant_with_context(title, f'{text} {_plain_text(str(structured.get("description") or ""))}'):
        return None
    location = ""
    published = _jsonld_job_posted(page_html)
    if portal_company == "HSBC Continental Europe" and not published:
        # HSBC exposes the publication in a separate visible Date field, not JSON-LD.
        for index, part in enumerate(page.parts[:-1]):
            if part == "Date:":
                published = _career_publication_date(page.parts[index + 1])
                break
    employment = str(structured.get("employmentType") or "")
    if portal_company == "Candriam":
        contract = re.search(r"\b(?:Contract type|Type de contrat)\s*[:|]*\s*(Internship|Stage|VIE|Graduate|Permanent|Temporary|Alternance)\b", offer_text, re.I)
        employment = contract[1] if contract else employment
    location = _structured_job_location(structured)
    if company == "Marex":
        location = _header_job_location(page.parts, title) or location
    else:
        label = "Ville" if company in {"Crédit Agricole CIB", "CACEIS", "La Banque Postale"} else "Localisation"
        location_match = re.search(rf"\b{label}\s*(?:du poste)?\s*(?:\|\s*){{0,2}}(.+?)(?=\s+(?:Niveau|Référence|Date|Critères|Métier|Zone géographique|Postuler)\b)", offer_text, re.IGNORECASE)
        if location_match:
            location = location_match.group(1).strip(" |,")
        if portal_company == "Crédit Mutuel Arkéa":
            precise_location = re.search(r"\bLocalisation du poste\s+Lieu\s+(.+?)(?=\s+Critères candidat\b)", offer_text, re.IGNORECASE)
            if precise_location:
                location = precise_location.group(1).strip(" |,")
        if portal_company in {"Amundi", "Crédit Mutuel Arkéa"} and not location:
            place = re.search(r"\b(?:Localisation du poste|Zone géographique|Ville)\b(.{0,180})", offer_text, re.IGNORECASE)
            if place:
                location = next((hub for hub in HUBS if hub in place.group(1).casefold()), "")
        if company == "Crédit Agricole CIB":
            location_match = re.search(r"\bVille\s+([^|]+?)(?=\s+Critères candidat\b)", text, re.IGNORECASE)
            location = location_match.group(1).strip() if location_match else location
        published_match = re.search(r"(?:Date de publication|Date de parution|Date de mise à jour|Mise à jour le)\s*[:|]*\s*(\d{2}[/.]\d{2}[/.]\d{4})", text, re.IGNORECASE)
        if published_match and not published:
            published = _career_publication_date(published_match.group(1))
        contract_match = re.search(r"(?:Type de contrat|Contrat)\s*[:|]*\s*(?:\|\s*){0,2}(Stage|VIE|Graduate)", text, re.IGNORECASE)
        employment = contract_match.group(1) if contract_match else employment
        if company == "La Banque Postale":
            location_match = re.search(r"\bVille\s+(.+?)(?=\s+(?:Je postule|Introduction|Description de l'offre|Type de contrat)\b)", text, re.IGNORECASE)
            location = location_match.group(1).strip(" |,") if location_match else ""
            relative = re.search(r"\bIl y a\s+(\d+)\s+(jour|jours|semaine|semaines|mois)\b", text, re.IGNORECASE)
            if relative and not published:
                amount = int(relative.group(1))
                unit = relative.group(2).casefold()
                days = amount if unit.startswith("jour") else amount * 7 if unit.startswith("semaine") else amount * 30
                published = (datetime.now(timezone.utc).date() - timedelta(days=days)).isoformat()
        if urlparse(url).hostname == "ofiinvestassetmanagement.flatchr.io":
            location_match = re.search(rf"{re.escape(title)}\s+([A-Za-zÃ€-Ã¿' -]+?)\s+\d{{5}}\s+(?:Stage|CDI|CDD|Alternance)", text, re.IGNORECASE)
            if location_match:
                location = location_match.group(1).strip()
            contract_match = re.search(r"\b(Stage|VIE|Graduate|Alternance)\b", text, re.IGNORECASE)
            if contract_match:
                employment = contract_match.group(1)
            start_match = re.search(r"(?:Date de prise de fonction souhait.{0,3}e|Starting date)\s*:\s*(\d{2})/(\d{2})/(\d{4})", text, re.IGNORECASE)
            if start_match:
                explicit_start = datetime.strptime(start_match.group(0).split(":")[-1].strip(), "%d/%m/%Y").strftime("%B %Y")
        if urlparse(url).hostname == "coveafinance-recrute.talent-soft.com":
            location_match = re.search(r"Localisation du poste\s*[:|]*\s*(.+?)(?=\s+(?:Critères candidat|Référence|Date de début|Informations générales))", text, re.IGNORECASE)
            location = location_match.group(1).strip(" |,") if location_match else location
            contract_match = re.search(r"Type de contrat\s*[:|]*\s*(Stage|VIE|Graduate)", text, re.IGNORECASE)
            employment = contract_match.group(1) if contract_match else employment
            posted_match = re.search(r"Date de début de diffusion\s*[:|]*\s*(\d{2}/\d{2}/\d{4})", text, re.IGNORECASE)
            if posted_match and not published:
                published = _career_publication_date(posted_match.group(1))
    if company == "BNP Paribas" and not location:
        location_match = re.search(rf"{re.escape(title)}\s+Stage\s+Temps plein\s+(.+?)\s+Postuler", text)
        location = location_match.group(1) if location_match else ""
    if portal_company == "BNP Paribas" and urlparse(url).hostname == "group.bnpparibas":
        if not location:
            place = re.search(
                r"\b(?:Localisation|Location)\s*:?\s*(.+?)(?=\s+(?:Reference|Référence|Last update|Mise à jour|Date de)\b)",
                text, re.I)
            location = place.group(1).strip() if place else ""
        contract = re.search(
            r"\b(?:Job type|Type de contrat)\s*:?\s*(Fixed[ -]Term Contract|Permanent Contract|CDI|CDD|Graduate|Stage|Internship|VIE)\b",
            text, re.I)
        employment = contract.group(1) if contract else employment
        location = re.sub(r"\s*\(Ce lien s'ouvre dans un nouvel onglet\)\s*$", "", location).strip()
    if company == "BNP Paribas" and urlparse(url).hostname == "careers.cib.bnpparibas":
        location_match = re.search(r"\bLocation:\s*(.+?)(?=\s+(?:Job/mission:|Reference:|About the job))", text)
        location = location_match.group(1).strip() if location_match else ""
        contract_match = re.search(r"\bEmployment contract:\s*(Internship|Trainee|VIE|Graduate)", text, re.IGNORECASE)
        employment = contract_match.group(1) if contract_match else employment
    if company == "Kepler Cheuvreux":
        location_match = re.search(r"\bLocation:\s*([A-Za-zÀ-ÿ -]+?)(?=\s+(?:Salary|About|Département|Employment type))", text)
        location = location_match.group(1).strip() if location_match else ""
        if not location:
            location_match = re.search(r"-\s*(PARIS|NYON|LONDON|NEW YORK)\s*$", title, re.IGNORECASE)
            location = location_match.group(1) if location_match else ""
    if portal_company == "BPCE / Natixis / BRED":
        location_match = re.search(rf"{re.escape(title)}\s+(?:Stage|VIE|Graduate)\s+\S+\s+([^ ]+)", text)
        location = location_match.group(1) if location_match else location
    if company == "CACEIS":
        location_match = re.search(r"\bVille\s+(.+?)(?=\s+Critères candidat\b)", text, re.IGNORECASE)
        location = location_match.group(1).strip() if location_match else location
    if company == "Tikehau Capital":
        location = next((label for href, label in page.links
                         if urlparse(href).hostname in {"www.google.fr", "www.google.com", "maps.google.com"}
                         and any(hub in label.casefold() for hub in HUBS)), "")
        if not location:
            map_label = next((label for href, label in page.links
                              if urlparse(href).hostname in {"www.google.fr", "www.google.com", "maps.google.com"}), "")
            location = next((city.title() for city in HUBS if city in map_label.casefold()), "")
        contract_match = re.search(r"\b(Internship|VIE|Graduate|Trainee)\b", text, re.IGNORECASE)
        if contract_match:
            employment = contract_match.group(1)
        start_match = re.search(r"Starting on\s+(\d{2})/(\d{2})/(\d{4})", text, re.IGNORECASE)
        if start_match:
            explicit_start = datetime.strptime(start_match.group(0).split()[-1], "%d/%m/%Y").strftime("%B %Y")
        relative = re.search(r"Published\s+(\d+)\s+(seconds?|minutes?|hours?|days?|weeks?|months?)\s+ago", text, re.IGNORECASE)
        if relative:
            amount, unit = int(relative.group(1)), relative.group(2).casefold()
            days = 0 if unit.startswith(("second", "minute", "hour")) else amount if unit.startswith("day") else amount * 7 if unit.startswith("week") else amount * 30
            published = (datetime.now(timezone.utc).date() - timedelta(days=days)).isoformat()
        # Tikehau's private-wealth and private-equity sales are not public-markets roles.
        if "private wealth solutions" in text.casefold() or re.search(r"\bprivate equity\b", text, re.IGNORECASE):
            if not re.search(r"\b(?:listed|equity|rates|fx|trading|capital markets strategies)\b", text, re.IGNORECASE):
                return None
    if company == "ODDO BHF":
        for marker, employer in (("ODDO BHF Asset Management", "ODDO BHF AM"),
                                 ("ODDO BHF Equities", "ODDO BHF Equities"),
                                 ("ODDO BHF Fixed Income", "ODDO BHF Fixed Income")):
            if marker.casefold() in text.casefold():
                company = employer
                break
    if company == "CFM":
        location_match = re.search(rf"{re.escape(title)}\s+(.+?)\s+ABOUT CFM\b", text, re.IGNORECASE)
        location = location_match.group(1).strip() if location_match else location
    if portal_company == "BNP Paribas":
        if re.search(r"\bMirova\b", text, re.IGNORECASE):
            company = "Mirova"
        elif "BNP Paribas Asset Management" in text:
            company = "BNP Paribas Asset Management"
        elif "Portzamparc" in text:
            company = "Portzamparc"
    structured_description = _plain_text(str(structured.get("description") or ""))
    full_description = offer_text if len(offer_text) >= len(structured_description) else structured_description
    role_context = f"{offer_text} {structured_description}"
    location = (_labelled_job_location(page.parts) or _structured_job_location(structured)
                or location)
    job = _opportunity(title, company, location, employment, url, published,
                       explicit_start or _start_period(offer_text) or _structured_job_start(structured)
                       or _start_period(structured_description) or _title_period(title), role_context=role_context)
    return replace(job, source=f"Site carrière · {urlparse(url).hostname}", deadline=deadline,
                   description=full_description[:12_000]) if job else None


def _render_public_career_page(url: str, link_selector: str) -> str:
    """Render a public careers page when its listings are JavaScript-only."""
    try:
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise ValueError("Playwright requis pour lire la liste publique rendue en JavaScript") from exc
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                headless=not (os.getenv("GITHUB_ACTIONS") == "true" and os.getenv("DISPLAY")))
            try:
                page = browser.new_page()
                response = page.goto(url, wait_until="domcontentloaded", timeout=20_000)
                if response is not None and response.status >= 400:
                    raise ValueError(f"page carrière publique en HTTP {response.status}")
                try:
                    page.locator(link_selector).first.wait_for(timeout=8_000)
                except PlaywrightTimeoutError:
                    pass
                return page.content()
            finally:
                browser.close()
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError(f"navigateur public indisponible ({type(exc).__name__})") from exc


class _RequestPacer:
    """Space request starts across the collectors that share a provider."""

    def __init__(self, interval: float):
        self.interval = interval
        self.next_start = 0.0
        self.lock = threading.Lock()
        self.ready = threading.Event()

    def wait(self) -> None:
        with self.lock:
            delay = self.next_start - time.monotonic()
            if delay > 0:
                self.ready.wait(delay)
            self.next_start = time.monotonic() + self.interval


_bnp_group_pacer = _RequestPacer(0.5)


def _bnp_group_jobs(company: str, listing_url: str) -> list[Opportunity]:
    """Read BNP's public listings without opening windows on the user's desktop."""
    if os.name == 'nt':
        from .background_desktop import collect_bnp
        return [Opportunity(**row) for row in collect_bnp(company, listing_url)]
    virtual_display = bool(os.getenv("GITHUB_ACTIONS") == "true" and os.getenv("DISPLAY"))
    return _bnp_group_jobs_browser(company, listing_url, headless=not virtual_display)


def _bnp_graduate_jobs(_slug: str = "", _company: str = "") -> list[Opportunity]:
    """BNP also files desk graduate programmes under fixed-term contracts."""
    found: dict[str, Opportunity] = {}
    failures = 0
    failure_reasons: list[str] = []
    catalogues = ("graduate-programme-cdi", "cdd", "je-recherche-mon-premier-emploi")
    for contract in catalogues:
        listing = "https://group.bnpparibas/emploi-carriere/toutes-offres-emploi/" + contract
        try:
            result = _bnp_group_jobs("BNP Paribas", listing)
        except _PartialSourceError as exc:
            result = exc.jobs
            failures += 1
            failure_reasons.append(f"{contract}: {exc}")
        except (requests.RequestException, ValueError) as exc:
            failures += 1
            reason = str(exc) if isinstance(exc, ValueError) else type(exc).__name__
            failure_reasons.append(f"{contract}: {reason}")
            continue
        found.update((job.url, job) for job in result if job.kind == "Graduate")
    if failures == len(catalogues) and not found:
        raise ValueError("Catalogues Graduate et Junior BNP indisponibles · " + failure_reasons[0])
    if failures:
        failure = _PartialSourceError(list(found.values()), [], search_failures=failures)
        failure.args = (str(failure) + "; " + "; ".join(failure_reasons),)
        raise failure
    return list(found.values())


def _bnp_group_jobs_browser(company: str, listing_url: str, *, headless: bool = True) -> list[Opportunity]:
    try:
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise ValueError("Playwright requis pour lire les offres publiques BNP Paribas") from exc

    host = "group.bnpparibas"
    path_prefixes = ("/emploi-carriere/offre-emploi/", "/en/careers/job-offer/")
    failed_urls: list[str] = []
    candidates: dict[str, str] = {}
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=headless)
            try:
                page = browser.new_page()
                _bnp_group_pacer.wait()
                response = page.goto(listing_url, wait_until="domcontentloaded", timeout=20_000)
                if response is not None and response.status >= 400:
                    raise ValueError(f"liste BNP en HTTP {response.status}; aucun contournement tenté")
                try:
                    page.locator(','.join(f'a[href*="{prefix}"]' for prefix in path_prefixes)).first.wait_for(timeout=8_000)
                except PlaywrightTimeoutError:
                    pass

                direct_links = 0
                listing_failures = 0
                listing_failure_reason = ""
                visited = {listing_url}
                # Follow the public pagination links; the AJAX button can be
                # covered by a consent banner or finish after a fixed wait.
                for _ in range(200):
                    listing_page = _CareerHTML()
                    listing_page.feed(page.content())
                    for href, label in listing_page.links:
                        offer_url = urljoin(listing_url, href)
                        parsed = urlparse(offer_url)
                        if (parsed.scheme == "https" and parsed.hostname == host
                                and parsed.path.startswith(path_prefixes)):
                            direct_links += 1
                            if _market_candidate(label):
                                candidates[offer_url] = label
                    # Pagination is inside <nav>, excluded by the offer parser.
                    anchors = page.locator("a").evaluate_all(
                        "els => els.map(a => ({href:a.href,label:(a.textContent.trim() || a.getAttribute('aria-label') || ''),disabled:a.getAttribute('aria-disabled') === 'true' || !!a.closest('.disabled, [disabled]')}))")
                    next_url = next((a["href"] for a in anchors
                        if re.fullmatch(r"(?:suivant|next)(?:\s*[›»→])?", a["label"], re.I)
                        and not a.get('disabled')
                        and urlparse(a["href"]).scheme == "https"
                        and urlparse(a["href"]).hostname == host
                        and urlparse(a["href"]).path == urlparse(listing_url).path), "")
                    if not next_url:
                        break
                    if next_url in visited:
                        listing_failures += 1
                        listing_failure_reason = "pagination répétée"
                        break
                    visited.add(next_url)
                    try:
                        _bnp_group_pacer.wait()
                        response = page.goto(next_url, wait_until="domcontentloaded", timeout=20_000)
                        if response is not None and response.status >= 400:
                            raise ValueError(f"pagination BNP HTTP {response.status}")
                    except (PlaywrightTimeoutError, ValueError) as exc:
                        listing_failures += 1
                        listing_failure_reason = "délai de pagination dépassé" if isinstance(exc,PlaywrightTimeoutError) else str(exc)
                        break
                else:
                    listing_failures += 1
                    listing_failure_reason = "limite de 200 pages atteinte"

                detail_company = "BNP Paribas" if company == "BNP Paribas Asset Management" else company
                jobs: list[Opportunity] = []
                failed_statuses: set[int] = set()
                for offer_url, label in candidates.items():
                    try:
                        for attempt in range(2):
                            try:
                                _bnp_group_pacer.wait()
                                detail_response = page.goto(offer_url, wait_until="domcontentloaded", timeout=15_000)
                                if detail_response is not None and detail_response.status in (500,502,503,504) and attempt == 0:
                                    continue
                                break
                            except PlaywrightTimeoutError:
                                if attempt: raise
                        if detail_response is not None and detail_response.status in (404,410):
                            continue  # An expired advert must not retain an old cached offer.
                        if detail_response is not None and detail_response.status >= 400:
                            failed_statuses.add(detail_response.status)
                            failed_urls.append(offer_url)
                            continue
                        job = _career_detail(offer_url, detail_company, label, html_override=page.content())
                        if job and company == "BNP Paribas Asset Management" and job.company == "BNP Paribas":
                            job = replace(job, company="BNP Paribas Asset Management")
                        if job:
                            jobs.append(job)
                    except (PlaywrightTimeoutError, ValueError, TypeError):
                        failed_urls.append(offer_url)
                if listing_failures or failed_urls:
                    failure = _PartialSourceError(jobs, failed_urls, search_failures=listing_failures)
                    reasons = [listing_failure_reason] if listing_failure_reason else []
                    if failed_statuses:
                        reasons.append("fiches BNP HTTP " + ", ".join(map(str, sorted(failed_statuses))))
                    if reasons:
                        failure.args = (str(failure) + "; " + "; ".join(reasons),)
                    raise failure
                if jobs:
                    return list({job.url: job for job in jobs}.values())
                if direct_links:
                    return []  # Readable offers outside the filters are a successful empty collection.
                if os.getenv("GITHUB_ACTIONS") == "true":
                    print("BNP browser diagnostic: " + json.dumps({
                        "listing": listing_url, "final": page.url, "title": page.title(),
                        "links": len(listing_page.links),
                        "job_links": [href for href, _ in listing_page.links
                                      if "/offre-emploi/" in href or "/job-offer/" in href][:3],
                    }, ensure_ascii=True), flush=True)
                raise ValueError("aucun lien direct visible dans la liste BNP rendue")
            finally:
                browser.close()
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError(f"navigateur public BNP indisponible ({type(exc).__name__})") from exc


def _oddo_jobs() -> list[Opportunity]:
    """Read ODDO BHF's public Altays listing and parse official offer PDFs."""
    listing = _CareerHTML()
    try:
        response = requests.get(ODDO_ALTAYS_LISTING, timeout=(8, 25))
        response.raise_for_status()
        listing.feed(response.text)
    except requests.RequestException:
        # The legacy search shell may fail while the current results stay live.
        pass
    pdf_links: dict[str, str] = {}
    for href, label in listing.links:
        url = urljoin(ODDO_ALTAYS_LISTING, href)
        parsed = urlparse(url)
        if (parsed.scheme == "https" and parsed.hostname == "recrutement.altays-progiciels.com"
                and parsed.path.startswith("/oddo/") and parsed.path.casefold().endswith(".pdf")):
            pdf_links[url] = label
    if not pdf_links:
        # Altays loads paginated HTML cards through this public endpoint. Error
        # banners in the search shell are hidden templates, not source failures.
        seen: set[str] = set()
        for number in range(1, 51):
            result = requests.get(
                "https://recrutement.altays-progiciels.com/oddo/fr/offres.html",
                params={"page": number}, timeout=(8, 25))
            result.raise_for_status()
            cards = _CareerHTML()
            cards.feed(result.text)
            links = {}
            for href, label in cards.links:
                parsed = urlparse(urljoin(ODDO_ALTAYS_LISTING, href))
                if (parsed.scheme == "https" and parsed.hostname == "recrutement.altays-progiciels.com"
                        and parsed.path.startswith("/oddo/fr/offres/") and parsed.path.endswith(".html")):
                    links[parsed._replace(query="", fragment="").geturl()] = label
            if not links:
                if result.text.strip() and not seen:
                    raise ValueError("réponse Altays sans liste d'offres reconnue")
                break
            if not set(links) - seen:
                raise ValueError("pagination Altays répétée")
            seen.update(links)
            for url, label in links.items():
                if _market_relevant(label):
                    # Each official HTML detail exposes its equivalent PDF.
                    pdf_links[url.removesuffix(".html") + ".pdf"] = label
        else:
            raise ValueError("pagination Altays incomplète après 50 pages")
        if not pdf_links:
            return []
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise ValueError("pypdf nécessaire pour lire les fiches PDF publiques ODDO BHF") from exc
    jobs: list[Opportunity] = []

    def read_offer(item: tuple[str, str]) -> tuple[str, str, str]:
        url, fallback_title = item
        try:
            offer = requests.get(url, timeout=(8, 25))
            offer.raise_for_status()
            description = " ".join((pdf_page.extract_text() or "")
                                   for pdf_page in PdfReader(BytesIO(offer.content)).pages)
            return url, fallback_title, description
        except Exception:
            return url, fallback_title, ""

    offer_links = list(pdf_links.items())
    with ThreadPoolExecutor(max_workers=6, thread_name_prefix="oddo-detail") as pool:
        offer_details = list(pool.map(read_offer, offer_links))
    detail_failures = sum(not description for _, _, description in offer_details)
    for url, fallback_title, description in offer_details:
        if not description:
            continue
        title = re.sub(r"\s+", " ", fallback_title).strip()
        title = re.sub(r"\s*(?:Postuler|Apply)\s*$", "", title, flags=re.IGNORECASE)
        if not _market_relevant(title):
            title = next((line.strip() for line in description.splitlines() if _market_relevant(line)), title)
        location_match = re.search(r"(?:Localisation|Location)\s*:\s*(.+?)(?=\s+(?:\d{5}|Type de contrat|Contract type|Date de|First publication date)\b|$)", description, re.IGNORECASE)
        contract_match = re.search(r"(?:Type de contrat|Contract type)\s*:\s*(Stage|Internship|VIE|Graduate)", description, re.IGNORECASE)
        posted_match = re.search(r"(?:Date.{0,35}publication|First publication date)\s*:\s*(\d{2}/\d{2}/\d{4})", description, re.IGNORECASE)
        employment = contract_match.group(1) if contract_match else ""
        published = _career_publication_date(posted_match.group(1)) if posted_match else ""
        job = _opportunity(title, "ODDO BHF", location_match.group(1).strip() if location_match else "",
                           employment, url, published, _start_period(description) or _title_period(title), description)
        if job:
            jobs.append(replace(job, source="Site carrière · ODDO BHF Altays", description=description[:12_000]))
    if not jobs and detail_failures == min(len(pdf_links), 60):
        raise ValueError("les liens PDF ODDO sont exposés, mais aucune fiche n'a pu être chargée")
    if detail_failures:
        raise _PartialSourceError(jobs, [url for url, _, text in offer_details if not text])
    return jobs


def _tikehau_jobs() -> list[Opportunity]:
    """Read Tikehau's public Talentview vacancies, rendering its JS-only board."""
    listing_url = "https://tikehau-capital-career.talentview.io/jobs"
    response = requests.get(listing_url, timeout=(8, 25))
    response.raise_for_status()
    page = _CareerHTML()
    page.feed(response.text)
    links = [(urljoin(listing_url, href), label) for href, label in page.links
             if urlparse(urljoin(listing_url, href)).hostname == "tikehau-capital-career.talentview.io"
             and urlparse(urljoin(listing_url, href)).path.startswith("/jobs/")]
    if not links:
        rendered = _render_public_career_page(listing_url, "a[href*='/jobs/']")
        page = _CareerHTML()
        page.feed(rendered)
        links = [(urljoin(listing_url, href), label) for href, label in page.links
                 if urlparse(urljoin(listing_url, href)).hostname == "tikehau-capital-career.talentview.io"
                 and urlparse(urljoin(listing_url, href)).path.startswith("/jobs/")]
    offers = list(dict(links).items())
    if not offers:
        raise ValueError("aucune fiche publique Tikehau exposée après rendu JavaScript")
    try:
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise ValueError("Playwright requis pour ouvrir les fiches publiques Tikehau") from exc
    jobs: list[Opportunity] = []
    detail_failures = 0
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            try:
                detail_page = browser.new_page()
                for url, title in offers:
                    try:
                        result = detail_page.goto(url, wait_until="domcontentloaded", timeout=15_000)
                        if result is not None and result.status >= 400:
                            detail_failures += 1
                            continue
                        try:
                            detail_page.locator("h1").first.wait_for(timeout=4_000)
                        except PlaywrightTimeoutError:
                            pass
                        job = _career_detail(url, "Tikehau Capital", title,
                                             html_override=detail_page.content())
                        if job:
                            jobs.append(job)
                    except Exception:
                        detail_failures += 1
                        continue
            finally:
                browser.close()
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError(f"navigateur public Tikehau indisponible ({type(exc).__name__})") from exc
    if not jobs and detail_failures == len(offers):
        raise ValueError("les fiches Tikehau sont listées, mais aucune n'a pu être chargée")
    return jobs


def _groupama_am_jobs() -> list[Opportunity]:
    """Read the official AM career page's directly linked Groupama AM vacancies."""
    listing_url = "https://www.groupama-am.com/fra/fr/intermediaire/carriere/groupama-asset-management-carriere"
    response = requests.get(listing_url, timeout=(8, 25))
    response.raise_for_status()
    page = _CareerHTML()
    page.feed(response.text)
    offers: dict[str, str] = {}
    for href, label in page.links:
        url = urljoin(listing_url, href)
        parsed = urlparse(url)
        if (parsed.scheme == "https" and parsed.hostname == "www.groupama-gan-recrute.com"
                and parsed.path.startswith("/details-offre/") and _market_relevant(label)):
            offers[url] = label
    def load(pair: tuple[str, str]) -> Opportunity | None:
        return _career_detail(pair[0], "Groupama AM", pair[1])
    with ThreadPoolExecutor(max_workers=4) as pool:
        return [job for job in pool.map(load, offers.items()) if job]


def _axa_jobs() -> list[Opportunity]:
    """Read AXA's public Stage list and verify market roles on their direct offer pages."""
    listing = "https://recrutement.axa.fr/recherche-d%27offres"
    params = {"acm": "ALL", "alrpm": "ALL", "ascf": '[{"key":"custom_fields.LocalContractType","value":"Stage"}]'}
    candidates: dict[str, tuple[str, str, str]] = {}
    pages = 1
    number = 1
    seen: set[str] = set()
    while number <= pages:
        response = requests.get(listing, params={**params, **({"p": number} if number > 1 else {})}, timeout=(8, 25))
        response.raise_for_status()
        body = response.text
        anchors = list(re.finditer(r'<a\b(?=[^>]*\bsearch-results-list__job-link\b)[^>]*>.*?</a>', body, re.I | re.S))
        if number == 1 and not anchors:
            raise ValueError("AXA : aucune fiche de stage dans la liste publique")
        total = re.search(r'class="pagination-current"[^>]*max="(\d+)"', body)
        if total:
            pages = max(pages, int(total.group(1)))
        links = {anchor.group() for anchor in anchors}
        if not links - seen:
            raise ValueError("Pagination AXA sans progression")
        seen.update(links)
        for index, anchor in enumerate(anchors):
            tag = anchor.group()
            href = re.search(r'\bhref="([^"]+)"', tag)
            if not href:
                continue
            url = urljoin(listing, html.unescape(href.group(1)))
            if urlparse(url).hostname != "recrutement.axa.fr" or not urlparse(url).path.startswith("/emploi/"):
                continue
            title = _plain_text(tag)
            if not re.search(r'\b(?:investment|investissement|portfolio|portefeuille|asset management|'
                             r'march[eé]s?|trading|trader|sales|structur|fixed income|fx|quant|credit)\b',
                             title, re.I):
                continue
            card = body[anchor.end():anchors[index + 1].start() if index + 1 < len(anchors) else anchor.end() + 1800]
            def field(name: str) -> str:
                match = re.search(rf'<li\b[^>]*class="[^"]*\bjob-{name}\b[^"]*"[^>]*>(.*?)</li>', card, re.I | re.S)
                return _plain_text(match.group(1)) if match else ""
            if field("contract").casefold() != "stage" or not field("location"):
                continue
            candidates[url] = (title, field("location"), field("entity") or "AXA")
        number += 1
    detail_errors: list[requests.RequestException] = []
    def load(pair: tuple[str, tuple[str, str, str]]) -> Opportunity | None:
        url, (title, location, company) = pair
        try:
            detail = requests.get(url, timeout=(8, 20))
            detail.raise_for_status()
        except requests.RequestException as exc:
            detail_errors.append(exc)
            return None
        posting = _jsonld_jobposting(detail.text)
        description = _plain_text(str(posting.get("description") or ""))
        job = _opportunity(title, company, location, "Stage", url,
                           _jsonld_job_posted(detail.text), role_context=description)
        return replace(job, source="Site carrière · AXA", description=description[:12_000]) if job else None
    with ThreadPoolExecutor(max_workers=4, thread_name_prefix="axa-detail") as pool:
        jobs = [job for job in pool.map(load, candidates.items()) if job]
    if not jobs and detail_errors:
        raise detail_errors[0]
    return jobs


def _career_page_jobs(company: str, config: tuple[str, str, str]) -> list[Opportunity]:
    listing, host, path_prefix = config
    links: dict[str, str] = {}
    nomura_ids: set[str] = set()
    listings = [listing]
    if company == "Crédit Mutuel / CIC":
        listings.append("https://recrutement.creditmutuel.fr/fr/etudiants/stage.html")
    elif company == "BPCE / Natixis / BRED":
        listings.append("https://recrutement.bpce.fr/offres-emploi")
    elif company == "BNP Paribas":
        listings.extend((
            "https://group.bnpparibas/emploi-carriere/toutes-offres-emploi/stage",
            "https://group.bnpparibas/emploi-carriere/toutes-offres-emploi/vie",
        ))
    elif company == "CACEIS":
        listings.append("https://jobs.caceis.com/pages/offre/listeoffre.aspx?facet_Country=119&lcid=1036&showSearchUrl=1")
    last_error: requests.RequestException | None = None
    listing_failures = 0
    successful_pages = 0
    direct_links = 0
    visited: set[str] = set()
    def read_listing(listing_url: str) -> tuple[str, str]:
        response = requests.get(listing_url, timeout=(8, 25))
        response.raise_for_status()
        return listing_url, response.text

    with ThreadPoolExecutor(max_workers=4) as pool:
        while listings:
            batch = [url for url in listings if url not in visited]
            if not batch:
                break
            visited.update(batch)
            futures = {pool.submit(read_listing, url): url for url in batch}
            for future in as_completed(futures):
                try:
                    listing_url, html = future.result()
                except requests.RequestException as exc:
                    last_error = exc
                    listing_failures += 1
                    continue
                successful_pages += 1
                page = _CareerHTML()
                page.feed(html)
                if company in {"Fidelity International", "Nomura"}:
                    # This public board currently exposes all programmes at once.
                    # Refuse a truncated/paginated response rather than silently
                    # publishing only the first page or inventing pagination URLs.
                    total = re.search(r"\b(\d+)\s+results match!", " ".join(page.parts))
                    identities = {match[1] for href, _ in page.links
                        if urlparse(href).scheme == "https" and urlparse(href).hostname == host
                        and (match := re.search(re.escape(path_prefix) + r"(\d+)-[^/]+/en-GB$", urlparse(href).path))}
                    if not total or len(identities) != int(total[1]):
                        raise ValueError(f"Catalogue {'Fidelity' if company == 'Fidelity International' else company} incomplet : pagination non vérifiée")
                if company in {"SMBC", "Intesa Sanpaolo IMI CIB"}:
                    for href in re.findall(r'href=["\']([^"\']+)["\']', html, re.I):
                        candidate = urljoin(listing_url, __import__('html').unescape(href))
                        parsed_page = urlparse(candidate)
                        offset = dict(parse_qsl(parsed_page.query)).get('startrow', '')
                        if (parsed_page.scheme == 'https' and parsed_page.hostname == host
                                and parsed_page.path == urlparse(listing).path and offset.isdigit()
                                and candidate not in visited and candidate not in listings):
                            if int(offset) >= 2500 or len(listings) >= 100:
                                raise ValueError('SuccessFactors pagination exceeds verified limit')
                            listings.append(candidate)
                if company == "BlackRock":
                    pages = re.search(r'data-total-pages="(\d+)"', html)
                    if not pages or not 1 <= int(pages[1]) <= 50:
                        raise ValueError('BlackRock campus pagination requires verification')
                    for number in range(2,int(pages[1])+1):
                        candidate = listing.rstrip('/')+'/'+str(number)
                        if candidate not in visited and candidate not in listings:
                            listings.append(candidate)
                if company == "HSBC Continental Europe":
                    total = re.search(r'jobRecordsFound:\s*parseInt\("(\d+)"\)', html)
                    per_page = re.search(r'jobRecordsPerPage:\s*parseInt\("(\d+)"\)', html)
                    if not total or not per_page or int(per_page[1]) < 1:
                        raise ValueError("pagination HSBC non reconnue")
                    if int(total[1]) > 25 * int(per_page[1]):
                        raise ValueError("pagination HSBC au-delà de la limite de collecte")
                    for offset in range(int(per_page[1]), int(total[1]), int(per_page[1])):
                        candidate = f"{listing}&startrow={offset}"
                        if candidate not in listings:
                            listings.append(candidate)
                if company in {"La Banque Postale", "Amundi · portail groupe"}:
                    # Pagination lives in <nav>, intentionally omitted from offer text.
                    for href in re.findall(r'href=["\']([^"\']+)["\']', html, re.I):
                        candidate = urljoin(listing_url, href).split("#", 1)[0]
                        parsed_page = urlparse(candidate)
                        base_path = urlparse(listing).path
                        pattern = (re.escape(base_path[:-5]) + r"\.p-(\d+)\.html"
                                   if company == "La Banque Postale" else re.escape(base_path) + r"page/(\d+)/")
                        number = re.fullmatch(pattern, parsed_page.path)
                        if (parsed_page.scheme == "https" and parsed_page.hostname == host and number
                                and 2 <= int(number[1]) <= 25 and len(listings) < 25
                                and candidate not in listings):
                            listings.append(candidate)
                links_to_process: list[tuple[str, str]] = []
                current_heading = ""
                if company == "La Banque Postale":
                    for event_type, href, label in page.events:
                        if event_type == "heading":
                            current_heading = label
                        else:
                            parsed_href = urlparse(urljoin(listing_url, href))
                            if (parsed_href.hostname == host and parsed_href.path.startswith(path_prefix)
                                    and not _market_relevant(label) and _market_relevant(current_heading)):
                                label = current_heading
                            links_to_process.append((href, label))
                else:
                    links_to_process = page.links
                for href, label in links_to_process:
                    url = urljoin(listing_url, href)
                    parsed = urlparse(url)
                    if company in {"Fidelity International", "Nomura"} and not re.fullmatch(
                            re.escape(path_prefix) + r"\d+-[^/]+/en-GB", parsed.path):
                        continue
                    if company == "La Banque Postale" and parsed.hostname == host:
                        query = dict(parse_qsl(parsed.query))
                        same_listing = parsed.path == urlparse(listing).path
                        page_parameter = any(any(token in key.casefold() for token in ("page", "offset", "start"))
                                             for key in query)
                        if (same_listing and page_parameter and len(listings) < 25
                                and url not in visited and url not in listings):
                            listings.append(url)
                    if company in {"BNP Paribas", "BNP Paribas Asset Management"} and parsed.hostname == host and parsed.path == urlparse(listing_url).path:
                        page_number = dict(parse_qsl(parsed.query)).get("page", "")
                        if page_number.isdigit() and 1 <= int(page_number) <= 25 and url not in visited and url not in listings:
                            listings.append(url)
                    prefixes = ("/offre-de-emploi/emploi-", "/job/emploi-") if company == "CACEIS" else (path_prefix,)
                    if parsed.scheme != "https" or parsed.hostname != host or not parsed.path.startswith(prefixes):
                        continue
                    if parsed.path.rstrip("/") == path_prefix.rstrip("/") and not parsed.query:
                        continue
                    direct_links += 1
                    market_label = _market_candidate(label) or (company == "BlackRock" and bool(_kind(label,""))) or (
                        company == "Ofi Invest" and bool(re.search(
                            r"analyste\s+(?:cr[eÃ©]dit|obligataire)|fixed\s+income\s+analyst|credit\s+analyst",
                            label, re.IGNORECASE,
                        ))
                    )
                    if market_label:
                        if company == "Nomura":
                            identity = re.search(r"/opp/(\d+)-", parsed.path)[1]
                            if identity in nomura_ids:
                                continue
                            nomura_ids.add(identity)
                        links[url] = label
    if not successful_pages and last_error:
        raise last_error
    if successful_pages and not direct_links and company not in {"Fidelity International", "Nomura"}:
        raise ValueError("aucun lien d'offre directe dans les pages carrières publiques")
    detail_errors: list[Exception] = []
    failed_urls: list[str] = []
    def load(pair: tuple[str, str]) -> Opportunity | None:
        try:
            job = _career_detail(pair[0], "BNP Paribas" if company == "BNP Paribas Asset Management" else company, pair[1])
            return replace(job, company="BNP Paribas Asset Management") if job and company == "BNP Paribas Asset Management" else job
        except (requests.RequestException, ValueError, TypeError) as exc:
            detail_errors.append(exc)
            failed_urls.append(pair[0])
            return None
    with ThreadPoolExecutor(max_workers=5) as pool:
        jobs = [job for job in pool.map(load, list(links.items())) if job]
    if not jobs and detail_errors:
        raise detail_errors[0]
    if listing_failures or failed_urls:
        raise _PartialSourceError(jobs, failed_urls, search_failures=listing_failures)
    return jobs


class _PartialSourceError(ValueError):
    """Keep verified results and identify the still-listed offers that failed."""

    def __init__(self, jobs: list[Opportunity], failed_urls: list[str], *, search_failures: int = 0,
                 retry_not_before: str = ""):
        reason = (f"collecte incomplète : {search_failures} requête(s) source en échec"
                  if search_failures else f"collecte incomplète : {len(failed_urls)} fiche(s) indisponible(s)")
        super().__init__(reason)
        self.jobs = jobs
        self.failed_urls = set(failed_urls)
        self.preserve_cached = bool(search_failures)
        self.retry_not_before = retry_not_before


def _morgan_stanley_sales_candidate(title: str) -> bool:
    return bool(re.search(r"\bsales\b", title, re.I) and _market_candidate(title)
                and not re.search(
                    r"\b(?:senior|sr|vp|vice president|director|head|lead|manager|wealth|retail|corporate|"
                    r"consumer|compensation|operations|control|compliance|research|developer|engineer|quant\w*)\b",
                    title, re.I))


def _morgan_stanley_detail(identity: str, title: str) -> Opportunity | None:
    host = "https://morganstanley.eightfold.ai"
    path = f"/careers/job/{identity}"
    url = f"{host}{path}?domain=morganstanley.com"
    response = requests.get(host + "/api/pcsx/position_details",
                            params={"position_id": identity, "domain": "morganstanley.com"},
                            timeout=(8, 20), allow_redirects=False)
    if response.status_code in (404, 410):
        return None
    response.raise_for_status()
    if response.status_code != 200:
        raise ValueError("Fiche Morgan Stanley indisponible")
    payload = response.json()
    info = payload.get("data") or {}
    if (payload.get("status") != 200 or str(info.get("id")) != identity
            or info.get("positionUrl") != path
            or _canonical_title(str(info.get("name") or "")) != _canonical_title(title)):
        raise ValueError("Fiche Morgan Stanley sans annonce correspondante")
    action = (info.get("positionUserActions") or {}).get("applyAction") or {}
    apply = urlparse(str(action.get("applyUrl") or ""))
    reference = str(info.get("atsJobId") or "")
    if (action.get("status") != "link_off" or apply.scheme != "https"
            or apply.netloc != "ms.wd5.myworkdayjobs.com" or not re.fullmatch(r"(?:PT-)?JR\d+", reference)
            or not re.fullmatch(r"/External/job/[^/]+/[^/]+_" + re.escape(reference) + r"(?:-\d+)?/apply", apply.path)):
        raise ValueError("Fiche Morgan Stanley sans candidature employeur vérifiable")
    # Read only the public vacancy. Never follow the application link.
    response = requests.get(url, timeout=(8, 20), allow_redirects=False)
    if response.status_code in (404, 410):
        return None
    response.raise_for_status()
    if response.status_code != 200:
        raise ValueError("Redirection de la fiche Morgan Stanley")
    posting = _jsonld_jobposting(response.text)
    if (not posting or posting.get("url") != url
            or (posting.get("hiringOrganization") or {}).get("name") != "Morgan Stanley"
            or _canonical_title(str(posting.get("title") or "")) != _canonical_title(title)):
        raise ValueError("Métadonnées Morgan Stanley sans annonce correspondante")
    deadline = str(posting.get("validThrough") or "")[:10]
    if deadline:
        try:
            if date.fromisoformat(deadline) < datetime.now(timezone.utc).date():
                return None
        except ValueError as exc:
            raise ValueError("Échéance Morgan Stanley invalide") from exc
    description = _plain_text(str(posting.get("description") or ""))
    if not description:
        raise ValueError("Description Morgan Stanley absente")
    if re.search(r"no longer accepting applications|position (?:has been )?filled|job is no longer available",
                 description, re.I):
        return None
    if not (re.search(r"\binstitutional (?:\w+\s+){0,2}(?:clients|investors|sales)\b|\basset managers\b|\bhedge funds\b",
                      description, re.I)
            and re.search(r"\b(?:fixed income|foreign exchange|fx|rates|credit|equities|equity|derivatives)\b",
                          title + " " + description, re.I)):
        return None
    locations = info.get("locations")
    if (not isinstance(locations, list) or not locations
            or any(not isinstance(place, str) or not _plausible_location(place) for place in locations)):
        raise ValueError("Lieu Morgan Stanley absent")
    # Location metadata is sometimes just HK; the matching public detail API
    # retains the actual city, including every location for a multi-city role.
    employment = str(posting.get("employmentType") or "").replace("_", " ")
    job = _opportunity(title, "Morgan Stanley", " / ".join(dict.fromkeys(locations)), employment,
                       url, _jsonld_job_posted(response.text),
                       _structured_job_start(posting) or _start_period(description) or _title_period(title),
                       role_context=description)
    return replace(job, source="Site carrière · morganstanley.eightfold.ai", deadline=deadline,
                   description=description[:12_000]) if job else None


def _morgan_stanley_jobs(_slug: str = "", _company: str = "") -> list[Opportunity]:
    """Scan worldwide Sales results, then verify institutional early-career roles."""
    endpoint = "https://morganstanley.eightfold.ai/api/pcsx/search"
    def page(offset: int) -> tuple[list, int]:
        response = requests.get(endpoint, params={"domain": "morganstanley.com", "query": "sales",
                                                 "location": "", "start": offset, "sort_by": "timestamp"},
                                timeout=(8, 20), allow_redirects=False)
        response.raise_for_status()
        if response.status_code != 200:
            raise ValueError("Redirection du catalogue Morgan Stanley")
        payload = response.json()
        data = payload.get("data") or {}
        rows, total = data.get("positions"), data.get("count")
        if (payload.get("status") != 200 or not isinstance(rows, list)
                or type(total) is not int or total < 0 or len(rows) != min(10, max(0, total - offset))):
            raise ValueError("Catalogue Morgan Stanley incomplet")
        return rows, total

    found, failed = [], []
    candidates: dict[str, str] = {}
    seen: dict[str, int] = {}
    overlaps: set[int] = set()
    search_failures = 0
    search_error: Exception | None = None
    def accept(result: tuple[list, int], total: int, offset: int) -> None:
        rows, count = result
        if count != total:
            raise ValueError("Catalogue Morgan Stanley modifié pendant la collecte")
        for row in rows:
            identity = str(row.get("id") or "")
            if (not identity.isdigit()
                    or row.get("positionUrl") != f"/careers/job/{identity}"):
                raise ValueError("Référence ou pagination Morgan Stanley incohérente")
            if identity in seen:
                overlaps.update((offset, seen[identity]))
            else:
                seen[identity] = offset
            title = html.unescape(str(row.get("name") or ""))
            if _morgan_stanley_sales_candidate(title):
                candidates[identity] = title

    try:
        first, total = page(0)
        accept((first, total), total, 0)
        # The public API returns ten rows even when num=100 is requested.
        # Equal publication timestamps can move a row across page boundaries.
        # Deduplicate references, then reread only overlapping boundaries once;
        # never declare completion until every advertised reference was seen.
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [(offset, pool.submit(page, offset)) for offset in range(10, min(total, 2000), 10)]
            for offset, future in futures:
                try:
                    accept(future.result(), total, offset)
                except (requests.RequestException, ValueError, TypeError, AttributeError) as exc:
                    search_failures += 1
                    search_error = search_error or exc
        if len(seen) < total and overlaps and not search_failures:
            retry_offsets = {near for offset in overlaps for near in (offset - 10, offset, offset + 10)
                             if 0 <= near < min(total, 2000)}
            for offset in sorted(retry_offsets):
                try:
                    accept(page(offset), total, offset)
                except (requests.RequestException, ValueError, TypeError, AttributeError) as exc:
                    search_failures += 1
                    search_error = search_error or exc
        if len(seen) != total:
            search_failures += 1
    except (requests.RequestException, ValueError, TypeError, AttributeError) as exc:
        search_failures += 1
        search_error = search_error or exc
    for identity, title in candidates.items():
        try:
            job = _morgan_stanley_detail(identity, title)
            if job:
                found.append(job)
        except (requests.RequestException, ValueError, TypeError, AttributeError):
            failed.append(f"https://morganstanley.eightfold.ai/careers/job/{identity}?domain=morganstanley.com")
    if failed or search_failures:
        raise _PartialSourceError(found, failed, search_failures=search_failures) from search_error
    return found


_MS_CAMPUS_POSTING = re.compile(
    r"(?P<prefix>/vx/lang-en-GB/mobile-0/brand-2/)(?:xf-[0-9a-f]+/)?"
    r"(?P<vacancy>candidate/so/pm/1/pl/1/opp/(?P<identity>\d+)-[^/]+/en-GB)")


def _morgan_stanley_campus_detail(identity: str, url: str, title: str) -> Opportunity | None:
    response = requests.get(url, timeout=(8, 20), allow_redirects=False)
    if response.status_code in (404, 410):
        return None
    response.raise_for_status()
    if response.status_code != 200:
        raise ValueError("Redirection de la fiche Morgan Stanley Campus")
    page = _CareerHTML()
    page.feed(response.text)
    if re.search(r"no longer (?:accepting applications|available)|(?:vacancy|opportunity) (?:is )?closed",
                 " ".join(page.parts), re.I):
        return None
    if not page.primary_headings or _canonical_title(page.primary_headings[0]) != _canonical_title(title):
        raise ValueError("Fiche Morgan Stanley Campus sans annonce correspondante")
    actions = re.findall(r'<form\b[^>]*action=["\']([^"\']+)["\']', response.text, re.I)
    if not any((action := urlparse(urljoin(url, html.unescape(link)))).netloc == "morganstanley.tal.net"
               and action.scheme == "https"
               and action.path.endswith(f"/opp/{identity}/apply/en-GB") for link in actions):
        raise ValueError("Fiche Morgan Stanley Campus sans candidature ouverte vérifiable")
    fields = _talnet_fields(response.text)
    location, programme, description = (fields.get(key, "") for key in ("city", "program", "job description"))
    if not _plausible_location(location) or not programme or not description:
        raise ValueError("Fiche Morgan Stanley Campus incomplète")
    if not re.search(r"internship|\b(?:full.time|graduate|summer (?:analyst|associate))\b", programme, re.I):
        return None
    posting = _jsonld_jobposting(response.text)
    job = _opportunity(title, "Morgan Stanley", location, programme, url,
                       _jsonld_job_posted(response.text),
                       _structured_job_start(posting) or _start_period(description),
                       role_context=description)
    return replace(job, source="Site carrière · morganstanley.tal.net",
                   description=description[:12_000]) if job else None


def _morgan_stanley_campus_jobs() -> list[Opportunity]:
    """Collect each advertised page of the public early-career programmes board."""
    board = CAREER_PORTALS["Morgan Stanley Campus"]
    listings: dict[str, tuple[str, str]] = {}
    offset, total = 0, None
    search_error = None
    try:
        while True:
            response = requests.get(board, params={"start": offset} if offset else None,
                                    timeout=(8, 20), allow_redirects=False)
            response.raise_for_status()
            page = _CareerHTML()
            page.feed(response.text)
            count = re.search(r"\b(\d+)\s+results? match", " ".join(page.parts), re.I)
            if response.status_code != 200 or not count or total is not None and int(count[1]) != total:
                raise ValueError("Catalogue Morgan Stanley Campus incomplet")
            total = int(count[1])
            before = len(listings)
            for href, title in page.links:
                parsed = urlparse(urljoin(board, href))
                path = _MS_CAMPUS_POSTING.fullmatch(parsed.path)
                if parsed.scheme == "https" and parsed.netloc == "morganstanley.tal.net" and path and title:
                    # Filtered listing pages add an xf path segment to the same vacancy.
                    url = f"https://{parsed.netloc}{path['prefix']}{path['vacancy']}"
                    listings.setdefault(path["identity"], (url, title))
            if len(listings) == total:
                break
            next_offset = len(listings)
            if not before < next_offset < total or not re.search(
                    rf'<a\b[^>]*href=["\']\?start={next_offset}["\'][^>]*>\s*Next page\s*</a>', response.text, re.I):
                raise ValueError("Pagination Morgan Stanley Campus sans progression vérifiable")
            offset = next_offset
    except (requests.RequestException, ValueError) as exc:
        search_error = exc
    found, failed = [], []
    for identity, (url, title) in listings.items():
        if (not _kind(title) or not _market_candidate(title)
                or re.search(r"\b(?:business control unit|transactional management group|developer)\b", title, re.I)):
            continue
        try:
            job = _morgan_stanley_campus_detail(identity, url, title)
            if job:
                found.append(job)
        except (requests.RequestException, ValueError, TypeError):
            failed.append(url)
    if failed or search_error:
        raise _PartialSourceError(found, failed, search_failures=int(search_error is not None)) from search_error
    return found


def _bofa_detail(url: str, title: str, identity: str, page_html: str) -> Opportunity | None:
    """Verify the campus vacancy itself, without following application/login links."""
    posting = _jsonld_jobposting(page_html)
    identifier = posting.get("identifier") or {}
    employer = posting.get("hiringOrganization") or {}
    if (not isinstance(identifier, dict) or str(identifier.get("value")) != identity
            or not isinstance(employer, dict) or employer.get("name") != "Bank of America"
            or _canonical_title(html.unescape(str(posting.get("title") or ""))) != _canonical_title(title)):
        raise ValueError("Fiche Bank of America sans annonce correspondante")
    page = _CareerHTML()
    page.feed(page_html)
    if not any(urlparse(href).scheme == "https" and urlparse(href).netloc == "bankcampuscareers.tal.net"
               and re.search(rf"/opp/{identity}-[^/]+/en-GB$", urlparse(href).path)
               for href, _ in page.links):
        raise ValueError("Fiche Bank of America sans candidature ouverte vérifiable")
    description = _plain_text(str(posting.get("description") or ""))
    if not description:
        raise ValueError("Description Bank of America absente")
    if re.search(r"no longer accepting applications|position (?:has been )?filled|job is no longer available",
                 description, re.I):
        return None
    if _experienced_junior(description):
        return None
    if not re.search(r"\binstitutional(?: investor)? clients\b|\binstitutional investors\b", description, re.I):
        return None
    def campus_date(value: str) -> str:
        for fmt in ("%m/%d/%Y", "%b %d, %Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(value.strip(), fmt).date().isoformat()
            except ValueError:
                continue
        return ""
    # The campus page uses US calendar dates, not ISO datePosted. Do not use
    # indexedDate/internalPostedDate, or a graduation year as the start date.
    published = campus_date(str(posting.get("datePosted") or ""))
    today = datetime.now(timezone.utc).date().isoformat()
    if published > today:
        published = ""
    posted = re.search(r'<div\b[^>]*class=["\'][^"\']*\bhead__posted\b[^"\']*["\'][^>]*>(.*?)</div>',
                       page_html, re.I | re.S)
    apply_by = re.search(r"\bApply by\s+([A-Za-z]{3} \d{1,2}, \d{4})\b",
                         _plain_text(posted[1]) if posted else "")
    deadline = campus_date(apply_by[1]) if apply_by else ""
    if deadline and deadline < today:
        return None
    if apply_by and not deadline:
        raise ValueError("Échéance Bank of America invalide")
    job = _opportunity(title, "Bank of America", _structured_job_location(posting),
                       str(posting.get("employmentType") or "").replace("_", " "), url, published,
                       _structured_job_start(posting) or _start_period(description) or _title_period(title),
                       role_context=description)
    return replace(job, source="Site carrière · careers.bankofamerica.com", deadline=deadline,
                   description=description[:12_000]) if job else None


def _bofa_jobs(_slug: str = "", _company: str = "") -> list[Opportunity]:
    """Worldwide campus catalogue; accept verified institutional markets Sales."""
    endpoint = "https://careers.bankofamerica.com/services/campusjobssearchservlet"
    candidates: dict[str, tuple[str, str]] = {}
    search_failures = 0
    # start=10 returns an empty page on this board despite totalMatches=12.
    # Grow a bounded prefix instead, checking coverage rather than declaring
    # the source complete when a truncated/empty page is returned.
    limit = 100
    try:
        while True:
            response = requests.get(endpoint, params={"start": 0, "rows": limit, "search": "getAllJobs"},
                                    timeout=(8, 20), allow_redirects=False)
            response.raise_for_status()
            if response.status_code != 200:
                raise ValueError("Catalogue Bank of America indisponible")
            payload = response.json()
            rows, total = payload.get("jobsList"), payload.get("totalMatches")
            if (not isinstance(rows, list) or type(total) is not int or total < 0
                    or len(rows) > total or len(rows) > limit):
                raise ValueError("Catalogue Bank of America incohérent")
            seen = set()
            for row in rows:
                identity = str(row.get("jobRequisitionId") or "")
                if not identity.isdigit():
                    raise ValueError("Annonce Bank of America sans référence")
                seen.add(identity)
                title = html.unescape(str(row.get("postingTitle") or ""))
                employment = str(row.get("timeType") or "")
                if (not _kind(title, employment)
                        or not re.search(r"\bsales\b", title, re.I)
                        or re.search(r"\b(?:retail|corporate|quant\w*|research|developer|engineer|operations|"
                                     r"senior|director|vice president|wealth|consumer)\b|private banking|"
                                     r"back[ -]?office|middle[ -]?office", title, re.I)):
                    continue
                path = str(row.get("jcrURL") or "")
                if not re.fullmatch(rf"/en-us/students/job-detail/{identity}/[a-z0-9-]+", path):
                    raise ValueError("Lien Bank of America invalide")
                candidates.setdefault(identity, ("https://careers.bankofamerica.com" + path, title))
            if len(seen) == total:
                break
            if len(seen) < len(rows) or len(rows) < limit or limit >= 2000:
                raise ValueError("Catalogue Bank of America incomplet")
            limit = min(total, 2000)
    except (requests.RequestException, ValueError, TypeError, AttributeError):
        search_failures = 1
    found, failed = [], []
    for identity, (url, title) in candidates.items():
        try:
            response = requests.get(url, timeout=(8, 20), allow_redirects=False)
            response.raise_for_status()
            if response.status_code != 200:
                raise ValueError("Fiche Bank of America indisponible")
            job = _bofa_detail(url, title, identity, response.text)
            if job:
                found.append(job)
        except (requests.RequestException, ValueError, TypeError, AttributeError):
            failed.append(url)
    if failed or search_failures:
        raise _PartialSourceError(found, failed, search_failures=search_failures)
    return found


def _bloomberg_detail(url: str, title: str, location: str, page_html: str) -> Opportunity | None:
    """Read only the vacancy's own Avature fields, excluding related jobs/footer."""
    blocks = re.findall(r'<article\b[^>]*class=["\'][^"\']*\barticle--details\b[^"\']*["\'][^>]*>(.*?)</article>',
                        page_html, re.I | re.S)
    sections = []
    for block in blocks:
        section = _CareerHTML()
        section.feed(block)
        sections.append(section)
    if len(sections) < 3 or _canonical_title(" ".join(sections[0].parts)) != _canonical_title(title):
        raise ValueError("Fiche Bloomberg sans annonce correspondante")
    fields = sections[1].parts
    def field(label: str) -> str:
        return next((fields[index + 1] for index, part in enumerate(fields[:-1]) if part == label), "")
    if not field("Location") or not re.fullmatch(r"[0-9]+", field("Ref #")):
        raise ValueError("Fiche Bloomberg sans lieu ou référence")
    description_section = next((section for section in sections[2:]
                                if "Description & Requirements" in section.headings), None)
    if description_section is None:
        raise ValueError("Description Bloomberg absente")
    description = " ".join(part for part in description_section.parts if part != "Description & Requirements")
    if not description:
        raise ValueError("Description Bloomberg vide")
    if re.search(r"\b(?:no longer accepting applications|position (?:has been )?filled|job is no longer available)\b",
                 description, re.I):
        return None
    # A visible apply link confirms that this detail is still a public vacancy.
    # Inspect its identity only; never visit the login/application page.
    identity = urlparse(url).path.rsplit("/", 1)[-1]
    page = _CareerHTML()
    page.feed(page_html)
    if not any(urljoin(url, href) == f"https://bloomberg.avature.net/careers/Login?jobId={identity}"
               and label.strip().casefold() in {"apply", "apply now"} for href, label in page.links):
        raise ValueError("Fiche Bloomberg sans candidature ouverte vérifiable")
    if not re.search(r"sales|client service|financial solutions", field("Business Area"), re.I):
        return None
    employment = ""
    if re.search(r"\banalytics\s*(?:&|and)\s*sales\b", title, re.I) and not _kind(title):
        # These named entry programmes omit 'graduate' in some regions. Confirm
        # the programme and entry requirements in its own description first.
        if not (re.search(r"\banalytics\s*(?:&|and)\s*sales\s+program(?:me)?\b", description, re.I)
                and re.search(r"begin your career|early professional|bachelor.?s degree|recent graduates?", description, re.I)
                and re.search(r"financial markets", description, re.I)):
            return None
        employment = "Graduate programme"
    if _experienced_junior(description):
        return None
    structured = _jsonld_jobposting(page_html)
    # Related vacancies can also carry JobPosting data. A conflicting title or
    # employer identity must not date, schedule or expire the current vacancy.
    structured_title = structured.get("title", title)
    structured_url = structured.get("url", url)
    try:
        metadata_url = urljoin(url, structured_url) if isinstance(structured_url, str) else ""
        same_posting = (isinstance(structured_title, str)
                        and _canonical_title(structured_title) == _canonical_title(title)
                        and is_trusted_offer_url(metadata_url)
                        and urlparse(metadata_url).hostname == "bloomberg.avature.net"
                        and re.fullmatch(rf"/careers/JobDetail/[^/]+/{identity}", urlparse(metadata_url).path))
    except ValueError:
        same_posting = False
    if not same_posting:
        structured = {}
    deadline = str(structured.get("validThrough") or "")[:10]
    try:
        if deadline and date.fromisoformat(deadline) < datetime.now(timezone.utc).date():
            return None
    except ValueError:
        deadline = ""
    start = _structured_job_start(structured) or _start_period(description) or _title_period(title)
    # The portal uses '2027 ... (May class, ...)' for an explicit intake.
    cohort = re.search(r"\b([A-Za-z]+) class\b", title, re.I)
    year = re.match(r"(20\d{2})\b", title)
    if not start and cohort and year and start_month(f"{cohort[1]} {year[1]}"):
        start = f"{cohort[1]} {year[1]}"
    job = _opportunity(title, "Bloomberg", location or field("Location"), employment, url,
                       _jsonld_job_posted(page_html) if structured else "", start, role_context=description)
    return replace(job, source="Site carrière · bloomberg.avature.net", deadline=deadline,
                   description=description[:12_000]) if job else None


def _bloomberg_jobs(_slug: str = "", _company: str = "") -> list[Opportunity]:
    """Scan the worldwide portal without inherited experience/country filters."""
    endpoint = CAREER_PORTALS["Bloomberg"]
    candidates: dict[str, tuple[str, str, str]] = {}
    seen: set[str] = set()
    search_failures = 0
    # Avature currently caps this board at 12 even if a larger size is requested.
    for offset in range(0, 1200, 12):
        try:
            response = requests.get(endpoint, params={"jobRecordsPerPage": 12, "jobOffset": offset},
                                    timeout=(8, 20), allow_redirects=False)
            response.raise_for_status()
            if response.status_code != 200:
                raise ValueError("Redirection du catalogue Bloomberg")
            total_match = re.search(r'aria-label=["\']([0-9]+) results["\']', response.text, re.I)
            if not total_match:
                raise ValueError("Catalogue Bloomberg sans nombre de résultats")
            total = int(total_match[1])
            rows = re.findall(r'<article\b[^>]*class=["\'][^"\']*\barticle--result\b[^"\']*["\'][^>]*>(.*?)</article>',
                              response.text, re.I | re.S)
            if len(rows) > 12 or rows and not total:
                raise ValueError("Nombre d'annonces Bloomberg incohérent")
            before = len(seen)
            for block in rows:
                row = _CareerHTML()
                row.feed(block)
                links = [(urljoin(endpoint, href), label) for href, label in row.links
                         if label.casefold() != "apply"]
                if not links:
                    raise ValueError("Annonce Bloomberg sans lien")
                url, title = links[0]
                if (not is_trusted_offer_url(url) or urlparse(url).hostname != "bloomberg.avature.net"
                        or not re.fullmatch(r"/careers/JobDetail/[^/]+/[0-9]+", urlparse(url).path) or not title):
                    raise ValueError("Lien d'annonce Bloomberg invalide")
                url = "https://bloomberg.avature.net" + urlparse(url).path
                identity = url.rsplit("/", 1)[-1]
                seen.add(identity)
                # No fallback to quant, engineering, proprietary trading or ops.
                if (not re.search(r"\b(?:sales|client services?|product specialist)\b", title, re.I)
                        or re.search(r"\b(?:senior|director|engineer|developer|retail|corporate)\b", title, re.I)
                        or not _market_candidate(title)
                        or not (_kind(title) or re.search(r"\banalytics\s*(?:&|and)\s*sales\b", title, re.I))):
                    continue
                place = re.search(r'<span\b[^>]*class=["\'][^"\']*\blist-item-location\b[^"\']*["\'][^>]*>(.*?)</span>',
                                  block, re.I | re.S)
                candidates.setdefault(identity, (url, title, _plain_text(place[1]) if place else ""))
            if (rows and len(seen) == before) or (not rows and offset < total):
                raise ValueError("Pagination Bloomberg sans progression")
            if offset + len(rows) >= total:
                break
            if len(rows) != 12:
                raise ValueError("Page Bloomberg incomplète")
        except (requests.RequestException, ValueError, TypeError):
            search_failures += 1
            break
    else:
        search_failures += 1
    found: list[Opportunity] = []
    failed: list[str] = []
    for url, title, location in candidates.values():
        try:
            response = requests.get(url, timeout=(8, 20), allow_redirects=False)
            response.raise_for_status()
            if response.status_code != 200:
                raise ValueError("Redirection de la fiche Bloomberg")
            job = _bloomberg_detail(url, title, location, response.text)
            if job:
                found.append(job)
        except (requests.RequestException, ValueError, TypeError):
            failed.append(url)
    if failed or search_failures:
        raise _PartialSourceError(found, failed, search_failures=search_failures)
    return found


def _susquehanna_jobs(_slug: str = "", _company: str = "") -> list[Opportunity]:
    """Read worldwide institutional Sales vacancies, then verify employer pages."""
    endpoint = "https://careers.sig.com/api/jobs"
    candidates: dict[str, str] = {}
    seen: set[str] = set()
    received = 0
    search_failures = 0
    today = datetime.now(timezone.utc).date().isoformat()
    for page in range(1, 21):
        try:
            response = requests.get(endpoint, params={"tags1": "Institutional Sales", "page": page, "limit": 20},
                                    timeout=(8, 20), allow_redirects=False)
            response.raise_for_status()
            if response.status_code != 200:
                raise ValueError("Redirection du catalogue Susquehanna")
            payload = response.json()
            if (not isinstance(payload, dict) or not isinstance(payload.get("jobs"), list)
                    or type(payload.get("totalCount")) is not int or payload["totalCount"] < 0):
                raise ValueError("Catalogue public Susquehanna invalide")
            rows = payload["jobs"]
            before = len(seen)
            for row in rows:
                item = row.get("data") if isinstance(row, dict) else None
                if not isinstance(item, dict) or not re.fullmatch(r"[0-9]+", str(item.get("slug") or "")):
                    raise ValueError("Annonce publique Susquehanna invalide")
                identity = str(item["slug"])
                seen.add(identity)
                title = str(item.get("title") or "")
                if item.get("applyable") is False or item.get("searchable") is False:
                    continue
                expiry = str(item.get("posting_expiry_date") or "")[:10]
                try:
                    if expiry and date.fromisoformat(expiry).isoformat() < today:
                        continue
                except ValueError:
                    pass
                if _kind(title) and _market_candidate(title):
                    # Never follow canonical/apply URLs supplied by the feed.
                    candidates[identity] = title
            received += len(rows)
            if (rows and len(seen) == before) or (not rows and received < payload["totalCount"]):
                raise ValueError("Pagination Susquehanna sans progression")
            if received >= payload["totalCount"]:
                break
        except (requests.RequestException, ValueError, TypeError):
            search_failures += 1
            break
    else:
        search_failures += 1

    found: list[Opportunity] = []
    failed: list[str] = []
    for identity, title in candidates.items():
        url = f"https://careers.sig.com/jobs/{identity}?lang=en-us"
        try:
            response = requests.get(url, timeout=(8, 20), allow_redirects=False)
            response.raise_for_status()
            if response.status_code != 200:
                raise ValueError("Redirection de la fiche Susquehanna")
            posting = _jsonld_jobposting(response.text)
            if not posting or _canonical_title(str(posting.get("title") or "")) != _canonical_title(title):
                raise ValueError("Fiche Susquehanna sans annonce correspondante")
            job = _career_detail(url, "Susquehanna", html_override=response.text)
            if job:
                description = _plain_text(str(posting.get("description") or ""))
                found.append(replace(job, description=description[:12_000],
                                     start_period=_structured_job_start(posting) or _start_period(description)
                                     or _title_period(job.title)))
        except (requests.RequestException, ValueError, TypeError):
            failed.append(url)
    if failed or search_failures:
        raise _PartialSourceError(found, failed, search_failures=search_failures)
    return found


def _dnca_jobs(_slug: str = "", _company: str = "") -> list[Opportunity]:
    """Collect DNCA's public HTML offers, excluding the surrounding career listing."""
    listing = CAREER_PORTALS["DNCA"]
    response = requests.get(listing, timeout=(8, 25))
    response.raise_for_status()
    page = _CareerHTML()
    page.feed(response.text)
    links = dict.fromkeys(
        urljoin(listing, href).split("?", 1)[0].split("#", 1)[0]
        for href, _ in page.links
        if urlparse(urljoin(listing, href)).hostname == "www.dnca-investments.com"
        and re.fullmatch(r"/carrieres/[A-Za-z0-9]+", urlparse(urljoin(listing, href)).path)
        and is_trusted_offer_url(urljoin(listing, href))
    )
    errors: list[Exception] = []
    failed_urls: list[str] = []

    def load(url: str) -> Opportunity | None:
        try:
            detail = requests.get(url, timeout=(8, 20))
            detail.raise_for_status()
            article = re.search(
                r'<article\b[^>]*data-careers=["\']detail["\'][^>]*>(.*?)</article>',
                detail.text, re.DOTALL | re.IGNORECASE,
            )
            if not article:
                raise ValueError("fiche DNCA absente de la page publique")
            offer = _CareerHTML()
            offer.feed(article.group(1))
            title = offer.headings[0] if offer.headings else ""
            metadata = []
            for raw in re.findall(r'<span\b[^>]*data-role=["\']meta-item["\'][^>]*>(.*?)</span>',
                                  article.group(1), re.DOTALL | re.IGNORECASE):
                field = _CareerHTML()
                field.feed(raw)
                metadata.append(" ".join(field.parts))
            # Publication belongs to this offer, never to a neighbouring vacancy.
            published = next((match.group(1) for value in metadata
                              if (match := re.search(r"Publiée le\s+(\d{2}/\d{2}/\d{4})", value))), "")
            description = " ".join(offer.parts)
            job = _opportunity(title, "DNCA", metadata[1] if len(metadata) > 1 else "",
                               metadata[0] if metadata else "", url,
                               _career_publication_date(published), _start_period(description),
                               role_context=description)
            return replace(job, source="Site carrière · DNCA", description=description[:12_000]) if job else None
        except (requests.RequestException, ValueError) as exc:
            errors.append(exc)
            failed_urls.append(url)
            return None

    with ThreadPoolExecutor(max_workers=5) as pool:
        jobs = [job for job in pool.map(load, links) if job]
    if not jobs and errors:
        raise errors[0]
    if errors:
        raise _PartialSourceError(jobs, failed_urls)
    return jobs


def _comgest_jobs(_slug: str = "", _company: str = "") -> list[Opportunity]:
    """Read Comgest's official internship page and validate each role from its PDF."""
    listing = "https://cm.comgest.com/fr/about-us/nos-collaborateurs/carrieres/stages"
    response = requests.get(listing, timeout=(8, 25))
    response.raise_for_status()
    page = _CareerHTML()
    page.feed(response.text)
    pdfs = [(urljoin(listing, href), label) for href, label in page.links
            if urlparse(urljoin(listing, href)).hostname == "cm.comgest.com"
            and urlparse(urljoin(listing, href)).path.casefold().endswith(".pdf")]
    applications = [urljoin(listing, href) for href, _ in page.links
                    if "application-form" in href and "jobID=" in href]
    try:
        from pypdf import PdfReader
    except ImportError:
        return []
    jobs: list[Opportunity] = []
    for (pdf_url, title), application_url in zip(pdfs, applications):
        if urlparse(application_url).hostname != "cm.comgest.com":
            continue
        try:
            pdf_response = requests.get(pdf_url, timeout=(8, 25))
            pdf_response.raise_for_status()
            description = " ".join(
                extracted for extracted in
                (pdf_page.extract_text() or "" for pdf_page in PdfReader(BytesIO(pdf_response.content)).pages)
            )
        except Exception:
            continue
        start = _start_period(description)
        if not start:
            match = re.search(rf"\b(?:begin|start)\w*\s+(?:in\s+)?(?:early\s+)?({_MONTH})\s+(\d{{4}})", description, re.IGNORECASE)
            start = f"{match.group(1)} {match.group(2)}" if match else ""
        job = _opportunity(title, "Comgest", "Paris", "Stage", application_url, "",
                           start or _title_period(title), description)
        if job:
            jobs.append(replace(job, source="Site carrière · Comgest", description=description[:12_000]))
    return jobs


def _bnp_cib_jobs(_slug: str = "", _company: str = "") -> list[Opportunity]:
    """Read public CIB listings, including the Global Markets career page."""
    candidates: dict[str, tuple[str, str]] = {}
    last_error: requests.RequestException | None = None
    successful_pages = 0
    archives = [
        ("https://careers.cib.bnpparibas/who-we-are/global-markets/", 1),
        ("https://careers.cib.bnpparibas/job-contract-type/internship/", 4),
        ("https://careers.cib.bnpparibas/job-contract-type/stage/", 4),
    ]
    # Some CIB internships are filed under a job domain rather than their
    # contract type. This official page has included Global Markets roles.
    archives.append(("https://careers.cib.bnpparibas/job-domain/temporary-status/", 1))
    def read_archive(archive: tuple[str, int], *, browser: bool = False) -> tuple[dict[str, tuple[str, str]], int, Exception | None]:
        base, pages = archive
        found: dict[str, tuple[str, str]] = {}
        successful = 0
        error: requests.RequestException | None = None
        for page_number in range(1, pages + 1):
            listing = base if page_number == 1 else f"{base}page/{page_number}/"
            try:
                if browser:
                    page_html = _render_public_career_page(listing, 'a[href*="/jobs/"]')
                else:
                    response = requests.get(listing, timeout=(8, 20))
                    response.raise_for_status()
                    page_html = response.text
                successful += 1
            except (requests.RequestException, ValueError) as exc:
                error = exc
                break
            page = _CareerHTML()
            page.feed(page_html)
            visible_text = " ".join(page.parts)
            for href, title in page.links:
                url = urljoin(listing, href)
                parsed = urlparse(url)
                if parsed.scheme != "https" or parsed.hostname != "careers.cib.bnpparibas" or not parsed.path.startswith("/jobs/"):
                    continue
                if not _market_candidate(title):
                    continue
                date_match = re.search(rf"{re.escape(title)}\s+(\d{{1,2}} [A-Za-z]+ \d{{4}})", visible_text)
                try:
                    published = datetime.strptime(date_match.group(1), "%d %B %Y").date().isoformat() if date_match else ""
                except ValueError:
                    published = ""
                previous = found.get(url)
                found[url] = (title, published or (previous[1] if previous else ""))
        return found, successful, error

    # Archives are independent, but pagination within each remains sequential so
    # an unavailable archive stops immediately without spending further requests.
    # map preserves archive order when a vacancy appears in several listings.
    with ThreadPoolExecutor(max_workers=4, thread_name_prefix="cib-archive") as pool:
        for found, successful, error in pool.map(read_archive, archives):
            successful_pages += successful
            last_error = error or last_error
            for url, (title, published) in found.items():
                previous = candidates.get(url)
                candidates[url] = (title, published or (previous[1] if previous else ""))

    virtual_display = os.getenv("GITHUB_ACTIONS") == "true" and bool(os.getenv("DISPLAY"))
    if not successful_pages and virtual_display:
        with ThreadPoolExecutor(max_workers=4, thread_name_prefix="cib-browser") as pool:
            for found, successful, error in pool.map(lambda archive: read_archive(archive, browser=True), archives):
                successful_pages += successful
                last_error = error or last_error
                candidates.update(found)
    if not successful_pages and last_error:
        raise last_error

    failed_urls: list[str] = []
    def load(pair: tuple[str, tuple[str, str]]) -> Opportunity | None:
        url, (title, published) = pair
        try:
            try:
                job = _career_detail(url, "BNP Paribas", title)
            except requests.RequestException:
                if not virtual_display:
                    raise
                job = _career_detail(url, "BNP Paribas", title,
                                     html_override=_render_public_career_page(url, "h1"))
            if job and not _publication_sort_value(job.published) and published:
                return replace(job, published=published, published_inferred=False)
            return job
        except (requests.RequestException, ValueError, TypeError):
            failed_urls.append(url)
            return None

    with ThreadPoolExecutor(max_workers=5) as pool:
        jobs = [job for job in pool.map(load, list(candidates.items())) if job]
    if failed_urls:
        raise _PartialSourceError(jobs, failed_urls)
    return jobs


def _bnp_tal_jobs(_slug: str = "", _company: str = "") -> list[Opportunity]:
    """Read BNP's public APAC applicant board and verify trainee descriptions."""
    board = "https://bnppapply.tal.net/candidate/jobboard/vacancy/3/adv/"
    response = requests.get(board, timeout=(8, 20))
    response.raise_for_status()
    listing = _CareerHTML()
    listing.feed(response.text)
    candidates: dict[str, str] = {}
    for href, label in listing.links:
        match = re.search(r"/opp/(\d+-[\w-]+/en-GB)(?:[/?#]|$)", href, re.IGNORECASE)
        if not match or not re.search(r"\b(?:trainee|intern(?:ship)?)\b", label, re.IGNORECASE):
            continue
        # The board injects a per-session /xf-.../ segment into links. The
        # public canonical URL works independently of that transient token.
        url = ("https://bnppapply.tal.net/vx/lang-en-GB/mobile-0/appcentre-1/brand-4/"
               "candidate/so/pm/1/pl/3/opp/" + match.group(1))
        candidates[url] = label.strip()

    def load(pair: tuple[str, str]) -> Opportunity | None:
        url, listing_title = pair
        try:
            detail = requests.get(url, timeout=(8, 20))
            detail.raise_for_status()
        except requests.RequestException:
            return None
        page = _CareerHTML()
        page.feed(detail.text)
        text = " ".join(page.parts)
        if not re.search(r"\bintern(?:ship)?\b", text, re.IGNORECASE):
            return None
        location_match = re.search(r"\bLocation\s+(.+?)\s+(?:Job Category|Position Type|Job Description)\b", text)
        location = location_match.group(1).strip() if location_match else ""
        title = listing_title
        if not _market_relevant(title):
            specific = re.search(
                r"\b(Summer Internship Programme\s*[-–]\s*[^.]+?Desk|"
                r"\d+-month Internship within Global Markets\s*[-–]+\s*the [^.]+?desk)\b",
                text, re.IGNORECASE,
            )
            title = specific.group(1).strip() if specific else ""
        job = _opportunity(title, "BNP Paribas", location, "Stage", url, "", _start_period(text))
        return replace(job, source="Site carrière · BNP Paribas APAC") if job else None

    with ThreadPoolExecutor(max_workers=5) as pool:
        return [job for job in pool.map(load, list(candidates.items())) if job]


def _career_rss_jobs(company: str, host: str, contracts: tuple[int, ...]) -> list[Opportunity]:
    """Read the employer's public stage and VIE RSS feeds."""
    links: dict[str, tuple[str, str]] = {}
    last_error: Exception | None = None
    successful_feeds = 0

    def read_feed(contract: int) -> tuple[ElementTree.Element | None, Exception | None]:
        try:
            response = requests.get(
                f"https://{host}/handlers/offerRss.ashx",
                params={"LCID": 1036, "Rss_Contract": contract}, timeout=(8, 25),
            )
            response.raise_for_status()
            root = ElementTree.fromstring(response.content)
            if root.tag != "rss" or root.find("channel") is None:
                raise ValueError(f"{host}: réponse sans flux RSS valide")
            return root, None
        except (requests.RequestException, ValueError, ElementTree.ParseError) as exc:
            return None, exc

    with ThreadPoolExecutor(max_workers=min(4, max(1, len(contracts))),
                            thread_name_prefix="career-rss") as pool:
        feeds = list(pool.map(read_feed, contracts))
    for root, error in feeds:
        if error is not None:
            last_error = error
            continue
        successful_feeds += 1
        for item in root.findall(".//item"):
            title = _plain_text(item.findtext("title") or "")
            url = (item.findtext("link") or "").strip()
            context = _plain_text(item.findtext("description") or "")
            try:
                parsed_url = urlparse(url)
                trusted_offer_url = (
                    parsed_url.scheme == "https"
                    and parsed_url.hostname in {host, f"www.{host}"}
                    and parsed_url.username is None
                    and parsed_url.password is None
                    and parsed_url.port in (None, 443)
                )
            except ValueError:
                trusted_offer_url = False
            if not _market_relevant_with_context(title, context) or not trusted_offer_url:
                continue
            published = ""
            try:
                stamp = parsedate_to_datetime(item.findtext("pubDate") or "")
                stamp = stamp.replace(tzinfo=stamp.tzinfo or timezone.utc).astimezone(timezone.utc)
                if stamp.date() <= datetime.now(timezone.utc).date():
                    published = stamp.date().isoformat()
            except (TypeError, ValueError, OverflowError):
                pass
            # The same offer can occur in both contract feeds. Fetch its detail
            # once, keeping a valid RSS date if another occurrence has none.
            links[url] = (title, links.get(url, ("", ""))[1] or published)
    if not successful_feeds and last_error:
        raise last_error
    detail_errors: list[Exception] = []
    failed_urls: list[str] = []

    def load(pair: tuple[str, tuple[str, str]]) -> Opportunity | None:
        url, (title, published) = pair
        try:
            job = _career_detail(url, company, title)
            # Only the offer's pubDate is a publication fallback; channel dates
            # and collection timestamps must not make an old vacancy look new.
            return replace(job, published=published) if job and published and not job.published else job
        except (requests.RequestException, ValueError, TypeError) as exc:
            detail_errors.append(exc)
            failed_urls.append(url)
            return None
    with ThreadPoolExecutor(max_workers=5) as pool:
        jobs = [job for job in pool.map(load, list(links.items())) if job]
    if not jobs and detail_errors:
        raise detail_errors[0]
    if failed_urls or successful_feeds < len(contracts):
        raise _PartialSourceError(jobs, failed_urls, search_failures=len(contracts) - successful_feeds)
    return jobs


def _ca_cib_jobs(_slug: str = "", _company: str = "") -> list[Opportunity]:
    return _career_rss_jobs("Crédit Agricole CIB", "jobs.ca-cib.com", (579, 1478))


def _candriam_jobs(_slug: str = "", _company: str = "") -> list[Opportunity]:
    return _career_rss_jobs("Candriam", "jobs.candriam.com", (2644,))


def _commerzbank_employment(title: str) -> str:
    # German trainee programmes are graduate jobs, not student internships.
    if re.search(r"\btrainee\b|traineeprogramm", title, re.I):
        return "Graduate"
    return "Internship" if re.search(r"\bpraktik(?:ant\w*|um)\b", title, re.I) else ""


def _bank_career_detail(url: str, company: str) -> Opportunity | None:
    """Read the two banks' public metadata, keeping posting and start dates apart."""
    response = requests.get(url, timeout=(8, 20))
    response.raise_for_status()
    page_html = response.content.decode("utf-8")
    page = _CareerHTML()
    page.feed(page_html)
    def field(label: str) -> str:
        for index, part in enumerate(page.parts[:-1]):
            if part.strip(" :\xa0").casefold() == label.casefold():
                for value in page.parts[index + 1:index + 3]:
                    value = value.strip().lstrip(":").strip()
                    if value.rstrip(":").casefold() != label.casefold():
                        return value
        return ""
    def calendar_date(value: str) -> str:
        try:
            return datetime.strptime(value.replace(".", "/"), "%d/%m/%Y").date().isoformat()
        except ValueError:
            return ""
    text = " ".join(page.parts)
    if company == "Commerzbank":
        structured = _jsonld_jobposting(page_html)
        title = html.unescape(str(structured.get("title") or ""))
        location = _structured_job_location(structured)
        published = _jsonld_job_posted(page_html)
        deadline = str(structured.get("validThrough") or "")[:10]
        start = field("Datum des ersten Arbeitstages") or field("Starting date") or field("First day of work")
        english_start = field("First working day")
        if not start and english_start:
            try:
                start = datetime.strptime(re.sub(r"\s", "", english_start), "%m/%d/%Y").date().isoformat()
            except ValueError:
                start = ""
        employment = _commerzbank_employment(title) or str(structured.get("employmentType") or "")
        text = _plain_text(html.unescape(str(structured.get("description") or ""))) or text
        # Retail/corporate-client sales are not institutional markets desks.
        if re.search(r"privat.? und unternehmerkunden|sales management.*corporate clients|\boperations\b", title, re.I):
            return None
    else:
        meta = re.search(r'<meta\s+property="og:title"\s+content="([^"]+)"', page_html, re.I)
        title = html.unescape(meta[1]) if meta else ""
        location = field("Job Location")
        published = _career_publication_date(field("Posting Start Date"))
        deadline = calendar_date(field("Posting End Date"))
        start = field("Start Date")
        employment = field("Employment Type")
    if not title:
        raise ValueError(f"fiche {company} sans métadonnées de poste")
    if deadline and deadline < datetime.now(timezone.utc).date().isoformat():
        return None
    start = calendar_date(start) or _start_period(f"Start date: {start}")
    job = _opportunity(title, company, location, employment, url, published,
                       start, role_context=text)
    return replace(job, deadline=deadline, description=text[:12_000],
                   source=f"Site carrière · {urlparse(url).hostname}") if job else None


def _commerzbank_jobs(_slug: str = "", _company: str = "") -> list[Opportunity]:
    found, failures = [], []
    first = 1
    while first <= 10_000:
        try:
            response = requests.post("https://api-jobs.commerzbank.com/search/", json={
                "LanguageCode": "DE",
                "SearchParameters": {"FirstItem": first, "CountItem": 100,
                    "MatchedObjectDescriptor": ["ID", "PositionTitle"],
                    "Sort": [{"Criterion": "PublicationStartDate", "Direction": "DESC"}]},
                "SearchCriteria": [{"CriterionName": "PublicationChannel.Code", "CriterionValue": ["12"]}],
            }, timeout=(8, 25))
            response.raise_for_status()
            result = response.json()["SearchResult"]
            rows = result["SearchResultItems"]
        except (requests.RequestException, ValueError, KeyError) as exc:
            if first > 1:
                raise _PartialSourceError(found, failures, search_failures=1) from exc
            raise
        if not rows and first <= int(result["SearchResultCountAll"]):
            raise _PartialSourceError(found, failures, search_failures=1)
        for row in rows:
            item = row["MatchedObjectDescriptor"]
            title = item["PositionTitle"]
            identity = str(item["ID"])
            if not identity.isdigit() or not _market_candidate(title) or not _kind(title, _commerzbank_employment(title)):
                continue
            url = f"https://jobs.commerzbank.com/index.php?ac=jobad&id={identity}&language=2"
            try:
                job = _bank_career_detail(url, "Commerzbank")
                if job:
                    found.append(job)
            except (requests.RequestException, ValueError):
                failures.append(url)
        first += len(rows)
        if first > int(result["SearchResultCountAll"]):
            break
    else:
        raise _PartialSourceError(found, failures, search_failures=1)
    if failures:
        raise _PartialSourceError(found, failures)
    return found


def _standard_chartered_jobs(_slug: str = "", _company: str = "") -> list[Opportunity]:
    response = requests.get("https://jobs.standardchartered.com/sitemap.xml", timeout=(8, 25))
    response.raise_for_status()
    root = ElementTree.fromstring(response.content)
    if root.tag.rsplit("}", 1)[-1] != "urlset":
        raise ValueError("sitemap Standard Chartered invalide")
    found, failures, seen = [], [], set()
    for element in root.iter():
        if element.tag.rsplit("}", 1)[-1] != "loc":
            continue
        url = (element.text or "").strip()
        parsed = urlparse(url)
        title = unquote(parsed.path).replace("-", " ")
        if (parsed.scheme != "https" or parsed.netloc != "jobs.standardchartered.com"
                or not parsed.path.startswith("/job/") or url in seen
                or not _kind(title) or not _market_candidate(title)):
            continue
        seen.add(url)
        try:
            job = _bank_career_detail(url, "Standard Chartered")
            if job:
                found.append(job)
        except (requests.RequestException, ValueError):
            failures.append(url)
    if failures:
        raise _PartialSourceError(found, failures)
    return found


def _amundi_jobs(_slug: str = "", _company: str = "") -> list[Opportunity]:
    return _career_rss_jobs("Amundi", "jobs.amundi.com", (579, 1478))


def _arkea_jobs(_slug: str = "", _company: str = "") -> list[Opportunity]:
    return _career_rss_jobs("Crédit Mutuel Arkéa", "recrutement.arkea.com", (1798,))


def _covea_finance_jobs(_slug: str = "", _company: str = "") -> list[Opportunity]:
    """Read Covéa Finance's public Talentsoft RSS feed for internship offers."""
    return _career_rss_jobs("Covéa Finance", "coveafinance-recrute.talent-soft.com", (579,))


def _ice_data_jobs() -> list[Opportunity]:
    """Read the public iCIMS/Jibe catalogue; never use login/application URLs."""
    found, seen = [], set()
    for page in range(1,101):
        response = requests.get('https://careers.ice.com/api/jobs',
                                params={'page':page,'limit':100},timeout=(8,25))
        response.raise_for_status()
        payload = response.json()
        rows, total = payload.get('jobs'), payload.get('totalCount')
        if not isinstance(rows,list) or type(total) is not int or total < 0:
            raise ValueError('Invalid ICE public catalogue')
        before = len(seen)
        for row in rows:
            item = row.get('data') if isinstance(row,dict) else None
            if not isinstance(item,dict) or not re.fullmatch(r'\d+',str(item.get('slug',''))):
                raise ValueError('Invalid ICE public posting')
            identity = str(item['slug'])
            if identity in seen:
                continue
            seen.add(identity)
            if item.get('external') is False or item.get('applyable') is False:
                continue
            description = _plain_text(str(item.get('description') or ''))
            # The group also recruits in mortgage technology and other divisions.
            if not re.search(r'ICE Data|market data|reference data|fixed income|pricing data',description,re.I):
                continue
            published = str(item.get('posted_date') or '')[:10]
            try:
                published = date.fromisoformat(published).isoformat()
            except ValueError:
                published = ''
            job = _opportunity(str(item.get('title') or ''),'ICE Data Services',
                str(item.get('full_location') or item.get('location_name') or item.get('city') or ''),
                str(item.get('employment_type') or ''),f'https://careers.ice.com/jobs/{identity}',
                published,role_context=description)
            if job:
                found.append(replace(job,description=description[:12_000],source='Site carrière · ICE Data Services'))
        if len(seen) >= total:
            return found
        if len(seen) == before:
            raise _PartialSourceError(found,[],search_failures=1)
    raise _PartialSourceError(found,[],search_failures=1)


def _market_securities_jobs() -> list[Opportunity]:
    """BambooHR exposes a public list and a separate, current vacancy detail."""
    base = 'https://marketsecurities.bamboohr.com/careers'
    response = requests.get(base+'/list',timeout=(8,20))
    response.raise_for_status()
    rows = response.json().get('result')
    if not isinstance(rows,list):
        raise ValueError('Invalid Market Securities catalogue')
    found, failed = [], []
    for row in rows:
        if not isinstance(row,dict) or not re.fullmatch(r'\d+',str(row.get('id',''))):
            raise ValueError('Invalid Market Securities posting')
        title = str(row.get('jobOpeningName') or '')
        if re.search(r'referral|talent pool|spontaneous',title,re.I) or not _market_candidate(title):
            continue
        if not _kind(title,str(row.get('employmentStatusLabel') or '')):
            continue
        url = base+'/'+str(row['id'])
        try:
            detail = requests.get(url+'/detail',timeout=(8,20))
            if detail.status_code in (404,410):
                continue
            detail.raise_for_status()
            info = (detail.json().get('result') or {}).get('jobOpening')
            if (not isinstance(info,dict) or info.get('jobOpeningShareUrl') != url
                    or not info.get('jobOpeningName') or not info.get('description')):
                raise ValueError('Incomplete Market Securities detail')
            if info.get('jobOpeningStatus') != 'Open':
                continue
            place = info.get('location') or {}
            location = ', '.join(str(place[k]) for k in ('city','state','addressCountry') if place.get(k))
            description = _plain_text(str(info['description']))
            job = _opportunity(str(info['jobOpeningName']),'Market Securities',location,
                str(info.get('employmentStatusLabel') or ''),url,str(info.get('datePosted') or ''),
                role_context=description)
            if job:
                found.append(replace(job,description=description[:12_000],source='Site carrière · Market Securities'))
        except (requests.RequestException,ValueError,TypeError,AttributeError):
            failed.append(url)
    if failed:
        raise _PartialSourceError(found,failed)
    return found


def _lbpam_jobs() -> list[Opportunity]:
    """Use the same public Minotore catalogue as the employer's jobs screen."""
    response = requests.post('https://www.lbpam.com/mapi/PageContentAPI/getRelatedContentByModuleAndContext',
        json={'context':{'countryCode':'WORLD','languageCode':'fr','userProfileName':'ALL'},
              'moduleKeyword':'offer','nbrOfElements':-1},timeout=(8,25))
    response.raise_for_status()
    rows = response.json().get('pages')
    if not isinstance(rows,list):
        raise ValueError('Invalid LBP AM public catalogue')
    found = []
    for row in rows:
        if not isinstance(row,dict) or row.get('module') != 'offer':
            raise ValueError('Invalid LBP AM public posting')
        seo = row.get('seoData') or {}
        url = str(seo.get('canonical') or '')
        if row.get('moduleLandingPage') or not url.startswith('https://www.lbpam.com/fr/carrieres/offre/') or not is_trusted_offer_url(url):
            continue
        tags = row.get('tags') or []
        contract = ' '.join(tag[len('CARRIERE_CONTRAT_'):].replace('_',' ') for tag in tags if isinstance(tag,str) and tag.startswith('CARRIERE_CONTRAT_'))
        location = ', '.join(tag[len('CARRIERE_LOCATION_'):].replace('_',' ') for tag in tags if isinstance(tag,str) and tag.startswith('CARRIERE_LOCATION_'))
        title, description = str(seo.get('title') or ''), _plain_text(str(seo.get('description') or ''))
        if not title or not description or not location or not contract:
            raise ValueError('Incomplete LBP AM public posting')
        published = ''
        stamp = row.get('publishingDate')
        if isinstance(stamp,(int,float)) and not isinstance(stamp,bool):
            published = datetime.fromtimestamp(stamp/1000,timezone.utc).date().isoformat()
            if published > datetime.now(timezone.utc).date().isoformat():
                continue
        job = _opportunity(title,'La Banque Postale AM',location,contract,url,published,role_context=description)
        if job:
            found.append(replace(job,description=description[:12_000],source='Site carrière · La Banque Postale AM'))
    return found


def _subsidiary_jobs(company: str) -> list[Opportunity]:
    if company == 'CPR AM':
        return [job for job in _amundi_jobs() if _canonical_company(job.company) in {'cpram','cprassetmanagement'}]
    return _bpce_open_data_jobs('',company)


def _bpce_open_data_jobs(_slug: str = "", _company: str = "") -> list[Opportunity]:
    """Use the public BPCE dataset; never synthesize a direct offer URL."""
    endpoint = ("https://bpce.opendatasoft.com/api/explore/v2.1/catalog/datasets/"
                "groupe-bpce-offres-emploi/exports/json")
    if _company in {'Ostrum AM','Mirova'}:
        term = 'Ostrum' if _company == 'Ostrum AM' else 'Mirova'
        response = requests.get(endpoint,params={'where':f'search(organization,"{term}")'},timeout=(5,45))
    else:
        response = requests.get(endpoint, timeout=(5, 45))
    response.raise_for_status()
    payload = response.json()
    rows = payload.get("results", []) if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        raise ValueError("format Open Data BPCE inconnu")

    def field(row: dict, *names: str) -> str:
        fields = row.get("fields", row)
        if not isinstance(fields, dict):
            return ""
        normalized = {re.sub(r"[^a-z0-9]", "", unicodedata.normalize("NFKD", str(key).casefold())): value
                      for key, value in fields.items()}
        for name in names:
            key = re.sub(r"[^a-z0-9]", "", unicodedata.normalize("NFKD", name.casefold()))
            value = normalized.get(key)
            if isinstance(value, dict):
                value = next((value.get(subkey) for subkey in ("url", "href", "value", "label", "text")
                              if value.get(subkey)), "")
            if value is not None and str(value).strip():
                return _plain_text(str(value))
        return ""

    jobs: list[Opportunity] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        title = field(row, "intitule", "intitule_du_poste", "intitule_offre", "titre", "titre_offre", "title", "job_title")
        if not _market_relevant(title):
            continue
        company = field(row, "organization", "entreprise", "employeur", "entite", "entite_recruteuse", "societe", "company", "brand")
        if _company in {'Ostrum AM','Mirova'}:
            expected = 'ostrum' if _company == 'Ostrum AM' else 'mirova'
            if expected not in _canonical_company(company):
                continue
            company = _company
        description = field(row, "description", "descriptif", "description_du_poste", "mission", "missions")
        if not company:
            company = "Employeur non précisé (BPCE)"
        if _excluded_employer(company) or "Banque Palatine" in description:
            continue
        location = field(row, "ville", "localisation", "lieu", "lieu_de_travail", "location", "city")
        contract = field(row, "jobtype", "type_de_contrat", "type_contrat", "contrat", "contract", "contract_type")
        published = field(row, "date_de_publication", "date_publication", "published", "publication_date", "date_parution")
        link = field(row, "url", "url_offre", "lien", "lien_offre", "link", "job_url")
        if not link:
            fields = row.get("fields", row)
            for value in fields.values():
                candidate = str(value)
                match = re.search(r"https://recrutement\.bpce\.fr/job/[\w%/?=&.\-]+", candidate)
                if match:
                    link = html.unescape(match.group(0))
                    break
        parsed = urlparse(link)
        if parsed.scheme != "https" or parsed.hostname != "recrutement.bpce.fr" or not parsed.path.startswith("/job/"):
            continue
        if re.fullmatch(r"\d{2}/\d{2}/\d{4}", published):
            try:
                published = datetime.strptime(published, "%d/%m/%Y").date().isoformat()
            except ValueError:
                # One invalid source date must not discard the entire feed.
                published = ""
        explicit_start = field(row, "date_de_debut", "date_debut", "date_prise_de_poste", "job_start_date")
        job = _opportunity(title, company, location, contract, link, published,
                           _start_period(f"Date de début : {explicit_start}")
                           or _start_period(description) or _title_period(title))
        if job:
            jobs.append(replace(job, source="Site carrière · BPCE Open Data", description=description[:12_000]))
    return jobs


def _jobteaser_from_sitemap_url(url: str) -> Opportunity | None:
    """Derive only fields explicit in a public URL; never claim to have read its page."""
    parsed = urlparse(url)
    match = re.fullmatch(
        r"/fr/job-offers/[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}-(.+)", parsed.path,
        re.IGNORECASE,
    )
    if parsed.scheme != "https" or parsed.hostname != "www.jobteaser.com" or not match:
        return None
    slug = match.group(1).lower()
    employer_slug = next((name for name in sorted(JOBTEASER_EMPLOYERS, key=len, reverse=True)
                          if slug.startswith(name + "-")), "")
    if not employer_slug:
        return None
    title_slug = slug[len(employer_slug) + 1:]
    title = title_slug.replace("-", " ").title().replace("V I E", "VIE")
    kind = _kind(title)
    if not kind or not _market_relevant(title) or _excluded_employer(JOBTEASER_EMPLOYERS[employer_slug]):
        return None
    location = next((city for slug_city, city in sorted(JOBTEASER_CITIES.items(), key=lambda pair: -len(pair[0]))
                     if re.search(rf"(?:^|-){re.escape(slug_city)}(?:-|$)", title_slug)), "")
    score = 75 if location and _is_paris(location) and kind == "Stage" else 35 if location else 25
    return Opportunity(
        title=title, company=JOBTEASER_EMPLOYERS[employer_slug], location=location,
        kind=kind, url=url, published="", score=score,
        start_period=_title_period(title), family=_family(title),
        checked_at=datetime.now(timezone.utc).date().isoformat(), source="JobTeaser · sitemap",
    )


def _jobteaser_jobs(_slug: str = "", _company: str = "") -> list[Opportunity]:
    """Read public sitemaps daily, or on forced refresh; no authenticated pages."""
    now = datetime.now(timezone.utc)
    cached: list[Opportunity] = []
    try:
        payload = json.loads(JOBTEASER_CACHE_PATH.read_text(encoding="utf-8"))
        if payload.get("version") == 3:
            cached = [Opportunity(**row) for row in payload.get("jobs", [])]
            if not _force_source_refresh and (now - datetime.fromisoformat(payload["updated"])).total_seconds() < _source_refresh_seconds("JobTeaser · sitemap", None):
                return [replace(job, family=_family(job.title)) for job in cached]
    except (OSError, ValueError, TypeError, KeyError):
        pass
    try:
        response = requests.get(JOBTEASER_INDEX, timeout=(5, 20))
        response.raise_for_status()
        root = ElementTree.fromstring(response.content)
        sitemap_urls = []
        for element in root.findall("{*}sitemap"):
            url = element.findtext("{*}loc") or ""
            parsed = urlparse(url)
            if (parsed.scheme == "https" and parsed.hostname == "assets-cf.jobteaser.com"
                    and re.fullmatch(r"/sitemaps/job_ads_sitemap\d*\.xml", parsed.path)):
                sitemap_urls.append(url)
        if not sitemap_urls:
            raise ValueError("aucun sitemap d'offres JobTeaser accessible")

        def read_sitemap(url: str) -> list[Opportunity]:
            reply = requests.get(url, timeout=(5, 45))
            reply.raise_for_status()
            found: list[Opportunity] = []
            for _, element in ElementTree.iterparse(BytesIO(reply.content), events=("end",)):
                if element.tag.endswith("}url") or element.tag == "url":
                    job = _jobteaser_from_sitemap_url(element.findtext("{*}loc") or "")
                    if job:
                        found.append(job)
                    element.clear()
            return found

        with ThreadPoolExecutor(max_workers=3) as pool:
            groups = list(pool.map(read_sitemap, sitemap_urls[:12]))
        jobs = list({job.url: job for group in groups for job in group}.values())
        JOBTEASER_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        temporary = JOBTEASER_CACHE_PATH.with_suffix(".tmp")
        temporary.write_text(json.dumps({"version": 3, "updated": now.isoformat(),
                                         "jobs": [asdict(job) for job in jobs]}, ensure_ascii=False), encoding="utf-8")
        temporary.replace(JOBTEASER_CACHE_PATH)
        return jobs
    except (requests.RequestException, ElementTree.ParseError, OSError, ValueError):
        if cached:
            return cached
        raise


def _workday_publication_date(start_date: object = "", posted_on: object = "",
                              *, today: date | None = None) -> str:
    """Read Workday's posting start date, with exact relative-day labels as fallback."""
    today = today or datetime.now(timezone.utc).date()
    raw_date = str(start_date or "").strip()[:10]
    try:
        posted = date.fromisoformat(raw_date)
        if posted <= today:
            return posted.isoformat()
    except ValueError:
        pass
    label = str(posted_on or "").strip().casefold()
    if label in {"posted today", "posted 0 days ago"}:
        return today.isoformat()
    if label in {"posted yesterday", "posted 1 day ago"}:
        return (today - timedelta(days=1)).isoformat()
    match = re.fullmatch(r"posted (\d{1,3}) days? ago", label)
    return (today - timedelta(days=int(match.group(1)))).isoformat() if match else ""


_workday_requests = threading.BoundedSemaphore(4)
_workday_pacer = _RequestPacer(0.25)


def _workday_request(send, url: str, pauses: list[requests.HTTPError], **kwargs):
    with _workday_requests:
        if pauses:
            raise pauses[0]
        _workday_pacer.wait()
        if pauses:
            raise pauses[0]
        response = send(url, **kwargs)
        status = getattr(response, "status_code", 200)
        if status in (403, 429) or (status == 503 and getattr(response, "headers", {}).get("Retry-After")):
            try:
                response.raise_for_status()
            except requests.HTTPError as exc:
                pauses.append(exc)
                raise
        return response


def _workday_pause_details(pauses: list[requests.HTTPError]) -> tuple[str, str]:
    if not pauses:
        return "", ""
    return (f"HTTP {pauses[0].response.status_code}",
            max(_http_retry_not_before(error) for error in pauses))


def _pictet_listing() -> list[dict]:
    """Read the public SuccessFactors search, including its ordinary pagination."""
    from playwright.sync_api import sync_playwright
    rows: dict[str, dict] = {}
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page(locale="en-GB")
            response = page.goto(CAREER_PORTALS["Pictet Asset Management"],
                                 wait_until="networkidle", timeout=60_000)
            if response is None or response.status >= 400:
                raise ValueError("Catalogue public Pictet indisponible")
            page.get_by_role("button", name="Search Jobs", exact=True).click(timeout=20_000)
            page.wait_for_function("document.querySelector('tr.jobResultItem') || /0 Jobs matched/.test(document.body.innerText)")
            if not page.locator("tr.jobResultItem").count():
                return []
            for _ in range(100):
                batch = page.locator("tr.jobResultItem").evaluate_all("""rs => rs.map(r => ({
                    title: r.querySelector('.jobTitle').textContent.trim(),
                    id: new URL(r.querySelector('.jobTitle').href).searchParams.get('career_job_req_id'),
                    meta: Array.from(r.querySelectorAll('.jobContentEM')).map(n => n.textContent.trim())
                }))""")
                if not batch or any(not re.fullmatch(r"\d+", row.get("id") or "") for row in batch):
                    raise ValueError("Résultats Pictet invalides")
                if all(row["id"] in rows for row in batch):
                    raise ValueError("Pagination Pictet répétée")
                rows.update((row["id"], row) for row in batch)
                next_page = page.get_by_role("button", name="Next Page", exact=True)
                if not next_page.count():
                    break
                first_id = batch[0]["id"]
                next_page.first.click(timeout=10_000)
                page.wait_for_function("""id => {
                    const a = document.querySelector('tr.jobResultItem .jobTitle');
                    return a && new URL(a.href).searchParams.get('career_job_req_id') !== id;
                }""", arg=first_id, timeout=20_000)
            else:
                raise ValueError("Pagination Pictet incomplète")
        finally:
            browser.close()
    return list(rows.values())


def _pictet_detail(row: dict) -> Opportunity | None:
    # Canonical public link: never keep anonymous session/CSRF query parameters.
    url = (CAREER_PORTALS["Pictet Asset Management"]
           + "&career_ns=job_listing&career_job_req_id=" + row["id"])
    response = requests.get(url, timeout=(8, 25))
    if response.status_code in (404, 410):
        return None
    response.raise_for_status()
    page = _CareerHTML()
    page.feed(response.content.decode("utf-8"))
    text = " ".join(page.parts)
    if "This job cannot be viewed" in text:
        return None
    sections = re.split(r"Your team|Votre équipe", text, maxsplit=1)
    if len(sections) != 2 or not re.search(r"Your role|Votre rôle", text):
        raise ValueError("Détail Pictet illisible")
    description = sections[1].split("Diversity & Inclusion", 1)[0].strip()
    team = re.split(r"Your role|Votre rôle", description, maxsplit=1)[0]
    # The group board also carries wealth management and fund administration.
    if not re.search(r"\bPictet (?:Asset Management|AM)\b", team, re.I):
        return None
    title = row["title"]
    employment = ""
    if re.search(r"\b(?:ce stage|this internship|internship (?:position|agreement)|"
                 r"stage (?:de|d'une|d’une)|as an intern)\b", description, re.I):
        employment = "Internship"
    meta = row["meta"]
    if len(meta) < 4:
        raise ValueError("Localisation Pictet absente du catalogue")
    published = _career_publication_date(meta[1].removeprefix("Posted on "))
    job = _opportunity(title, "Pictet Asset Management", f"{meta[3]}, {meta[2]}",
                       employment, url, published, _start_period(description), role_context=description)
    return replace(job, description=description[:12_000], source="Site carrière · Pictet Asset Management") if job else None


def _pictet_jobs() -> list[Opportunity]:
    rows = _pictet_listing()
    failed_urls: list[str] = []
    def load(row: dict) -> Opportunity | None:
        try:
            return _pictet_detail(row)
        except (requests.RequestException, ValueError, TypeError):
            failed_urls.append(CAREER_PORTALS["Pictet Asset Management"]
                               + "&career_ns=job_listing&career_job_req_id=" + row["id"])
            return None
    with ThreadPoolExecutor(max_workers=4) as pool:
        jobs = [job for job in pool.map(load, rows) if job and _eligible_offer(job)]
    if failed_urls:
        raise _PartialSourceError(jobs, failed_urls)
    return jobs


def _rbc_posting_dates(info: dict, description: str) -> tuple[str, str]:
    # The employer's explicit Posted Date can predate a Workday repost.
    posted = re.search(r"\bPosted Date:\s*(\d{4}-\d{2}-\d{2})\b", description, re.I)
    published = _workday_publication_date(posted[1] if posted else info.get("startDate"),
                                          info.get("postedOn"))
    closing = re.search(r"\bApplication Deadline:\s*(\d{4}-\d{2}-\d{2})\b", description, re.I)
    raw = str(closing[1] if closing else info.get("endDate") or info.get("validThrough") or "")[:10]
    try:
        deadline = date.fromisoformat(raw)
        if re.search(r"applications will be accepted until 11:59\s*PM on the day prior "
                     r"to the application deadline date above", description, re.I):
            deadline -= timedelta(days=1)
        return published, deadline.isoformat()
    except ValueError:
        return published, ""


def _workday_jobs(company: str, board: tuple[str, str, str], *, _client=None) -> list[Opportunity]:
    verified_feed = company in {"TP ICAP", "Capital Group", "FactSet", "PIMCO", "Murex", "RBC Capital Markets", "S&P Global Market Intelligence", "LSEG", "Mizuho"}
    if company == "BBVA" and _client is None:
        # Reuse one connection: repeated parallel TLS connections to BBVA time out.
        with requests.Session() as session:
            return _workday_jobs(company, board, _client=session)
    client = _client or requests
    host, tenant, site = board
    base = f"https://{host}/wday/cxs/{tenant}/{site}"
    http_pauses: list[requests.HTTPError] = []

    def listing(term: str, offset: int, facets: dict) -> dict:
        attempts = 1 if verified_feed else 3
        for attempt in range(attempts):
            try:
                response = _workday_request(
                    client.post, f"{base}/jobs", http_pauses,
                    json={"appliedFacets": facets, "limit": 20, "offset": offset, "searchText": term},
                    timeout=(8, 25),
                )
                if getattr(response, 'status_code', 200) in (500, 502, 503, 504) and attempt < attempts - 1:
                    time.sleep(attempt + 1)
                    continue
                response.raise_for_status()
                try:
                    payload = response.json()
                except ValueError as exc:
                    if attempt < attempts - 1:
                        time.sleep(attempt + 1)
                        continue
                    raise ValueError(f'Workday : réponse non JSON après {attempts} tentative(s)') from exc
                if not isinstance(payload, dict) or not isinstance(payload.get("jobPostings"), list):
                    raise ValueError("Catalogue Workday invalide")
                if verified_feed and (type(payload.get("total")) is not int or payload["total"] < 0):
                    raise ValueError("Total Workday indisponible")
                return payload
            except (requests.Timeout, requests.ConnectionError):
                if attempt == attempts - 1:
                    raise
                time.sleep(attempt + 1)

    internship_facets = {}
    # One complete scan avoids overlapping keyword searches and their 400-row cap.
    # Title/contract/market filters are applied below, not weakened on the server.
    searches = [({}, "")]
    catalogue = None
    if company == "Citi":
        # Citi caps the unfiltered catalogue at 2,000 despite having more jobs.
        # Scan every family independently; do not rely on internship contract
        # facets (many graduate and off-cycle roles are marked Regular).
        catalogue = listing("", 0, {})
        families = next((facet.get("values", []) for facet in catalogue.get("facets", [])
                         if facet.get("facetParameter") == "jobFamilyGroup"), [])
        if not families or any(not value.get("id") for value in families):
            raise ValueError("Catégories Citi indisponibles")
        searches = [({"jobFamilyGroup": [value["id"]]}, "") for value in families]
    if company == "BBVA":
        catalogue = listing("", 0, {})
        for facet in catalogue.get("facets", []):
            if facet.get("facetParameter") == "workerSubType":
                ids = [value["id"] for value in facet.get("values", [])
                       if value.get("id") and _kind("", str(value.get("descriptor") or "")) == "Stage"]
                if ids:
                    internship_facets["workerSubType"] = ids
        if not internship_facets:
            raise ValueError("Filtre de stages BBVA indisponible")
        # Also find internships without a contract word in the job title.
        searches = [(internship_facets, "Internship"), ({}, "")]

    def search(query: tuple[dict, str]) -> tuple[list[tuple[str, Opportunity]], Exception | None]:
        facets, contract = query
        found: list[tuple[str, Opportunity]] = []
        seen_pages: set[tuple[str, ...]] = set()
        total = 0
        invalid_row = False
        for offset in range(0, 5000, 20):
            try:
                payload = catalogue if catalogue is not None and not facets and offset == 0 else listing("", offset, facets)
            except (requests.RequestException, ValueError) as exc:
                return found, exc
            rows = payload.get("jobPostings") or []
            # Workday often reports total=0 after the first page, even when
            # further pages exist. Keep the total from the initial response.
            total = max(total, int(payload.get("total") or 0))
            if company == "Citi" and total >= 2000:
                return found, ValueError("Catégorie Citi plafonnée : collecte incomplète")
            if verified_feed and any(not isinstance(item, dict) for item in rows):
                return found, ValueError("Annonce Workday invalide")
            signature = tuple(str(item.get("externalPath") or "") for item in rows)
            if rows and signature in seen_pages:
                return found, ValueError("Pagination Workday répétée")
            seen_pages.add(signature)
            for item in rows:
                if verified_feed and (not item.get("title")
                        or not str(item.get("externalPath") or "").startswith("/job/")):
                    invalid_row = True
                    continue
                path = str(item.get("externalPath") or "")
                if not path.startswith("/job/"):
                    continue
                title = str(item.get("title") or "")
                if company == "Citi" and re.search(r"\b(?:operations|reference data|product control)\b", title, re.I):
                    continue  # Operational programmes are not markets desk roles.
                job = _opportunity(
                    title, company, str(item.get("locationsText") or ""),
                    contract,
                    f"https://{host}/en-US/{site}{path}",
                    _workday_publication_date(posted_on=item.get("postedOn")),
                    defer_junior_context=True,
                )
                if job:
                    found.append((path, replace(job, source=f"Workday {company}")))
            if verified_feed and len(rows) < 20 and offset + len(rows) < total:
                return found, ValueError("Pagination Workday incomplète")
            if len(rows) < 20 or total and offset + len(rows) >= total:
                break
        else:
            return found, ValueError("Pagination Workday incomplète")
        return found, ValueError("Annonce Workday incomplète") if invalid_row else None

    candidates: dict[str, Opportunity] = {}
    search_errors: list[Exception] = []
    with ThreadPoolExecutor(max_workers=3 if company == "Citi" else 1) as pool:
        for result, error in pool.map(search, searches):
            candidates.update(result)
            if error:
                search_errors.append(error)
    if len(search_errors) == len(searches) and not candidates:
        raise search_errors[0]
    if http_pauses:
        reason, retry_at = _workday_pause_details(http_pauses)
        failure = _PartialSourceError([], [], search_failures=len(search_errors), retry_not_before=retry_at)
        failure.args = (f"{failure} · catalogue Workday {reason}",)
        raise failure

    failed_details: list[str] = []

    def enrich(pair: tuple[str, Opportunity]) -> Opportunity | None:
        path, job = pair
        reused = None if verified_feed else _cached_detail(job)
        if reused and reused.description and _display_offer_location(reused.location) != "Non précisé":
            return replace(reused, source=f"Workday career site · {company}")
        try:
            response = _workday_request(client.get, base + path, http_pauses, timeout=(8, 20))
            if getattr(response, "status_code", 200) in (404, 410):
                return None
            response.raise_for_status()
            detail = response.json()
            if verified_feed and (not isinstance(detail, dict)
                    or not isinstance(detail.get("jobPostingInfo"), dict)):
                raise ValueError("Fiche Workday invalide")
            info = detail.get("jobPostingInfo") or {}
            if info.get("canApply") is False:
                return None
            description = str(info.get("jobDescription") or "")
            location = str(info.get("location") or job.location)
            if verified_feed:
                if (info.get("canApply") is not True or not info.get("title")
                        or not description or not info.get("location")):
                    raise ValueError("Fiche Workday incomplète")
                if company in {"PIMCO", "Murex", "RBC Capital Markets"}:
                    locations = [location] + [place for place in (info.get("additionalLocations") or [])
                                              if isinstance(place, str) and place.strip()]
                    location = "; ".join(dict.fromkeys(locations))
                revised = _opportunity(str(info["title"]), company, location,
                    str(info.get("timeType") or ""), job.url,
                    _workday_publication_date(info.get("startDate"), info.get("postedOn")),
                    _start_period(description) or _title_period(str(info["title"])), role_context=_plain_text(description))
                if not revised:
                    return None
                deadline = str(info.get("validThrough") or "")[:10]
                try:
                    deadline = date.fromisoformat(deadline).isoformat()
                except ValueError:
                    deadline = ""
                # Workday startDate is the publication date; the programme dates
                # below are explicit employer text, never inferred from graduation.
                start = revised.start_period
                if company == "RBC Capital Markets":
                    published, deadline = _rbc_posting_dates(info, _plain_text(description))
                    revised = replace(revised, published=published)
                    cohort = re.search(r"\b(20\d{2})\b.*\bsummer\b", revised.title, re.I)
                    if not start and cohort:
                        start = f"Summer {cohort[1]}"
                program = re.search(r"Program(?:me)? dates?:\s*(?:\w+,\s*)?"
                    r"([A-Z][a-z]+)\s+(\d{1,2})\s*[-–—]\s*(?:\w+,\s*)?"
                    r"[A-Z][a-z]+\s+\d{1,2},?\s+(20\d{2})", _plain_text(description))
                if company == "TP ICAP" and not start and program:
                    try:
                        start = datetime.strptime(f"{program[1]} {program[2]} {program[3]}", "%B %d %Y").date().isoformat()
                    except ValueError:
                        pass
                return replace(revised, start_period=start, deadline=deadline,
                    family="Sales" if re.search(r"\bbroker(?:ing|s)?\b|\bbroking\b", revised.title, re.I) else revised.family,
                    description=_plain_text(description)[:12_000], source=f"Workday career site · {company}")
            if _display_offer_location(location) == "Non précisé":
                # Require a title city, an explicit workplace statement and a matching country.
                country = _LOCATION_COUNTRY_NAMES.get(_offer_search_text(
                    str((info.get("country") or {}).get("descriptor") or "")))
                title_text = _offer_search_text(job.title)
                detail_text = _offer_search_text(_plain_text(description))
                places = {f"{city}, {expected_country}" for pattern, city, expected_country in _LOCATION_CITY_PATTERNS
                          if expected_country == country and (match := pattern.search(title_text))
                          and re.search(r"\bbased in " + re.escape(match[0]) + r"\b", detail_text)}
                if len(places) == 1:
                    location = places.pop()
            if company == "Citi":
                # Some Workday locations are building names (e.g. TAURUS).
                # Use an explicit city in the title only when its country
                # matches Workday's structured country, never a guessed city.
                country = str((info.get("country") or {}).get("descriptor") or "")
                city = re.search(r",\s*([^,–]+?)\s*[–-]\s*" + re.escape(country)
                                 + r"(?:\s*[,–-]?\s*20\d{2})?\s*$", job.title, re.I) if country else None
                if city:
                    location = f"{city[1].strip()}, {country}"
            detail_company = job.company
            if re.search(r"Rothschild\s*&\s*Co\s+Redburn|\bRedburn\b", description, re.IGNORECASE):
                detail_company = "Rothschild & Co Redburn"
            elif re.search(r"Rothschild\s*&\s*Co\s+(?:Asset|Wealth) Management", description[:1_500], re.IGNORECASE):
                detail_company = "Rothschild & Co Asset Management"
            if _junior_analyst(job.title):
                revised = _opportunity(job.title, detail_company, location,
                    job.employment or "", job.url,
                    _workday_publication_date(info.get("startDate"), info.get("postedOn")) or job.published,
                    _start_period(description) or _title_period(job.title), role_context=_plain_text(description))
                return replace(revised, description=_plain_text(description)[:12_000],
                               source=f"Workday career site · {detail_company}") if revised else None
            return replace(
                job,
                company=detail_company,
                start_period=_start_period(description) or _title_period(job.title),
                location=location,
                published=_workday_publication_date(info.get("startDate"), info.get("postedOn")) or job.published,
                description=_plain_text(description)[:12_000],
                source=f"Workday career site · {detail_company}",
            )
        except (requests.RequestException, ValueError, TypeError):
            if verified_feed or _junior_analyst(job.title) or http_pauses:
                failed_details.append(job.url)
                return None
            return job

    selected = dict(sorted(candidates.items(), key=lambda pair: -pair[1].score)[:50])
    if company in {"Capital Group", "FactSet", "PIMCO", "Murex", "RBC Capital Markets", "S&P Global Market Intelligence", "LSEG", "Mizuho"}:
        selected = dict(candidates)  # Every offer needs a verified live detail.
    selected.update((path, job) for path, job in candidates.items() if _junior_analyst(job.title))
    selected = list(selected.items())
    with ThreadPoolExecutor(max_workers=1 if company == "BBVA" else 6) as pool:
        enriched = dict(zip((path for path, _ in selected), pool.map(enrich, selected)))
    jobs = [verified for path, job in candidates.items() if (verified := enriched.get(path, job)) is not None
            and _eligible_offer(verified)]
    if search_errors or failed_details:
        reason, retry_at = _workday_pause_details(http_pauses)
        failure = _PartialSourceError(jobs, failed_details, search_failures=len(search_errors),
                                      retry_not_before=retry_at)
        if reason or search_errors:
            failure.args = (f"{failure} · {reason or str(search_errors[0])[:90]}",)
        raise failure
    return jobs


def _ubs_opportunity(item: dict) -> Opportunity | None:
    fields = {str(q.get('QuestionName') or '').lower(): html.unescape(str(q.get('Value') or ''))
              for q in item.get('Questions', [])}
    url = str(item.get('Link') or '')
    if urlparse(url).hostname != 'jobs.ubs.com':
        return None
    description = _plain_text(fields.get('jobdescription', ''))
    job = _opportunity(fields.get('jobtitle', ''), 'UBS', fields.get('formtext23', ''), '', url, '',
                       _start_period(description), role_context=description)
    # lastupdated is an update date, not evidence of publication or contract start.
    return replace(job, description=description[:12_000], source='Site carrière · UBS') if job else None


def _ubs_jobs(_slug: str = '', _company: str = '') -> list[Opportunity]:
    """Read the public early-career board and its ordinary Next control, without login."""
    from playwright.sync_api import sync_playwright, TimeoutError as BrowserTimeout
    jobs: dict[str, Opportunity] = {}
    seen: set[str] = set()
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                response = page.goto('https://jobs.ubs.com/TGnewUI/Search/Home/Home?partnerid=25008&siteid=5131',
                                     wait_until='domcontentloaded', timeout=30_000)
                if response is not None and response.status >= 400:
                    raise ValueError(f'Catalogue UBS en HTTP {response.status}')
                decline = page.get_by_text('Decline all', exact=True)
                try:
                    decline.wait_for(state='visible', timeout=5000)
                    decline.click()
                except BrowserTimeout:
                    pass
                def search_response(response):
                    parsed = urlparse(response.url)
                    return parsed.hostname == 'jobs.ubs.com' and parsed.path.rsplit('/', 1)[-1] in {
                        'MatchedJobs', 'ProcessSortAndShowMoreJobs'}
                with page.expect_response(search_response, timeout=25_000) as first:
                    page.get_by_role('button', name='Search', exact=True).click(timeout=15_000)
                payload = first.value.json()
                total = int(payload['JobsCount'])
                for _ in range(20):
                    total = int(payload.get('JobsCount', total))
                    rows = (payload.get('Jobs') or {}).get('Job') or []
                    if not isinstance(rows, list):
                        raise ValueError('Format du catalogue UBS inattendu')
                    before = len(seen)
                    for row in rows:
                        url = str(row.get('Link') or '')
                        if url:
                            seen.add(url)
                        job = _ubs_opportunity(row)
                        if job:
                            jobs[job.url] = job
                    if len(seen) >= total:
                        return list(jobs.values())
                    if len(seen) == before:
                        raise ValueError('Pagination UBS sans nouveaux résultats')
                    with page.expect_response(search_response, timeout=25_000) as next_page:
                        page.locator('#showMoreJobs').click(timeout=10_000)
                    payload = next_page.value.json()
                raise ValueError('Limite de pagination UBS atteinte')
            finally:
                browser.close()
    except Exception as exc:
        if jobs:
            raise _PartialSourceError(list(jobs.values()), [], search_failures=1) from exc
        raise ValueError(f'Catalogue public UBS indisponible ({type(exc).__name__})') from exc


def _banque_de_france_jobs(_slug: str = "", _company: str = "") -> list[Opportunity]:
    """The Banque de France lists contract type only on Workday detail pages."""
    host, tenant, site = "bdf.wd103.myworkdayjobs.com", "bdf", "recrutement-banque-de-France"
    base = f"https://{host}/wday/cxs/{tenant}/{site}"
    candidates: dict[str, tuple[str, str, str]] = {}
    http_pauses: list[requests.HTTPError] = []
    failed_urls: list[str] = []
    for term in ("march", "quant", "trading", "ALM"):
        offset, total = 0, 0
        seen: set[str] = set()
        while True:
            response = _workday_request(requests.post, base + "/jobs", http_pauses, json={
                "appliedFacets": {}, "limit": 20, "offset": offset, "searchText": term,
            }, timeout=(8, 20))
            response.raise_for_status()
            payload = response.json()
            rows = payload.get("jobPostings") or []
            total = max(total, int(payload.get("total") or 0))
            identities = {str(item.get("externalPath") or "") for item in rows}
            if rows and (not identities - seen or "" in identities):
                raise ValueError("Pagination Banque de France sans progression")
            seen.update(identities)
            if not rows and len(seen) < total:
                raise ValueError("Catalogue Banque de France incomplet")
            for item in rows:
                path = str(item.get("externalPath") or "")
                title = str(item.get("title") or "")
                if path.startswith("/job/") and (_market_relevant(title) or "analyste des marchés" in title.casefold()):
                    candidates[path] = (title, str(item.get("locationsText") or ""),
                                        str(item.get("postedOn") or ""))
            if not rows or total and len(seen) >= total:
                break
            offset += len(rows)

    def load(pair: tuple[str, tuple[str, str, str]]) -> Opportunity | None:
        path, (title, location, posted_on) = pair
        url = f"https://{host}/fr-FR/{site}{path}"
        try:
            response = _workday_request(requests.get, base + path, http_pauses, timeout=(8, 20))
            if getattr(response, "status_code", 200) in (404, 410):
                return None
            response.raise_for_status()
            info = response.json().get("jobPostingInfo") or {}
            description = _plain_text(str(info.get("jobDescription") or ""))
            if not re.search(r"Type de recrutement\s*:[\s\u200e\u200f]*Stage\b", description, re.IGNORECASE):
                return None
            job = _opportunity(title, "Banque de France", str(info.get("location") or location),
                               "Stage", url,
                               _workday_publication_date(info.get("startDate"), info.get("postedOn") or posted_on),
                               _start_period(description), description)
            return replace(job, description=description[:12_000], source="Site carrière · Banque de France") if job else None
        except (requests.RequestException, ValueError, TypeError):
            failed_urls.append(url)
            return None

    with ThreadPoolExecutor(max_workers=6) as pool:
        jobs = [job for job in pool.map(load, candidates.items()) if job]
    if failed_urls:
        reason, retry_at = _workday_pause_details(http_pauses)
        failure = _PartialSourceError(jobs, failed_urls, retry_not_before=retry_at)
        if reason:
            failure.args = (f"{failure} · fiches Workday {reason}",)
        raise failure
    return jobs


def _oracle_jobs(board_name: str, board: tuple[str, str, str]) -> list[Opportunity]:
    """Read public Oracle Candidate Experience postings and their public details."""
    root, site, employer = board
    board_url = f"{root}/hcmUI/CandidateExperience/en/sites/{site}/jobs"
    endpoint = f"{root}/hcmRestApi/resources/11.13.18.05/recruitingCEJobRequisitions"
    session = requests.Session()
    session.headers.update({"Accept": "application/json", "User-Agent": "MarketsCareerDesk/1.0"})
    response = session.get(board_url, timeout=(8, 20))
    response.raise_for_status()
    site_number_match = re.search(
        r"(?:siteNumber|site_number)\s*[\"']?\s*[:=]\s*[\"']?([A-Za-z0-9_-]+)",
        response.text, re.IGNORECASE,
    )
    site_number = site_number_match.group(1) if site_number_match else site

    def requisitions(offset: int) -> tuple[list[dict], int, int]:
        response = session.get(endpoint, params={
            "onlyData": "true", "expand": "requisitionList",
            "finder": f"findReqs;siteNumber={site_number},limit=100,offset={offset}",
        }, timeout=(8, 20))
        response.raise_for_status()
        payload = response.json()
        items = payload.get("items") or []
        rows = items[0].get("requisitionList") or [] if items and isinstance(items[0], dict) else []
        if isinstance(rows, dict):
            rows = rows.get("items") or []
        if not rows:
            rows = payload.get("requisitionList") or []
        total = int((items[0].get("TotalJobsCount") if items and isinstance(items[0], dict) else 0)
                    or payload.get("TotalJobsCount") or len(rows))
        metadata = items[0] if items and isinstance(items[0], dict) else payload
        # Oracle can hide closed rows inside a page; Offset/Limit still count those slots.
        page_size = metadata.get("Limit")
        if isinstance(page_size, int) and page_size > 0:
            if metadata.get("Offset", offset) != offset:
                raise ValueError("Position de page Oracle incohérente")
            return rows, total, offset + page_size
        return rows, total, offset + len(rows)

    candidates: dict[str, tuple[Opportunity, str]] = {}
    offset, total = 0, 0
    seen: set[str] = set()
    while True:
        rows, reported_total, next_offset = requisitions(offset)
        total = max(total, reported_total)
        identities = {str(row.get("Id") or row.get("RequisitionId") or "") for row in rows}
        if rows and (not identities - seen or "" in identities):
            raise ValueError("Pagination Oracle sans progression")
        seen.update(identities)
        if not rows and offset < total and next_offset <= offset:
            raise ValueError("Catalogue Oracle incomplet")
        for row in rows:
            title = str(row.get("Title") or row.get("JobTitle") or "").strip()
            location = str(row.get("PrimaryLocation") or row.get("Location") or "").strip()
            job_id = str(row.get("Id") or row.get("RequisitionId") or "").strip()
            if not title or not job_id:
                continue
            direct_url = str(row.get("ExternalUrlSeo") or row.get("ExternalUrl") or "").strip()
            if direct_url.startswith("/"):
                direct_url = urljoin(f"{root}/hcmUI/CandidateExperience/en/sites/{site}/", direct_url)
            if not direct_url:
                direct_url = f"{root}/hcmUI/CandidateExperience/en/sites/{site}/job/{job_id}/"
            short_description = str(row.get("ExternalDescription") or row.get("ShortDescription") or row.get("ShortDescriptionStr") or "")
            description_text = _plain_text(short_description)
            description_fold = unicodedata.normalize("NFKD", description_text).encode("ascii", "ignore").decode().casefold()
            employer_context = description_fold[:1_200]
            actual_employer = ("Lazard Asset Management" if "lazard asset management" in employer_context
                               else "Lazard Freres Gestion" if "lazard freres gestion" in employer_context
                               else employer)
            job = _opportunity(
                title, actual_employer, location,
                str(row.get("WorkerType") or row.get("ContractType") or ""),
                direct_url, str(row.get("PostedDate") or row.get("PostingStartDate") or ""),
                _start_period(description_text) or _title_period(title), role_context=description_text,
                defer_junior_context=True,
            )
            if job:
                job = replace(job, description=description_text[:12_000])
                candidates[job_id] = (replace(job, source=f"Site carrière · Oracle · {board_name}"), description_text)
        if next_offset >= total:
            break
        offset = next_offset

    def enrich(item: tuple[str, tuple[Opportunity, str]]) -> Opportunity:
        job_id, (job, existing_description) = item
        reused = _cached_detail(job)
        if reused and reused.description:
            return reused
        detail_url = f"{root}/hcmRestApi/resources/11.13.18.05/recruitingCEJobRequisitionDetails"
        try:
            response = session.get(detail_url, params={"onlyData": "true", "expand": "all",
                                                       "finder": f"ById;Id={job_id},siteNumber={site_number}"},
                                   timeout=(8, 20))
            response.raise_for_status()
            payload = response.json()
            nodes = [payload]
            while nodes:
                node = nodes.pop()
                if isinstance(node, list):
                    nodes.extend(node)
                elif isinstance(node, dict):
                    nodes.extend(value for value in node.values() if isinstance(value, (dict, list)))
                    for key in ("ExternalDescription", "JobDescription", "Description", "ShortDescription", "ExternalDescriptionStr"):
                        value = node.get(key)
                        if isinstance(value, str) and len(_plain_text(value)) > len(existing_description):
                            existing_description = _plain_text(value)
            description = existing_description[:12_000]
            detail_company = job.company
            description_fold = unicodedata.normalize("NFKD", description).encode("ascii", "ignore").decode().casefold()
            if re.search(r"lazard asset management|lazard freres gestion", description_fold[:1_200], re.IGNORECASE):
                detail_company = "Lazard Asset Management" if "asset management" in description_fold else "Lazard Freres Gestion"
            return replace(job, company=detail_company, description=description,
                           start_period=_start_period(description) or job.start_period)
        except (requests.RequestException, ValueError, TypeError):
            return replace(job, description=existing_description[:12_000])

    selected = dict(list(candidates.items())[:60])
    selected.update((job_id, item) for job_id, item in candidates.items() if _junior_analyst(item[0].title))
    selected = list(selected.items())
    with ThreadPoolExecutor(max_workers=6) as pool:
        enriched = dict(zip((job_id for job_id, _ in selected), pool.map(enrich, selected)))
    return [job for job_id, item in candidates.items()
            if _eligible_offer(job := enriched.get(job_id, item[0]))]


def _vie_jobs(_slug: str = "", _company: str = "") -> list[Opportunity]:
    """Use the official feed when configured, plus dated verified public offers."""
    today = datetime.now(timezone.utc).date()
    jobs: list[Opportunity] = []
    key = os.getenv("VIE_API_KEY", "").strip()
    if key:
        endpoint = "https://civiweb-api-prd.azurewebsites.net/api/Offers/search"
        def search(term: str) -> list[dict]:
            response = requests.post(
                endpoint, headers={"X-API-KEY": key},
                json={"limit": 100, "skip": 0, "query": term, "teletravail": [], "porteEnv": [],
                      "activitySectorId": [], "missionsTypesIds": [], "missionsDurations": [],
                      "geographicZones": [], "countriesIds": [], "studiesLevelId": [],
                      "companiesSizes": [], "specializationsIds": [], "entreprisesIds": [],
                      "missionStartDate": None},
                timeout=(8, 20),
            )
            response.raise_for_status()
            payload = response.json()
            return payload if isinstance(payload, list) else payload.get("result", [])

        with ThreadPoolExecutor(max_workers=4) as pool:
            results = pool.map(search, ("trading", "market", "sales", "risk"))
            for rows in results:
                for item in rows:
                    if "vie" not in str(item.get("missionType") or "").casefold().replace(".", ""):
                        continue
                    offer_id = item.get("id")
                    if not str(offer_id).isdigit():
                        continue
                    location = ", ".join(filter(None, (str(item.get("cityName") or ""),
                                                       str(item.get("countryName") or ""))))
                    job = _opportunity(
                        str(item.get("missionTitle") or ""), str(item.get("organizationName") or ""),
                        location, "VIE", f"https://mon-vie-via.businessfrance.fr/offres/{offer_id}",
                        str(item.get("publicationDate") or ""), str(item.get("missionStartDate") or ""),
                    )
                    if job:
                        jobs.append(job)
    for offer_id, title, company, city, expiry, start in VIE_SEEDS:
        if date.fromisoformat(expiry) < today:
            continue
        job = _opportunity(
            title, company, city, "VIE",
            f"https://mon-vie-via.businessfrance.fr/en/offres/{offer_id}", "", start,
        )
        if job:
            jobs.append(replace(job, deadline=expiry))
    return list({job.url: job for job in jobs}.values())


def _source_cache_path() -> Path:
    return CACHE_PATH.with_name("internships_source_cache.json")


def _load_source_job_cache() -> None:
    global _source_job_cache, _source_job_cache_path
    path = _source_cache_path()
    with _source_cache_lock:
        if _source_job_cache_path == path:
            return
        _source_job_cache_path = path
        _source_job_cache = {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if payload.get("version") != 1 or not isinstance(payload.get("sources"), dict):
                return
            for name, item in payload["sources"].items():
                if not isinstance(item, dict) or not isinstance(item.get("jobs"), list):
                    continue
                try:
                    jobs = [Opportunity(**row) for row in item["jobs"] if isinstance(row, dict)]
                    updated = str(item.get("updated") or "")
                    if updated:
                        datetime.fromisoformat(updated)
                except (TypeError, ValueError):
                    continue
                _source_job_cache[str(name)] = {
                    "updated": updated, "jobs": jobs,
                    "check": item.get("check") if isinstance(item.get("check"), dict) else {},
                    "connector_version": int(item.get("connector_version") or 1),
                }
        except (OSError, ValueError, TypeError):
            return


def _write_source_job_cache() -> None:
    path = _source_cache_path()
    with _source_cache_lock:
        payload = {
            "version": 1,
            "sources": {
                name: {"updated": item["updated"], "jobs": [asdict(job) for job in item["jobs"]],
                       "check": item.get("check") or {},
                       "connector_version": item.get("connector_version", 1)}
                for name, item in _source_job_cache.items()
            },
        }
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(".tmp")
            temporary.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            temporary.replace(path)
        except OSError:
            pass


def _source_refresh_seconds(name: str, loader: object) -> int:
    """Give dynamic feeds hourly checks and expensive or low-change pages longer intervals."""
    configured = os.environ.get("INTERNSHIPS_SOURCE_CACHE_SECONDS")
    if configured:
        return max(300, int(configured))
    if name == "JobTeaser · sitemap":
        return JOBTEASER_CACHE_SECONDS
    if name in {"BNP Paribas", "BNP Paribas VIE", "BNP Paribas Asset Management", "ODDO BHF", "Tikehau Capital"}:
        return 4 * 3600
    if name in {"Comgest", "Groupama AM", "Cov\u00e9a Finance", "BPCE Open Data",
                "Cr\u00e9dit Mutuel Ark\u00e9a", "Amundi", "Cr\u00e9dit Agricole CIB"} or loader in {
            _career_page_jobs, _career_rss_jobs, _comgest_jobs, _groupama_am_jobs}:
        return 3 * 3600
    return CACHE_REFRESH_SECONDS


def _http_retry_not_before(error: Exception) -> str:
    """Convert an employer's Retry-After to a persistent UTC deadline."""
    response = getattr(error, 'response', None)
    if response is None or response.status_code not in (429, 503):
        return ""
    raw = str(getattr(response, 'headers', {}).get('Retry-After') or '').strip()
    now = datetime.now(timezone.utc)
    try:
        if re.fullmatch(r'[0-9]+', raw):
            deadline = now + timedelta(seconds=int(raw))
        else:
            deadline = parsedate_to_datetime(raw)
            if deadline.tzinfo is None:
                return ""
        return deadline.astimezone(timezone.utc).isoformat() if deadline > now else ""
    except (ValueError, TypeError, OverflowError):
        return ""


def _source_retry_metadata(previous_check: dict, checked_at: str, *, retry_not_before: str = "") -> dict:
    """Back off automatic retries; an explicit refresh may retry immediately."""
    try:
        failures = max(1, int(previous_check.get("failure_count", 0)) + 1)
    except (TypeError, ValueError):
        failures = 1
    delay = min(SOURCE_RETRY_MAX_SECONDS,
                SOURCE_RETRY_BASE_SECONDS * (2 ** min(failures - 1, 10)))
    retry_at = datetime.fromisoformat(checked_at) + timedelta(seconds=delay)
    if retry_not_before:
        retry_at = max(retry_at, datetime.fromisoformat(retry_not_before))
    metadata = {"failure_count": failures, "next_retry_at": retry_at.isoformat()}
    if retry_not_before:
        metadata['retry_not_before'] = retry_not_before
    return metadata


def _remember_source_failure(name: str, cached: dict | None, check: dict,
                             connector_version: int) -> None:
    """Persist failure timing while preserving the last successful offer snapshot."""
    with _source_cache_lock:
        _source_job_cache[name] = {
            "updated": str((cached or {}).get("updated") or ""),
            "jobs": list((cached or {}).get("jobs") or []),
            "check": check,
            "connector_version": connector_version,
        }


def _collect_source(name: str, loader: object, args: tuple, force: bool) -> tuple[list[Opportunity], dict, str]:
    """Fetch one connector, timing it and serving its own cache if fresh or temporarily stale."""
    _load_source_job_cache()
    with _source_cache_lock:
        cached = _source_job_cache.get(name)
        cached = dict(cached) if cached else None
    connector_version = SOURCE_CONNECTOR_VERSIONS.get(name, 1)
    connector_version_changed = bool(
        cached and cached.get("connector_version", 1) != connector_version
    )
    now = datetime.now(timezone.utc)
    previous_check = dict((cached or {}).get("check") or {})
    cached_jobs = list((cached or {}).get("jobs") or [])
    cached_at: datetime | None = None
    try:
        cached_at = datetime.fromisoformat(str((cached or {}).get("updated") or ""))
        if cached_at.tzinfo is None:
            cached_at = cached_at.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        pass
    # An explicit employer pause also applies to manual refreshes and new code.
    try:
        server_retry = datetime.fromisoformat(str(previous_check.get('retry_not_before') or ''))
        if server_retry.tzinfo is not None and server_retry > now:
            check = {**previous_check, 'cache_status': 'backoff', 'duration_ms': 0}
            return cached_jobs, check, f"{name}: nouvel essai différé par la source"
    except (TypeError, ValueError):
        pass
    if not force and not connector_version_changed:
        try:
            retry_at = datetime.fromisoformat(str(previous_check.get("next_retry_at") or ""))
            if retry_at.tzinfo is None:
                retry_at = retry_at.replace(tzinfo=timezone.utc)
        except (TypeError, ValueError):
            retry_at = None
        if retry_at and retry_at > now:
            check = dict(previous_check)
            check["cache_status"] = "backoff"
            check["duration_ms"] = 0
            reason = str(check.get("error") or "source temporairement indisponible")
            return cached_jobs, check, f"{name}: {reason} (nouvel essai différé)"
    if (not force and not connector_version_changed and cached_at
            and previous_check.get("status") not in {"error", "stale"} and
            (now - cached_at).total_seconds() < _source_refresh_seconds(name, loader)):
        check = previous_check or {
            "status": "ok" if cached_jobs else "empty", "count": len(cached_jobs),
            "checked_at": cached_at.isoformat(), "last_success": cached_at.isoformat(),
            "error": "", "duration_ms": None,
        }
        check.update({"cache_status": "fresh"})
        return cached_jobs, check, ""

    started = time.perf_counter()
    try:
        found = loader(*args)
        elapsed = round((time.perf_counter() - started) * 1000)
        checked_at = datetime.now(timezone.utc).isoformat()
        check = {"status": "ok" if found else "empty", "count": len(found),
                 "checked_at": checked_at, "last_success": checked_at, "error": "",
                 "duration_ms": elapsed, "cache_status": "live"}
        with _source_cache_lock:
            _source_job_cache[name] = {"updated": checked_at, "jobs": list(found), "check": check,
                                       "connector_version": connector_version}
        return list(found), check, ""
    except _PartialSourceError as exc:
        # Only restore offers that the current public listing still advertises.
        # Removed offers and successfully parsed but irrelevant roles stay removed.
        retained = {job.url: job for job in exc.jobs}
        for job in cached_jobs:
            if exc.preserve_cached or job.url in exc.failed_urls:
                retained.setdefault(job.url, job)
        found = list(retained.values())
        checked_at = datetime.now(timezone.utc).isoformat()
        reason = str(exc)
        check = {"status": "stale", "count": len(found), "checked_at": checked_at,
                 "last_success": str((cached or {}).get("updated") or ""), "error": reason,
                 "duration_ms": round((time.perf_counter() - started) * 1000), "cache_status": "partial",
                 **_source_retry_metadata(previous_check, checked_at, retry_not_before=exc.retry_not_before)}
        # Persist verified partial results too, without advancing the last full success.
        # Otherwise a first partial collection disappears on restart/backoff.
        partial_cache = {**(cached or {}), "jobs": found}
        _remember_source_failure(name, partial_cache, check, connector_version)
        return found, check, f"{name}: {reason}"
    except Exception as exc:
        elapsed = round((time.perf_counter() - started) * 1000)
        if isinstance(exc, requests.HTTPError) and exc.response is not None:
            reason = f"HTTP {exc.response.status_code}"
        elif isinstance(exc, requests.Timeout):
            reason = "délai dépassé"
        elif isinstance(exc, requests.ConnectionError):
            reason = "connexion interrompue"
        elif isinstance(exc, ValueError):
            reason = str(exc)[:90] or "réponse invalide"
        else:
            reason = type(exc).__name__
        checked_at = datetime.now(timezone.utc).isoformat()
        retry = _source_retry_metadata(previous_check, checked_at, retry_not_before=_http_retry_not_before(exc))
        if cached_jobs:
            check = {"status": "stale", "count": len(cached_jobs), "checked_at": checked_at,
                     "last_success": str((cached or {}).get("updated") or ""), "error": reason,
                     "duration_ms": elapsed, "cache_status": "stale", **retry}
            _remember_source_failure(name, cached, check, connector_version)
            return cached_jobs, check, f"{name}: {reason} (anciennes offres conservées)"
        check = {"status": "error", "count": None, "checked_at": checked_at,
                 "last_success": previous_check.get("last_success", ""), "error": reason,
                 "duration_ms": elapsed, "cache_status": "none", **retry}
        _remember_source_failure(name, cached, check, connector_version)
        return [], check, f"{name}: {reason}"


def _merge_duplicate_publication(preferred: Opportunity, other: Opportunity) -> Opportunity:
    """Keep a valid confirmed date, or the earliest detection, for one vacancy."""
    valid = [job for job in (preferred, other) if _publication_sort_value(job.published)]
    confirmed = [job for job in valid if not job.published_inferred]
    if confirmed:
        publication = confirmed[0]
    elif valid:
        publication = min(valid, key=lambda job: job.published)
    else:
        return preferred
    return replace(preferred, published=publication.published,
                   published_inferred=publication.published_inferred)


def _eligible_offer(job: Opportunity) -> bool:
    """Apply the same role and contract checks to live results and saved snapshots."""
    try:
        if job.deadline and date.fromisoformat(job.deadline[:10]) < datetime.now(timezone.utc).date():
            return False
    except ValueError:
        pass
    if job.employment is not None:
        kind = (_tp_icap_kind(job.title, job.employment, job.description) if job.company == "TP ICAP" else
                _factset_kind(job.title, job.employment, job.description)
                if job.company == "FactSet" or job.company in FINANCIAL_DATA_EMPLOYERS else
                _morgan_stanley_kind(job.title, job.employment, job.description)
                if job.company == "Morgan Stanley" else _kind(job.title, job.employment))
        if kind != job.kind:
            return False
    if job.employment is None and _kind(job.title) is None and re.search(
        r"\b(?:internal|international|senior|vice president|executive director)\b", job.title, re.I
    ):
        # Legacy snapshots did not retain contract evidence. These titles could
        # be admitted by the old substring/whole-page contract heuristics.
        return False
    return (not _excluded_employer(job.company)
            and not (job.kind == "Graduate" and _junior_analyst(job.title) and _experienced_junior(job.description))
            and (_rbc_relevant(job.title, job.description) if job.company == "RBC Capital Markets" else
                 _murex_relevant(job.title, job.description) if job.company == "Murex" else
                 _pimco_relevant(job.title, job.description) if job.company == "PIMCO" else
                 _market_relevant_with_context(job.title, job.description)
                 or (job.company == "FactSet" or job.company in FINANCIAL_DATA_EMPLOYERS)
                 and _factset_client_solutions(job.title))
            and (job.source == "JobTeaser · sitemap" or _plausible_location(job.location)))


def _deduplicate_opportunities(jobs: list[Opportunity]) -> list[Opportunity]:
    # Only usable direct postings may replace a JobTeaser fallback. Otherwise
    # a rejected employer result can suppress the only offer we can display.
    jobs = [replace(job, location=_clean_job_location(job.location, job.title)) for job in jobs]
    jobs = [job for job in jobs if _eligible_offer(job)]
    grouped: dict[tuple[str, str, str, str, str], list[Opportunity]] = {}
    for job in _without_jobteaser_duplicates(jobs):
        location_key = "paris-area" if _is_paris(job.location) else _canonical_location(job.location)
        # Identical role names can advertise separate internship, VIE or work-study contracts.
        # These employers publish distinct requisitions with identical titles/cohorts.
        # A repeated requisition may collapse; different employer IDs must survive.
        requisition = (re.search(r"_(R\d+)(?:-\d+)?$", urlparse(job.url).path)
                       if _canonical_company(job.company) == "factset" else None)
        if _canonical_company(job.company) == "murex":
            requisition = re.search(r"_(JR\d+)(?:-\d+)?$", urlparse(job.url).path)
        if _canonical_company(job.company) == "rbccapitalmarkets":
            requisition = re.search(r"_(R-\d+)(?:-\d+)?$", urlparse(job.url).path)
        greenhouse_board = {"drw": "drweng", "fiverings": "fiveringsllc",
                            "jumptrading": "jumptrading"}.get(_canonical_company(job.company))
        if greenhouse_board:
            requisition = re.fullmatch(rf"/{greenhouse_board}/jobs/([1-9][0-9]*)/?", urlparse(job.url).path)
        key = (_canonical_title(job.title), _canonical_company(job.company), location_key, job.kind,
               requisition[1] if requisition else "")
        grouped.setdefault(key, []).append(job)
    deduplicated: list[Opportunity] = []
    for group in grouped.values():
        months = {month for job in group if (month := start_month(job.start_period))}
        unique: dict[str, Opportunity] = {}
        for job in group:
            # An unknown start can join one known cohort, but must not join two
            # different cohorts or make their survival depend on source order.
            month = start_month(job.start_period)
            if not month and len(months) == 1:
                month = next(iter(months))
            previous = unique.get(month)
            if previous is None or (_is_jobteaser(previous) and not _is_jobteaser(job)) or (
                previous.source == job.source and not previous.start_period and job.start_period
            ) or (previous.source == job.source and not previous.description and job.description):
                if previous is not None and previous.source == job.source:
                    job = replace(job, start_period=job.start_period or previous.start_period,
                                  description=job.description or previous.description)
                preferred, other = job, previous
            else:
                preferred, other = previous, job
            # Cohort grouping above makes a known start safe to share across
            # sources without changing the selected posting or its provenance.
            if other is not None and not preferred.start_period and start_month(other.start_period):
                preferred = replace(preferred, start_period=other.start_period)
            unique[month] = (_merge_duplicate_publication(preferred, other)
                             if other is not None else preferred)
        deduplicated.extend(unique.values())
    return sorted(deduplicated, key=_opportunity_sort_key)


def _date_detected_offer(job: Opportunity, previous: Opportunity | None, today: date) -> Opportunity:
    """Use only valid calendar dates for publication and first detection."""
    earlier = [value for value in (_refresh_first_seen.get(job.url, ""),
                                   previous.published if previous else "")
               if _publication_sort_value(value)]
    if _publication_sort_value(job.published) and not job.published_inferred:
        first_seen = min(earlier, default=job.published)
        if first_seen < job.published:
            confirmed_previous = previous and not previous.published_inferred and previous.published == first_seen
            job = replace(job, published=first_seen, published_inferred=not confirmed_previous)
        _refresh_first_seen[job.url] = min(_refresh_first_seen.get(job.url, job.published), job.published)
        return job
    if previous and _publication_sort_value(previous.published) and not previous.published_inferred:
        first_seen = min(_refresh_first_seen.get(job.url, previous.published), previous.published)
        _refresh_first_seen[job.url] = first_seen
        return replace(job, published=first_seen, published_inferred=first_seen < previous.published)
    candidates = [value for value in (job.published, previous.published if previous else "",
                                      _refresh_first_seen.get(job.url, ""))
                  if _publication_sort_value(value)]
    first_seen = min(candidates, default=today.isoformat())
    _refresh_first_seen[job.url] = first_seen
    return replace(job, published=first_seen, published_inferred=True)


def _publish_refresh_progress(completed_jobs: list[Opportunity], errors: list[str]) -> None:
    """Make completed source results visible while slower connectors continue running."""
    global _cache
    merged = {job.url: job for job in _refresh_previous_jobs.values()}
    merged.update({job.url: job for job in completed_jobs})
    dated: list[Opportunity] = []
    now = _last_attempt or datetime.now(timezone.utc)
    for job in _deduplicate_opportunities(list(merged.values())):
        previous = _refresh_previous_jobs.get(job.url)
        dated.append(_date_detected_offer(job, previous, now.date()))
    snapshot = (now, sorted(dated, key=_opportunity_sort_key), list(errors))
    with _lock:
        _cache = snapshot
    _write_cache(*snapshot)



def _opportunity_source_tasks() -> list[tuple[str, object, tuple]]:
    """Share the configured collectors with the public source inventory."""
    tasks: list[tuple[str, object, tuple]] = []
    for slug, company in SMARTRECRUITERS.items():
        tasks.append((company, _smart_jobs, (slug, company)))
    for slug, company in GREENHOUSE.items():
        tasks.append((company, _greenhouse_jobs, (slug, company)))
    for slug, company in LEVER.items():
        tasks.append((company, _lever_jobs, (slug, company)))
    for slug, company in ASHBY.items():
        tasks.append((company, _ashby_jobs, (slug, company)))
    tasks.extend([
        ("Optiver", _optiver_jobs, ("", "")),
        ("Susquehanna", _susquehanna_jobs, ("", "")),
        ("Bloomberg", _bloomberg_jobs, ("", "")),
        ("Morgan Stanley", _morgan_stanley_jobs, ("", "")),
        ("Morgan Stanley Campus", _morgan_stanley_campus_jobs, ()),
        ("Bank of America", _bofa_jobs, ("", "")),
        ("UBS", _ubs_jobs, ("", "")),
        ("Pictet Asset Management", _pictet_jobs, ()),
        ("Soci\u00e9t\u00e9 G\u00e9n\u00e9rale Careers", _socgen_jobs, ("", "")),
        ("Business France VIE", _vie_jobs, ("", "")),
        ("Cr\u00e9dit Agricole CIB", _ca_cib_jobs, ("", "")),
        ("BNP Paribas CIB", _bnp_cib_jobs, ("", "")),
        ("BNP Paribas Graduate", _bnp_graduate_jobs, ("", "")),
        ("BNP Paribas APAC", _bnp_tal_jobs, ("", "")),
        ("BNP Paribas", lambda *_: _bnp_group_jobs(
            "BNP Paribas", "https://group.bnpparibas/emploi-carriere/toutes-offres-emploi/stage"), ()),
        ("BNP Paribas VIE", lambda *_: _bnp_group_jobs(
            "BNP Paribas", "https://group.bnpparibas/emploi-carriere/toutes-offres-emploi/vie"), ()),
        ("BNP Paribas Asset Management", lambda *_: _bnp_group_jobs(
            "BNP Paribas Asset Management",
            "https://group.bnpparibas/emploi-carriere/toutes-offres-emploi/bnp-paribas-asset-management"), ()),
        ("Banque de France", _banque_de_france_jobs, ("", "")),
        ("Amundi", _amundi_jobs, ("", "")),
        ("Cr\u00e9dit Mutuel Ark\u00e9a", _arkea_jobs, ("", "")),
        ("Cov\u00e9a Finance", _covea_finance_jobs, ("", "")),
        ("Comgest", _comgest_jobs, ("", "")),
        ("DNCA", _dnca_jobs, ("", "")),
        ("Candriam", _candriam_jobs, ("", "")),
        ("Commerzbank", _commerzbank_jobs, ("", "")),
        ("Standard Chartered", _standard_chartered_jobs, ("", "")),
        ("BPCE Open Data", _bpce_open_data_jobs, ("", "")),
        ("Ostrum AM", _subsidiary_jobs, ("Ostrum AM",)),
        ("Mirova", _subsidiary_jobs, ("Mirova",)),
        ("CPR AM", _subsidiary_jobs, ("CPR AM",)),
        ("ICE Data Services", _ice_data_jobs, ()),
        ("La Banque Postale AM", _lbpam_jobs, ()),
        ("Market Securities", _market_securities_jobs, ()),
        ("JobTeaser \u00b7 sitemap", _jobteaser_jobs, ("", "")),
        ("ODDO BHF", lambda *_: _oddo_jobs(), ()),
        ("Tikehau Capital", lambda *_: _tikehau_jobs(), ()),
        ("Groupama AM", lambda *_: _groupama_am_jobs(), ()),
        ("AXA", lambda *_: _axa_jobs(), ()),
    ])
    tasks.extend((company, _workday_jobs, (company, board)) for company, board in WORKDAY.items())
    tasks.extend((name, _oracle_jobs, (name, board)) for name, board in ORACLE_CAREER_BOARDS.items())
    tasks.extend((company, _career_page_jobs, (company, config))
                 for company, config in CAREER_LISTINGS.items())
    return tasks


def _fetch_opportunities_progressive() -> tuple[list[Opportunity], list[str]]:
    """Publish the first results immediately, then batch progress writes once a second."""
    global _source_counts, _source_checks
    tasks = _opportunity_source_tasks()

    with _lock:
        checks = {name: dict(check) for name, check in _source_checks.items()}
    collected: list[Opportunity] = []
    errors: list[str] = []
    counts: dict[str, int] = {}
    last_published: float | None = None
    # Limit overlapping public requests (some connectors also fetch job details)
    # so rate-limited career sites stay responsive; completed feeds stay visible.
    # Source collection is I/O-bound and each connector already caps its own
    # detail requests. Eight workers reduce queueing across the many independent
    # career boards while keeping outbound concurrency bounded.
    with ThreadPoolExecutor(max_workers=SOURCE_COLLECTION_WORKERS, thread_name_prefix="internships") as pool:
        futures = {pool.submit(_collect_source, name, loader, args, _force_source_refresh): name
                   for name, loader, args in tasks}
        for completed, future in enumerate(as_completed(futures), start=1):
            name = futures[future]
            try:
                found, check, error = future.result()
            except Exception as exc:
                found = []
                error = f"{name}: {type(exc).__name__}"
                check = {"status": "error", "count": None,
                         "checked_at": datetime.now(timezone.utc).isoformat(),
                         "last_success": checks.get(name, {}).get("last_success", ""),
                         "error": type(exc).__name__, "duration_ms": None, "cache_status": "none"}
            counts[name] = len(found)
            checks[name] = check
            if error:
                errors.append(error)
            collected.extend(found)
            with _lock:
                _source_counts = dict(counts)
                _source_checks = {key: dict(value) for key, value in checks.items()}
            now = time.perf_counter()
            if last_published is None or now - last_published >= 1 or completed == len(futures):
                _publish_refresh_progress(collected, errors)
                last_published = time.perf_counter()
    # The per-source cache is already shared in memory during collection. Flush
    # it once: serializing every source after each completion makes even a
    # fully cached refresh repeatedly write the entire collection to disk.
    _write_source_job_cache()
    with _lock:
        _source_counts = counts
        _source_checks = checks
    return _deduplicate_opportunities(collected), errors


def _fetch_opportunities() -> tuple[list[Opportunity], list[str]]:
    """Stable refresh entry point; results become visible as source tasks finish."""
    return _fetch_opportunities_progressive()


def _read_cache() -> tuple[datetime, list[Opportunity], list[str]] | None:
    global _source_checks, _source_counts
    try:
        payload = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        if payload.get("version") != 3:
            return None
        updated = datetime.fromisoformat(payload["updated"])
        today = datetime.now(timezone.utc).date()
        jobs = [Opportunity(**item) for item in payload["jobs"]
                if item.get("source") != "Adzuna"
                and urlparse(str(item.get("url") or "")).hostname not in {"adzuna.fr", "www.adzuna.fr"}
                and (not item.get("deadline") or date.fromisoformat(item["deadline"]) >= today)]
        jobs = [replace(job, location=_clean_job_location(job.location, job.title)) for job in jobs]
        jobs = [replace(job, family=_family(job.title, job.description),
                        start_period=_recovered_start_period(job))
                for job in jobs if _eligible_offer(job)]
        # Older snapshots had undated offers. Their snapshot date is the
        # earliest detection date we can recover without inventing history.
        jobs = [replace(job, published=updated.date().isoformat(), published_inferred=True)
                if not job.published else job for job in jobs]
        history = _read_history_document()
        first_seen = _first_seen_from_history(history)
        jobs = [replace(job, published=first_seen[job.url], published_inferred=True)
                if job.url in first_seen and first_seen[job.url] < job.published else job for job in jobs]
        jobs = _without_jobteaser_duplicates(jobs, official_history=_career_jobs_from_history(history))
        checks = payload.get("source_checks") or {}
        _source_checks = {str(name): dict(check) for name, check in checks.items()
                          if isinstance(name, str) and isinstance(check, dict)}
        _source_counts = {name: int(check["count"]) for name, check in _source_checks.items()
                          if check.get("status") in {"ok", "empty"} and isinstance(check.get("count"), int)}
        return updated, jobs, list(payload.get("errors") or [])
    except (OSError, ValueError, TypeError, KeyError):
        return None


def _read_history_document() -> dict:
    history_path = CACHE_PATH.with_name("internships_history.json")
    try:
        payload = json.loads(history_path.read_text(encoding="utf-8"))
        if payload.get("version") == 1:
            return {
                "version": 1,
                "baseline": payload.get("baseline") if isinstance(payload.get("baseline"), dict) else None,
                "snapshots": payload.get("snapshots") if isinstance(payload.get("snapshots"), list) else [],
                "first_seen": payload.get("first_seen") if isinstance(payload.get("first_seen"), dict) else {},
                "career_offers": payload.get("career_offers") if isinstance(payload.get("career_offers"), dict) else {},
            }
    except (OSError, ValueError, TypeError, AttributeError):
        pass
    return {"version": 1, "baseline": None, "snapshots": [], "first_seen": {}}


def _first_seen_from_history(payload: dict) -> dict[str, str]:
    """Recover the earliest detection, including snapshots from before the durable index existed."""
    dates: dict[str, str] = {}
    def remember(url: object, value: object) -> None:
        if isinstance(url, str) and url and isinstance(value, str) and _publication_sort_value(value):
            dates[url] = min(dates.get(url, value), value)
    for url, value in (payload.get("first_seen") or {}).items():
        remember(url, value)
    for snapshot in [payload.get("baseline"), *(payload.get("snapshots") or [])]:
        if not isinstance(snapshot, dict):
            continue
        observed = str(snapshot.get("updated") or "")[:10]
        for job in snapshot.get("jobs") or []:
            if isinstance(job, dict):
                remember(job.get("url"), observed)
                remember(job.get("url"), job.get("published"))
    return dates


_CAREER_IDENTITY_FIELDS = ('title', 'company', 'location', 'kind', 'url', 'published',
                           'score', 'start_period', 'source', 'published_inferred')


def _career_jobs_from_history(payload: dict) -> dict[str, Opportunity]:
    """Keep employer identities after rotating snapshots, without retaining descriptions."""
    rows = []
    for snapshot in [payload.get('baseline'), *(payload.get('snapshots') or [])]:
        if isinstance(snapshot, dict):
            rows.extend(snapshot.get('jobs') or [])
    rows.extend((payload.get('career_offers') or {}).values())
    result = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        try:
            job = Opportunity(**{key:row[key] for key in _CAREER_IDENTITY_FIELDS if key in row})
            if not _is_jobteaser(job):
                result[job.url] = job
        except (TypeError, ValueError, AttributeError):
            continue
    return result


def _remember_opportunity_snapshot(updated: datetime, jobs: list[Opportunity],
                                   errors: list[str], *, baseline: bool = False) -> None:
    """Keep public-feed history so non-admin accounts can read a delayed snapshot."""
    snapshot = {"updated": updated.isoformat(), "jobs": [asdict(job) for job in jobs],
                "errors": list(errors)}
    history_path = CACHE_PATH.with_name("internships_history.json")
    try:
        with _history_lock:
            payload = _read_history_document()
            first_seen = _first_seen_from_history(payload)
            for job in jobs:
                observed = updated.date().isoformat()
                first_seen[job.url] = min(first_seen.get(job.url, observed),
                                          job.published if _publication_sort_value(job.published) else observed,
                                          observed)
            payload["first_seen"] = first_seen
            career_jobs = _career_jobs_from_history(payload)
            career_jobs.update((job.url, job) for job in jobs if not _is_jobteaser(job))
            payload['career_offers'] = {url:{key:getattr(job,key) for key in _CAREER_IDENTITY_FIELDS}
                                        for url,job in career_jobs.items()}
            if baseline:
                if payload.get("baseline") is None:
                    payload["baseline"] = snapshot
            else:
                snapshots = [item for item in payload.get("snapshots", [])
                             if isinstance(item, dict) and item.get("updated") != snapshot["updated"]]
                snapshots.append(snapshot)
                payload["snapshots"] = snapshots[-8:]
            history_path.parent.mkdir(parents=True, exist_ok=True)
            temporary = history_path.with_suffix(".tmp")
            temporary.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            temporary.replace(history_path)
    except OSError:
        # If history storage is unavailable, don't expose the live snapshot as delayed data.
        pass


def load_delayed_opportunities(now: datetime | None = None) -> tuple[list[Opportunity], list[str], datetime]:
    """Return the newest shared feed snapshot that is at least three hours old."""
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(seconds=PUBLIC_UPDATE_DELAY_SECONDS)
    with _history_lock:
        payload = _read_history_document()
    candidates = [item for item in payload.get("snapshots", []) if isinstance(item, dict)]
    baseline = payload.get("baseline")
    if isinstance(baseline, dict):
        candidates.append(baseline)
    parsed = []
    for item in candidates:
        try:
            timestamp = datetime.fromisoformat(str(item["updated"]))
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=timezone.utc)
            jobs = [Opportunity(**job) for job in item.get("jobs", []) if isinstance(job, dict)]
            jobs = [job for job in jobs if _eligible_offer(job)]
            parsed.append((timestamp, jobs, list(item.get("errors") or []), item is baseline))
        except (ValueError, TypeError, KeyError):
            continue
    eligible = [item for item in parsed if item[0] <= cutoff]
    if eligible:
        updated, jobs, errors, _ = max(eligible, key=lambda item: item[0])
        return jobs, errors, updated
    if baseline:
        seeded = next((item for item in parsed if item[3]), None)
        if seeded:
            return seeded[1], seeded[2], seeded[0]
    return [], [], cutoff


def _write_cache(updated: datetime, jobs: list[Opportunity], errors: list[str]) -> None:
    try:
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        temporary = CACHE_PATH.with_suffix(".tmp")
        temporary.write_text(json.dumps({
            "version": 3, "updated": updated.isoformat(), "jobs": [asdict(job) for job in jobs],
            "errors": errors, "source_checks": source_checks(),
        }, ensure_ascii=False), encoding="utf-8")
        temporary.replace(CACHE_PATH)
    except OSError:
        # Public offers remain available in memory on read-only hosts.
        pass


class CollectionBusyError(RuntimeError):
    """Another refresh owns the collector; callers may retry later."""


def refresh_opportunities(force: bool = False, *, notify_email: bool = True,
                          fail_if_busy: bool = False) -> tuple[list[Opportunity], list[str], datetime]:
    global _cache, _last_attempt, _force_source_refresh, _refresh_previous_jobs, _refresh_first_seen, _refresh_career_jobs
    if not _refresh_guard.acquire(blocking=False):
        if fail_if_busy:
            raise CollectionBusyError("Une autre collecte est déjà en cours.")
        with _lock:
            snapshot = _cache
        if snapshot is None:
            snapshot = _read_cache()
        if snapshot:
            return list(snapshot[1]), list(snapshot[2]), snapshot[0]
        return [], [], datetime.now(timezone.utc)
    now = datetime.now(timezone.utc)
    try:
        with _lock:
            _last_attempt = now
            if _cache is None:
                _cache = _read_cache()
            previous_jobs = {job.url: job for job in _cache[1]} if _cache else {}
            baseline_snapshot = _cache
            _refresh_previous_jobs = previous_jobs
            _force_source_refresh = force
        history = _read_history_document()
        _refresh_first_seen = _first_seen_from_history(history)
        _refresh_career_jobs = _career_jobs_from_history(history)
        _refresh_career_jobs.update((job.url, job) for job in previous_jobs.values() if not _is_jobteaser(job))
        for job in previous_jobs.values():
            if _publication_sort_value(job.published):
                _refresh_first_seen[job.url] = min(_refresh_first_seen.get(job.url, job.published), job.published)
        if baseline_snapshot:
            _remember_opportunity_snapshot(*baseline_snapshot, baseline=True)
        ordered, errors = _fetch_opportunities()
        dated = []
        for job in ordered:
            previous = previous_jobs.get(job.url)
            dated.append(_date_detected_offer(job, previous, now.date()))
        ordered = sorted(dated, key=_opportunity_sort_key)
        with _lock:
            if ordered or _cache is None:
                _cache = (now, ordered, errors)
            elif _cache:
                _cache = (_cache[0], _cache[1], errors)
            snapshot = _cache or (now, [], errors)
        _write_cache(*snapshot)
        _remember_opportunity_snapshot(*snapshot)
        if notify_email:
            try:
                from .email_alerts import notify_new_offers
                notify_new_offers(snapshot[1], now=now)
            except Exception as exc:
                logging.warning("Internship email alert could not run (%s).", type(exc).__name__)
        return list(snapshot[1]), list(snapshot[2]), snapshot[0]
    finally:
        _force_source_refresh = False
        _refresh_previous_jobs = {}
        _refresh_career_jobs = {}
        _refresh_first_seen = {}
        _refresh_guard.release()


def opportunities_loading() -> bool:
    with _lock:
        return bool(_refresh_worker and _refresh_worker.is_alive())


def source_counts() -> dict[str, int]:
    with _lock:
        return dict(_source_counts)


def source_checks() -> dict[str, dict]:
    """Last attempted check per connector, including zero-result and failed checks."""
    with _lock:
        return {name: dict(check) for name, check in _source_checks.items()}


def load_opportunities(force: bool = False, refresh: bool = True) -> tuple[list[Opportunity], list[str], datetime]:
    """Return the last snapshot immediately and refresh stale data in the background."""
    global _cache, _refresh_worker
    now = datetime.now(timezone.utc)
    with _lock:
        needs_baseline = _cache is None
        if _cache is None:
            _cache = _read_cache()
        snapshot = _cache
        retry_due = False
        for check in _source_checks.values():
            if check.get("status") not in {"error", "stale"}:
                continue
            try:
                retry_at = datetime.fromisoformat(str(check.get("next_retry_at") or ""))
                if retry_at.tzinfo is None:
                    retry_at = retry_at.replace(tzinfo=timezone.utc)
                retry_due |= retry_at <= now
            except ValueError:
                pass
        stale = (snapshot is None or not _source_checks or retry_due
                 or (now - snapshot[0]).total_seconds() >= CACHE_SECONDS)
        retry_ready = _last_attempt is None or (now - _last_attempt).total_seconds() >= 60
        if refresh and (force or stale) and (force or retry_ready) and not (_refresh_worker and _refresh_worker.is_alive()):
            _refresh_worker = threading.Thread(
                target=refresh_opportunities, args=(force,), daemon=True, name="internship-refresh"
            )
            _refresh_worker.start()
        snapshot = _cache
    if needs_baseline and snapshot:
        _remember_opportunity_snapshot(*snapshot, baseline=True)
    if snapshot is None:
        return [], [], now
    return list(snapshot[1]), list(snapshot[2]), snapshot[0]


def start_hourly_refresh() -> None:
    """Start the initial fetch and refresh once per hour while this process runs."""
    global _hourly_worker
    with _lock:
        if _hourly_worker and _hourly_worker.is_alive():
            return

        def run() -> None:
            load_opportunities()
            while True:
                # Check retry deadlines without re-fetching healthy, fresh sources.
                threading.Event().wait(60)
                load_opportunities(force=False)

        _hourly_worker = threading.Thread(target=run, daemon=True, name="internship-hourly-refresh")
        _hourly_worker.start()


def _utc_display_stamp(value: datetime) -> str:
    # Legacy timestamps without an offset already represent UTC.
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")


_LOCATION_COUNTRIES = {
    "France": "FR|FRA|France", "Royaume-Uni": "GB|GBR|UK|United Kingdom|Great Britain|Royaume Uni|England|Scotland",
    "États-Unis": "US|USA|United States|United States of America|Etats Unis",
    "Allemagne": "DE|DEU|Germany|Deutschland|Allemagne", "Suisse": "CH|CHE|Switzerland|Suisse|Schweiz",
    "Pays-Bas": "NL|NLD|Netherlands|Pays Bas|Nederland", "Italie": "IT|ITA|Italy|Italia|Italie",
    "Espagne": "ES|ESP|Spain|Espana|Espagne", "Portugal": "PT|PRT|Portugal",
    "Luxembourg": "LU|LUX|Luxembourg", "Singapour": "SG|SGP|Singapore|Singapour",
    "Hong Kong": "HK|HKG|Hong Kong", "Chine": "CN|CHN|China|Chine",
    "Japon": "JP|JPN|Japan|Japon", "Corée du Sud": "KR|KOR|South Korea|Coree du Sud",
    "Émirats arabes unis": "AE|ARE|UAE|United Arab Emirates|Emirats arabes unis",
    "Australie": "AU|AUS|Australia|Australie", "Irlande": "IE|IRL|Ireland|Irlande",
    "Danemark": "DK|DNK|Denmark|Danemark", "Hongrie": "HU|HUN|Hungary|Hongrie",
    "Pologne": "PL|POL|Poland|Pologne", "Maroc": "MA|MAR|Morocco|Maroc",
    "Monaco": "MC|MCO|Monaco", "Chili": "CL|CHL|Chile|Chili",
    "Brésil": "BR|BRA|Brazil|Brasil|Bresil", "Mexique": "MX|MEX|Mexico|Mexique",
    "Thaïlande": "TH|THA|Thailand|Thailande", "Inde": "IN|IND|India|Inde",
    "Qatar": "QA|QAT|Qatar", "Taïwan": "TW|TWN|Taiwan",
    "Canada": "CA|CAN|Canada", "Suède": "SE|SWE|Sweden|Suede",
    "Belgique": "BE|BEL|Belgium|Belgique",
    # No two-letter code: "CO" is also the Colorado state abbreviation.
    "Colombie": "COL|Colombia|Colombie",
}
_LOCATION_CITIES = {
    "Paris": ("France", ""), "Montrouge": ("France", ""), "La Défense": ("France", ""),
    "Courbevoie": ("France", ""), "Puteaux": ("France", ""), "Nanterre": ("France", ""),
    "Charenton-le-Pont": ("France", ""), "Rueil-Malmaison": ("France", ""),
    "Levallois-Perret": ("France", ""), "Boulogne-Billancourt": ("France", ""),
    "Fontenay-sous-Bois": ("France", ""), "Saint-Denis": ("France", ""),
    "Issy-les-Moulineaux": ("France", ""), "Saint-Quentin-en-Yvelines": ("France", ""),
    "Saint-Grégoire": ("France", ""), "Le Relecq-Kerhuon": ("France", ""), "Lyon": ("France", ""), "Lille": ("France", ""),
    "Bordeaux": ("France", ""), "Nantes": ("France", ""), "Marseille": ("France", ""),
    "Londres": ("Royaume-Uni", "London|Canary Wharf"), "Glasgow": ("Royaume-Uni", ""),
    "Francfort": ("Allemagne", "Frankfurt am Main|Frankfurt"), "Düsseldorf": ("Allemagne", "Dusseldorf"),
    "Munich": ("Allemagne", "Munchen"), "Berlin": ("Allemagne", ""),
    "Zurich": ("Suisse", "Zürich"), "Genève": ("Suisse", "Geneva"), "Nyon": ("Suisse", ""),
    "Amsterdam": ("Pays-Bas", ""), "La Haye": ("Pays-Bas", "The Hague|Den Haag"),
    "Milan": ("Italie", "Milano"), "Rome": ("Italie", "Roma"), "Assago": ("Italie", ""),
    "Scandicci": ("Italie", ""), "Madrid": ("Espagne", ""), "Barcelone": ("Espagne", "Barcelona"),
    "Lisbonne": ("Portugal", "Lisbon|Lisboa"), "Luxembourg": ("Luxembourg", "Lux"),
    "Dublin": ("Irlande", ""), "Copenhague": ("Danemark", "Copenhagen"), "Aarhus": ("Danemark", ""),
    "Budapest": ("Hongrie", ""), "Varsovie": ("Pologne", "Warsaw"), "Wrocław": ("Pologne", "Wroclaw"),
    "Stockholm": ("Suède", ""), "Bruxelles": ("Belgique", "Brussels"),
    "Singapour": ("Singapour", "Singapore"), "Hong Kong": ("Hong Kong", ""),
    "Shanghai": ("Chine", ""), "Pékin": ("Chine", "Beijing"), "Tokyo": ("Japon", ""),
    "Séoul": ("Corée du Sud", "Seoul"), "Taipei": ("Taïwan", ""),
    "Dubaï": ("Émirats arabes unis", "Dubai"), "Doha": ("Qatar", ""),
    "Sydney": ("Australie", ""), "Mumbai": ("Inde", "Bombay"), "Casablanca": ("Maroc", ""),
    "Monaco": ("Monaco", ""), "Santiago": ("Chili", ""), "São Paulo": ("Brésil", "Sao Paulo"),
    "Mexico": ("Mexique", "Mexico City"), "Bogota": ("Colombie", "Bogotá"), "Toronto": ("Canada", ""), "Montréal": ("Canada", "Montreal"),
    **{city: ("États-Unis", alias) for city, alias in (
        ("New York", "New York City|NYC"), ("Chicago", ""), ("Miami", ""), ("Dallas", ""),
        ("West Palm Beach", ""), ("Salt Lake City", ""), ("Stafford", ""), ("Houston", ""),
        ("San Francisco", ""), ("Los Angeles", ""), ("Austin", ""), ("Seattle", ""), ("Stamford", ""), ("Boston", ""),
        ("Newport Beach", ""))},
}
_LOCATION_COUNTRY_NAMES = {
    _offer_search_text(alias): country
    for country, aliases in _LOCATION_COUNTRIES.items() for alias in aliases.split("|")
}
_LOCATION_CITY_PATTERNS = [
    (re.compile(r"(?<!\w)(?:" + "|".join(re.escape(alias) for alias in sorted(
        {_offer_search_text(city), *(_offer_search_text(a) for a in aliases.split("|") if a)}, key=len, reverse=True)) + r")(?!\w)"), city, country)
    for city, (country, aliases) in _LOCATION_CITIES.items()
]


def _display_offer_location(value: str) -> str:
    """Normalize known cities/countries without overwriting raw source metadata."""
    value = re.split(r"\b(?:Domaine d.activit[eé]|Business area|Job category|Department)\s*:",
                     html.unescape(value or ""), maxsplit=1, flags=re.I)[0]
    value = _plain_text("".join(char for char in value if unicodedata.category(char) != "Co")).strip(" ,|–-")
    key = _offer_search_text(value)
    # "Search" is a listing-page label some career sites leave in the location column.
    if key in {"", "all", "non precise", "not specified", "unknown", "n a", "multiple locations", "various", "search"}:
        return "Non précisé"
    parts = re.split(r"[,;|·()]+|\s+[-–—]\s+", value)
    countries = {_LOCATION_COUNTRY_NAMES[part] for part in map(_offer_search_text, parts)
                 if part in _LOCATION_COUNTRY_NAMES}
    named_countries = set()
    for alias, country in _LOCATION_COUNTRY_NAMES.items():
        if len(alias) > 3 and re.search(r"(?<!\w)" + re.escape(alias) + r"(?!\w)", key):
            countries.add(country)
            named_countries.add(country)
    # CA/IN/MA can denote US states rather than countries in employer addresses.
    if re.search(r"\bunited states\b|\busa\b|\betats unis\b", key):
        countries -= {_LOCATION_COUNTRY_NAMES[part] for part in map(_offer_search_text, parts)
                      if part in {"ca", "in", "ma", "va"} and part in _LOCATION_COUNTRY_NAMES
                      and _LOCATION_COUNTRY_NAMES[part] not in named_countries}
    code = re.search(r"\b([A-Z]{2,3})$|^([A-Z]{2,3})-", value)
    if code and (country := _LOCATION_COUNTRY_NAMES.get((code[1] or code[2]).lower())):
        countries.add(country)
    matches = sorted((match.start(), city, country) for pattern, city, country in _LOCATION_CITY_PATTERNS
                     if (match := pattern.search(key)))
    matches = [item for item in matches if item[1] != "Stafford" or "États-Unis" in countries or re.search(r"\bva\b", key)]
    if not matches and countries == {"Hong Kong"} and re.match(r"central\b", key):
        matches = [(0, "Hong Kong", "Hong Kong")]
    if not re.search(r"/|;|\b(?:or|ou)\b", value, re.I) and any(city == "La Défense" for _, city, _ in matches):
        matches = [item for item in matches if item[1] not in {"Paris", "Courbevoie", "Puteaux", "Nanterre"}]
    if matches and all(country == "États-Unis" for _, _, country in matches):
        for state, country in (("ca", "Canada"), ("in", "Inde"), ("ma", "Maroc")):
            if state in map(_offer_search_text, parts) and country not in named_countries:
                countries.discard(country)
    # Explicit contradictory countries must not be overwritten by a familiar city name.
    if matches and not countries - {country for _, _, country in matches}:
        result = []
        for _, city, country in matches:
            if city == "Paris":
                district = re.search(r"\bparis\s+(0?[1-9]|1\d|20)(?:e(?:me)?|er|\s+arrondissement)\b", key)
                postal = re.search(r"\b750(0[1-9]|1\d|20)\b", key)
                if district or postal:
                    number = int((district or postal)[1])
                    city += f" {number}{'er' if number == 1 else 'e'}"
            result.append(city if city == country else f"{city} · {country}")
        return " / ".join(result)
    if len(countries) == 1:
        country = next(iter(countries))
        rest = [part.strip() for part in parts if part.strip() and _offer_search_text(part) not in _LOCATION_COUNTRY_NAMES]
        if key in {"sgp head office", "sg head office"}:
            return "Singapour"
        if key in {"ile de france", "idf"}:
            return "Île-de-France · France"
        return f"{', '.join(rest)} · {country}" if rest else country
    if key in {"ile de france", "idf"}:
        return "Île-de-France · France"
    if not matches and re.search(r"\b(?:corp|head office)\b", key):
        return "Non précisé"
    return value


def _display_offer_place(location: str, title: str = "") -> str:
    """Display a location, falling back to a city named at the end of the title."""
    place = _display_offer_location(location)
    if place != "Non précisé" or not title:
        return place
    tail = re.search(r"[-–—,(]\s*([^-–—,()]+?)\s*\)?\s*$", html.unescape(title))
    if not tail:
        return place
    key = _offer_search_text(tail[1])
    for pattern, city, country in _LOCATION_CITY_PATTERNS:
        if (match := pattern.fullmatch(key)) and match[0] == key:
            return city if city == country else f"{city} · {country}"
    return place


def _display_offer_date(value: str) -> str:
    """Normalize presentation only; retain the source date's precision and ranges."""
    value = (value or "").strip()
    if not value:
        return "Non précisé"
    for pattern in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            parsed = datetime.strptime(value, pattern)
            return f"{parsed.day} {_MONTH_NAMES[parsed.month - 1]} {parsed.year}"
        except ValueError:
            pass
    if re.fullmatch(r"\d{4}-\d{2}", value):
        try:
            parsed = datetime.strptime(value, "%Y-%m")
            return f"{_MONTH_NAMES[parsed.month - 1]} {parsed.year}"
        except ValueError:
            return value
    # Translate named months without inferring a missing day or year.
    english_day = re.fullmatch(rf"({_MONTH})\s+(\d{{1,2}})(?:st|nd|rd|th)?[,]?\s+(\d{{4}})", value, re.I)
    if english_day:
        value = f"{english_day[2]} {english_day[1]} {english_day[3]}"
    # "6th September 2027" -> "6 septembre 2027"; "1st" keeps the French "1er".
    value = re.sub(rf"\b(\d{{1,2}})(?:st|nd|rd|th)\s+(?=(?:of\s+)?(?:{_MONTH})\b)",
                   lambda match: ("1er" if match[1] in {"1", "01"} else str(int(match[1]))) + " ",
                   value, flags=re.I)
    value = re.sub(rf"\b(\d{{1,2}}(?:er)?)\s+of\s+(?=(?:{_MONTH})\b)", r"\1 ", value, flags=re.I)
    return re.sub(rf"\b({_MONTH})\b",
                  lambda match: _MONTH_NAMES[_MONTH_ALIASES[match[0].casefold()] - 1], value, flags=re.I)


def _display_offer_title(title: str, location: str = "") -> str:
    """Keep the role and desk visible, removing contract and gender boilerplate."""
    value = html.unescape(title)
    gender = (r"(?:[fmhw]\s*[/·.\-]\s*[fmhw]\s*[/·.\-]\s*(?:d|x|divers(?:e)?)|"
              r"[hf]\s*[/·.\-]\s*[hf]|[fmw]\s*[/·.\-]\s*[fmw]|"
              r"all\s+genders?|all\s+sexes|tous\s+genres)")
    value = re.sub(rf"[\[(]\s*{gender}\s*[\])]", " ", value, flags=re.I)
    value = re.sub(rf"\b{gender}\b", " ", value, flags=re.I)
    while value.rstrip().endswith(')') and value.count(')') > value.count('('):
        value = value.rstrip()[:-1]
    value = re.sub(r"\s+([)\]])", r"\1", value)
    # Public sitemap titles sometimes lose punctuation ("F H", "F M D").
    value = re.sub(r"(?:^|\s)(?:[FH]\s+[HF]|F\s+M\s+D|M\s+W\s+D)\s*$", "", value)
    value = re.sub(r"^\s*(?:[FH]\s+[HF]|F\s+M\s+D|M\s+W\s+D)\s*[-–—:|]\s*", "", value)
    # Strip explicit calendar metadata before internship labels, so a trailing
    # city/year cannot hide "Summer Intern" from the existing cleanup.
    month = rf"(?:{_MONTH}|jan|feb|fév|fev|mar|apr|avr|jun|jul|aug|sep|sept|oct|nov|dec|déc)\.?"
    value = re.sub(r"\b(summer|winter|spring|autumn|fall|été|hiver|printemps)\s+20\d{2}\b",
                   r"\1", value, flags=re.I)
    period = (rf"(?:\d{{1,2}}(?:st|nd|rd|th|er)?\s+)?{month}"
              rf"(?:\s+20\d{{2}})?\s*(?:[-–—/]|to|à|au)\s*{month}\s+20\d{{2}}|"
              rf"(?:\d{{1,2}}(?:st|nd|rd|th|er)?\s+)?{month}\s+20\d{{2}}|"
              r"(?:summer|winter|spring|autumn|fall|été|hiver|printemps|S[12]|H[12]|Q[1-4])\s+20\d{2}")
    value = re.sub(rf"\b(?:{period})\b", " ", value, flags=re.I)
    value = re.sub(r"\b20\d{2}\s+Start\b", " ", value, flags=re.I)
    value = re.sub(r"\b20\d{2}\b", " ", value)
    if location and _display_offer_location(location) != "Non précisé":
        place = _offer_search_text(_display_offer_location(location))
        aliases = []
        for city, (country, variants) in _LOCATION_CITIES.items():
            if re.search(r"(?<!\w)" + re.escape(_offer_search_text(city)) + r"(?!\w)", place):
                aliases.extend([city, *(a for a in variants.split('|') if a)])
                aliases.extend(a for a in _LOCATION_COUNTRIES.get(country, '').split('|') if len(a) > 3)
        for alias in sorted(set(aliases), key=len, reverse=True):
            value = re.sub(r"(?<!\w)" + re.escape(alias) + r"(?!\w)(?!\s+(?:Stock Exchange|Stock Market))",
                           " ", value, flags=re.I)
        # A removed city can leave its state or country code behind ("- , CA", "- , UK").
        value = re.sub(r"(?:\s*[-–—,]|(?<=[\[(]))\s*,\s*[A-Z]{2}\b(?=\s*(?:[,;]\s*)*(?:[|)\]]|$))", " ", value)
    value = re.sub(r"[\[(][\s\-–—,:|/]*[\])]", " ", value)
    value = re.sub(r"\s+", " ", value).strip(" -–—:|,")
    contract = r"(?:(?:summer|winter|spring|off[ -]?cycle|seasonal|long)\s+)?(?:stage|stagiaire|internship|intern)\b"
    duration = r"(?:de\s+|of\s+)?\d{1,2}\s*[-–]?\s*(?:mois|months?)\b"
    label = rf"(?:{contract}(?:\s*[-–—:|]?\s*{duration})?|{duration}\s+{contract})"
    def keep_stage_type(match: re.Match) -> str:
        return match[0] if re.search(r"\b(?:intern|internship|summer|winter|spring|off[ -]?cycle|seasonal)\b", match[0], re.I) else ""
    value = re.sub(rf"\(\s*{label}\s*\)", keep_stage_type, value, flags=re.I).strip()
    value = re.sub(rf"^\s*{label}\s*[-–—:|]?\s*", keep_stage_type, value, flags=re.I)
    value = re.sub(rf"\s*[-–—:|]?\s+{label}\s*$", keep_stage_type, value, flags=re.I)
    value = re.sub(r"\b\d{1,2}\s*[-–]?\s*(?:mois|months?)\b", " ", value, flags=re.I)
    value = re.sub(r"\(\s*(?:North America|Americas|EMEA|APAC)\s*[-–—]?\s*\)", " ", value, flags=re.I)
    value = re.sub(r"[\[(][\s\-–—,:|/]*[\])]", " ", value)
    value = re.sub(r"([\[(])\s+", r"\1", value)
    value = re.sub(r"\s+([)\]])", r"\1", value)
    value = re.sub(r"\s*[-–—,:|]+\s*([)\]])", r"\1", value)
    # Collapse separator runs such as " - /", ", -" or " - :" into one dash.
    value = re.sub(r"\s*[-–—:|,/](?:\s*[-–—:|,/])+\s*",
                   lambda run: " - " if re.search(r"[-–—:|]", run[0]) else run[0], value)
    return re.sub(r"\s+", " ", value).strip(" -–—:|,") or title


def render_opportunities(jobs: list[Opportunity], errors: list[str], updated: datetime,
                         category: str = "Toutes", query: str = "", family: str = "Tous métiers",
                         earliest: str = "Toutes dates", seen_urls: list[str] | None = None,
                         tracking: dict | None = None, only_new: bool = False,
                         hide_dismissed: bool = True, refreshing: bool = False,
                         weekly: bool = False, today: date | None = None,
                         daily: bool = False, feedback: dict | None = None,
                         show_hors_cible: bool = False, sort_by: str = "pertinence",
                         delayed_updates: bool = False, page: int = 1, page_size: int = 50) -> str:
    # BNP endpoints often reject server-side requests; keep those diagnostics
    # in the cache, without presenting them as recurring user notifications.
    visible_errors = [error for error in errors if not error.startswith((
        "BNP Paribas:", "BNP Paribas VIE:", "BNP Paribas CIB:", "BNP Paribas APAC:",
        "BNP Paribas Asset Management:",
    ))]
    checks = {} if delayed_updates else source_checks()
    unavailable = partial = retained = 0
    for name in {error.partition(":")[0] for error in visible_errors}:
        check = checks.get(name, {})
        if check.get("cache_status") == "partial":
            partial += 1
        elif check.get("status") == "stale" and check.get("count", 0):
            retained += 1
        else:
            unavailable += 1
    warnings = []
    if unavailable:
        warnings.append(f"{unavailable} source{'s' if unavailable > 1 else ''} inaccessible{'s' if unavailable > 1 else ''}")
    if partial:
        warnings.append(f"{partial} collecte{'s' if partial > 1 else ''} partielle{'s' if partial > 1 else ''}")
    if retained:
        warnings.append(f"{retained} source{'s' if retained > 1 else ''} avec offres conservées")
    today = today or datetime.now(timezone.utc).date()
    ordered = matching_opportunities(
        jobs, category, query, family, earliest, seen_urls, tracking, only_new,
        hide_dismissed, weekly, today, daily, sort_by,
    )
    stamp = _utc_display_stamp(updated)
    total = len(ordered)
    page_size = max(1, min(int(page_size), 100))
    page_count = max(1, (total + page_size - 1) // page_size)
    page = max(1, min(int(page), page_count))
    first_index = (page - 1) * page_size
    shown = ordered[first_index:first_index + page_size]
    range_start = first_index + 1 if total else 0
    range_end = min(first_index + page_size, total)
    displayed = f"Offres {range_start}–{range_end} sur {total}"
    status = (
        '<div class="results-overview" role="status">'
        f'<span class="results-count"><strong>{html.escape(displayed)}</strong></span>'
        '<span class="results-meta">'
        f'<span class="results-updated" title="Début de la dernière collecte globale ; chaque source a sa propre date de vérification.">Mis à jour {html.escape(stamp)}</span>'
        + (f'<span class="results-warning">{html.escape(" · ".join(warnings))}</span>' if warnings else '')
        + ('<span class="results-refreshing">Actualisation en cours</span>' if refreshing else '')
        + '</span>'
        + '</div>'
    )
    cards = []
    for job in shown:
        entry = (tracking or {}).get(job.url) if isinstance(tracking, dict) else None
        initials = "".join(word[0] for word in re.findall(r"[A-Za-zÀ-ÿ0-9]+", job.company)[:2]).upper() or "•"
        icon = _company_icon(job.company)
        company_mark = (
            f'<img src="{html.escape(icon, quote=True)}" alt="" loading="lazy" '
            'referrerpolicy="no-referrer" onerror="this.remove()">'
            if icon else ""
        )
        badges = (
            (f'<span class="job-badge tracked">{html.escape(normalize_status(entry.get("status")))}</span>'
               if isinstance(entry, dict) and entry.get("status") else '')
        )
        details = (
            f'<span class="job-fact" title="{html.escape(job.family, quote=True)}">{html.escape(job.family)}</span>'
            + (f'<span class="job-fact deadline">Limite : {html.escape(job.deadline)}</span>'
               if job.deadline else '')
        )
        publication = (f'Publication inconnue · Détectée le {html.escape(job.published)}'
                       if job.published_inferred else f'Publié {html.escape(job.published or "date inconnue")}')
        shown_publication = html.escape(_display_offer_date(job.published))
        publication_label = (f'Détectée le {shown_publication}' if job.published_inferred
                             else f'Publié le {shown_publication}' if job.published else 'Publication inconnue')
        source_label = "JobTeaser · sitemap" if job.source == "JobTeaser · sitemap" else "Source employeur"
        source_detail = (f'{job.source} · '
                         f'{"Sitemap lu le" if job.source == "JobTeaser · sitemap" else "Vérifié le"} {job.checked_at}')
        content = (
            '<span class="job-card-header">'
            f'<span class="job-company-mark" aria-hidden="true">{html.escape(initials)}{company_mark}</span>'
            '<span class="job-company-block">'
            f'<span class="job-company" title="{html.escape(job.company, quote=True)}">{html.escape(job.company)}</span>'
            '</span>'
            f'<span class="job-fact kind">{html.escape(job.kind)}</span>'
            '<span class="job-card-open" aria-hidden="true">↗</span>'
            '</span>'
            f'<strong class="job-title" title="{html.escape(job.title, quote=True)}">{html.escape(_display_offer_title(job.title, job.location))}</strong>'
            '<span class="job-key-facts">'
            f'<span><small>Lieu</small><span class="job-location">{html.escape(_display_offer_location(job.location))}</span></span>'
            f'<span><small>Début</small><span>{html.escape(_display_offer_date(job.start_period))}</span></span>'
            '</span>'
        )
        escaped_url = html.escape(job.url, quote=True)
        footer = (
            '<span class="job-card-footer">'
            f'<span class="job-card-tags">{details}{badges}</span>'
            '<span class="job-card-provenance">'
            f'<span class="job-published" title="{publication} · {source_label} · {html.escape(source_detail, quote=True)}">{publication_label}</span>'
            '</span>'
            '</span>'
        )
        link = (f'<a class="job-card-main" href="{escaped_url}" target="_blank" rel="noopener noreferrer">'
                + content + footer + '</a>')
        tracked_status = normalize_status(entry.get("status")) if isinstance(entry, dict) else ""
        cards.append(
            '<article class="internship-card-container internship-card"'
            f' data-offer-url="{escaped_url}"'
            f' data-offer-title="{html.escape(job.title, quote=True)}"'
            f' data-offer-company="{html.escape(job.company, quote=True)}"'
            f' data-tracking-status="{html.escape(tracked_status, quote=True)}">'
            + link + '</article>'
        )
    empty = ("Chargement des offres en cours…" if refreshing and not jobs else
             "Aucune offre pour ce filtre. Essaie une autre recherche ou actualise les sources.")
    body = "".join(cards) or f'<div class="calendar-empty">{empty}</div>'
    vie_link = (
        '<a class="internship-source-link" href="https://mon-vie-via.businessfrance.fr/en/offres" '
        'target="_blank" rel="noopener noreferrer">Explorer toutes les offres VIE sur le portail officiel Business France ↗</a>'
        if category in {"Toutes", "VIE"} else ""
    )
    source_rows = []
    for name, check in sorted(checks.items()):
        state = check.get("status")
        count = check.get("count")
        label = ("Disponible" if state == "ok" else
                 "Aucune offre remontée" if state == "empty" else "Vérification impossible")
        try:
            checked = _utc_display_stamp(datetime.fromisoformat(str(check.get("checked_at") or "")))
        except ValueError:
            checked = "Inconnue"
        count_label = str(count) if state in {"ok", "empty"} and isinstance(count, int) else "—"
        if state == "stale":
            label = "Offres en cache, dernière collecte en erreur"
            count_label = str(count) if isinstance(count, int) else "—"
        if check.get("cache_status") == "partial":
            label = "Collecte incomplète, certaines fiches indisponibles"
            count_label = str(count) if isinstance(count, int) else "—"
        if check.get("cache_status") == "backoff":
            label = ("Reprise différée · anciennes offres conservées" if state == "stale"
                     else "Réessai programmé")
        duration = check.get("duration_ms")
        duration_label = f"{duration} ms" if isinstance(duration, (int, float)) else "-"
        if check.get("cache_status") == "fresh":
            duration_label = "Cache · " + duration_label
        elif check.get("cache_status") == "backoff":
            duration_label = "retour automatique"
        source_rows.append(
            '<tr>'
            f'<th scope="row">{html.escape(name)}</th>'
            f'<td><span class="source-state source-state-{html.escape(str(state), quote=True)}">{label}</span></td>'
            f'<td>{count_label}<small class="source-duration"> · {html.escape(duration_label)}</small></td>'
            f'<td>{html.escape(checked)}</td>'
            '</tr>'
        )
    source_details = (
        '<p class="results-delay-note">Les nouveautés et changements sont affichés avec trois heures de décalage.</p>'
        if delayed_updates else
        '<details class="internship-source-details"><summary>État des sources</summary>'
        '<p>Offres remontées par chaque connecteur avant dédoublonnage. Un zéro ne signifie pas que l’employeur ne recrute pas.</p>'
        '<div class="source-checks-scroll"><table class="source-checks-table">'
        '<thead><tr><th>Source</th><th>État</th><th>Offres</th><th>Dernière vérification</th></tr></thead><tbody>'
        + ("".join(source_rows) if source_rows else '<tr><td colspan="4">Diagnostic en cours de chargement.</td></tr>')
        + '</tbody></table></div>'
        + (f'<p>Problèmes de collecte : {html.escape(", ".join(visible_errors))}</p>' if visible_errors else '')
        + '</details>'
    )
    jobteaser_link = (
        '<a class="internship-source-link" href="https://www.jobteaser.com/fr/job-offers?locale=fr" '
        'target="_blank" rel="noopener noreferrer">Explorer les offres publiques sur JobTeaser ↗</a>'
    )
    bnp_link = (
        '<a class="internship-source-link" '
        'href="https://group.bnpparibas/emploi-carriere/toutes-offres-emploi/stage" '
        'target="_blank" rel="noopener noreferrer">Voir les stages BNP Paribas sur le site officiel ↗</a>'
        if not any(job.company.startswith("BNP Paribas") and job.source.startswith("Site carrière") for job in jobs)
        else ''
    )
    return (f'<section class="internship-board"><div class="internship-status">{status}</div>'
            f'{source_details}<div class="internship-grid">{body}</div>'
            f'<div class="internship-external-sources">{jobteaser_link}{bnp_link}{vie_link}</div></section>')


def _published_this_week(published: str, today: date) -> bool:
    """Include publication dates from today and the preceding six calendar days."""
    if not isinstance(published, str):
        return False
    published_ordinal = _publication_sort_value(published)
    return 0 < published_ordinal and today.toordinal() - 6 <= published_ordinal <= today.toordinal()


TRACKING_STATUSES = (
    "À examiner", "À candidater", "Postulé", "OA", "HV", "Interview", "Offer", "Rejected", "Écartée",
)
LEGACY_STATUSES = {
    "Candidature envoyée": "Postulé", "Entretien": "Interview",
    "Offre reçue": "Offer", "Refus": "Rejected",
}


def normalize_status(status: object) -> str:
    value = LEGACY_STATUSES.get(str(status or ""), str(status or ""))
    return value if value in TRACKING_STATUSES else TRACKING_STATUSES[0]


def save_tracking(state: dict | None, job: Opportunity, status: str, note: str,
                  deadline: str = "", follow_up: str = "", applied_at: str = "") -> dict:
    entries = dict(state) if isinstance(state, dict) else {}
    status = normalize_status(status)
    def valid_date(value: str) -> str:
        value = (value or "").strip()[:10]
        try:
            return date.fromisoformat(value).isoformat() if value else ""
        except ValueError:
            return ""

    deadline, follow_up, applied_at = map(valid_date, (deadline, follow_up, applied_at))
    previous = entries.get(job.url) if isinstance(entries.get(job.url), dict) else {}
    if not applied_at and status == "Postulé":
        applied_at = previous.get("applied_at") or datetime.now(timezone.utc).date().isoformat()
    elif not applied_at:
        applied_at = previous.get("applied_at") or ""
    entries[job.url] = {
        "title": job.title[:180], "company": job.company[:100], "location": job.location[:100],
        "status": status, "note": (note or "")[:1000],
        "deadline": deadline or job.deadline, "follow_up": follow_up,
        "applied_at": applied_at,
        "updated": datetime.now(timezone.utc).date().isoformat(),
    }
    return dict(list(entries.items())[-100:])


def mark_opened_offer_applied(state: dict | None, jobs: list[Opportunity], url: str) -> tuple[dict, bool]:
    """Confirm an opened, currently listed offer without downgrading existing progress."""
    entries = dict(state) if isinstance(state, dict) else {}
    job = next((item for item in jobs if item.url == url), None)
    if job is None:
        return entries, False
    previous = entries.get(url) if isinstance(entries.get(url), dict) else {}
    status = normalize_status(previous.get("status")) if previous else ""
    if status and status not in {"À examiner", "À candidater"}:
        return entries, False
    return save_tracking(
        entries, job, "Postulé", str(previous.get("note") or ""),
        str(previous.get("deadline") or ""), str(previous.get("follow_up") or ""),
        str(previous.get("applied_at") or ""),
    ), True


def save_offer_feedback(state: dict | None, job: Opportunity, verdict: str) -> dict:
    """Toggle personal relevance feedback without altering the public source data."""
    entries = dict(state) if isinstance(state, dict) else {}
    if verdict not in {"pertinent", "hors_cible"}:
        return entries
    previous = entries.get(job.url)
    if isinstance(previous, dict) and previous.get("verdict") == verdict:
        entries.pop(job.url, None)
    else:
        entries[job.url] = {
            "verdict": verdict, "title": job.title[:180], "company": job.company[:100],
            "updated": datetime.now(timezone.utc).isoformat(),
        }
    return dict(list(entries.items())[-1000:])


def export_tracking(state: dict | None) -> str:
    """Return a copyable local backup of the browser-only application tracker."""
    return json.dumps(state if isinstance(state, dict) else {}, ensure_ascii=False, indent=2)


def import_tracking(payload: str, state: dict | None) -> tuple[dict, str]:
    if len(payload or "") > 200_000:
        return dict(state or {}), "Sauvegarde trop volumineuse."
    try:
        incoming = json.loads(payload)
    except (TypeError, ValueError):
        return dict(state or {}), "JSON invalide."
    if not isinstance(incoming, dict):
        return dict(state or {}), "La sauvegarde doit contenir des offres."
    merged = dict(state or {})
    imported = 0
    for url, entry in list(incoming.items())[:100]:
        if not isinstance(url, str) or not isinstance(entry, dict):
            continue
        try:
            parsed = urlparse(url)
            if parsed.scheme != "https" or not parsed.hostname or len(url) > 2000:
                continue
        except ValueError:
            # Malformed hostnames must not abort the rest of the backup import.
            continue
        status = normalize_status(entry.get("status"))
        def safe_date(key: str) -> str:
            value = str(entry.get(key) or "")[:10]
            try:
                return date.fromisoformat(value).isoformat() if value else ""
            except ValueError:
                return ""
        merged[url] = {
            "title": str(entry.get("title") or "Offre")[:180],
            "company": str(entry.get("company") or "")[:100],
            "location": str(entry.get("location") or "")[:100],
            "status": status, "note": str(entry.get("note") or "")[:1000],
            "deadline": safe_date("deadline"), "follow_up": safe_date("follow_up"),
            "applied_at": safe_date("applied_at"), "updated": safe_date("updated"),
        }
        imported += 1
    return dict(list(merged.items())[-100:]), f"{imported} offre(s) importée(s) dans ce navigateur."


PIPELINE_GROUPS = (
    ("À préparer", ("À examiner", "À candidater")),
    ("En cours", ("Postulé", "OA", "HV")),
    ("Entretiens", ("Interview",)),
    ("Décisions", ("Offer", "Rejected", "Écartée")),
)


def render_tracking(state: dict | None, current_jobs: list[Opportunity],
                    today: date | None = None) -> str:
    """Render a compact application pipeline, priorities, and editable-record context."""
    today = today or datetime.now(timezone.utc).date()
    entries = state if isinstance(state, dict) else {}
    live = {job.url for job in current_jobs}
    records = []
    for url, entry in list(entries.items())[-100:]:
        if not isinstance(url, str) or not isinstance(entry, dict):
            continue
        parsed = urlparse(url)
        if parsed.scheme == "https" and parsed.hostname:
            records.append((url, entry, normalize_status(entry.get("status"))))
    if not records:
        return ('<div class="pipeline-empty"><strong>Aucune candidature suivie</strong>'
                '<p>Ajoute une offre pour préparer ta candidature et retrouver tes prochaines étapes ici.</p></div>')

    active = [(url, entry, status) for url, entry, status in records
              if status not in {"Offer", "Rejected", "Écartée"}]
    due = []
    for url, entry, status in active:
        try:
            action_date = date.fromisoformat(str(entry.get("follow_up") or ""))
        except ValueError:
            continue
        if action_date <= today + timedelta(days=7):
            due.append((action_date, url, entry))
    due.sort(key=lambda item: item[0])
    missing_action = sum(not entry.get("follow_up") for _, entry, _ in active)
    metrics = (
        ("Offres suivies", len(records)), ("En cours", len(active)),
        ("Actions sous 7 jours", len(due)), ("Sans prochaine action", missing_action),
    )
    summary = "".join(
        f'<div class="pipeline-stat"><strong>{value}</strong><span>{html.escape(label)}</span></div>'
        for label, value in metrics
    )
    priorities = "".join(
        f'<li><span class="priority-date">{action_date.isoformat()}</span>'
        f'<span><b>{html.escape(str(entry.get("company") or ""))}</b> · '
        f'{html.escape(str(entry.get("title") or "Offre"))}</span></li>'
        for action_date, _, entry in due[:5]
    )
    priority_panel = (
        '<div class="pipeline-priorities"><strong>Prochaines actions</strong><ul>' + priorities + '</ul></div>'
        if priorities else '<div class="pipeline-priorities"><strong>Prochaines actions</strong>'
        '<p>Aucune action prévue sous sept jours.</p></div>'
    )

    groups = []
    for group_name, statuses in PIPELINE_GROUPS:
        grouped = [(url, entry, status) for url, entry, status in reversed(records) if status in statuses]
        cards = []
        for url, entry, status in grouped:
            follow_up = str(entry.get("follow_up") or "")
            deadline = str(entry.get("deadline") or "")
            availability = "Dans les flux actuels" if url in live else "Absente des flux — vérifier l'annonce"
            cards.append(
                '<article class="pipeline-card">'
                f'<span class="tracking-stage">{html.escape(status)}</span>'
                f'<a href="{html.escape(url, quote=True)}" target="_blank" rel="noopener noreferrer">'
                f'{html.escape(str(entry.get("title") or "Offre"))}</a>'
                f'<span class="pipeline-company">{html.escape(str(entry.get("company") or ""))} · '
                f'{html.escape(str(entry.get("location") or ""))}</span>'
                + (f'<span class="pipeline-action">Prochaine action : {html.escape(follow_up)}</span>'
                   if follow_up else '')
                + (f'<span>Date limite : {html.escape(deadline)}</span>' if deadline else '')
                + (f'<span>Candidature envoyée : {html.escape(str(entry["applied_at"]))}</span>'
                   if entry.get("applied_at") else '')
                + f'<span class="pipeline-availability">{html.escape(availability)}</span>'
                + (f'<p>{html.escape(str(entry.get("note") or ""))}</p>' if entry.get("note") else '')
                + '</article>'
            )
        groups.append(
            '<section class="pipeline-column">'
            f'<h3>{html.escape(group_name)} <span>{len(grouped)}</span></h3>'
            '<div class="pipeline-column-cards">' + ("".join(cards) or '<p class="pipeline-no-cards">Aucune offre</p>')
            + '</div></section>'
        )
    return ('<div class="pipeline-dashboard"><div class="pipeline-top">'
            '<div class="pipeline-stats">' + summary + '</div>' + priority_panel + '</div>'
            '<div class="pipeline-columns">' + "".join(groups) + '</div></div>')
