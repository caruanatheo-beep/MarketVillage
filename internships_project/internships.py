"""Public employer career feeds for markets internships and early careers."""

from __future__ import annotations

import html
import json
import logging
import os
import re
import threading
import time
import unicodedata
from difflib import SequenceMatcher
from html.parser import HTMLParser
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, replace
from datetime import date, datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
from urllib.parse import parse_qsl, urljoin, urlparse
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
    "point72": "Point72",
    "janestreet": "Jane Street",
    "optiver": "Optiver",
    "imc": "IMC Trading",
    "flowtraders": "Flow Traders",
    "quberesearchandtechnologies": "Qube Research & Technologies",
    "21shares": "21shares",
}
LEVER = {
    "wisdomtree-2": "WisdomTree",
}
ASHBY = {}
WORKDAY = {
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
    "JobTeaser · recherche publique": "https://www.jobteaser.com/fr/job-offers?locale=fr",
    "BNP Paribas": "https://group.bnpparibas/emploi-carriere/toutes-offres-emploi",
    "BNP Paribas Asset Management": "https://group.bnpparibas/emploi-carriere/toutes-offres-emploi/bnp-paribas-asset-management",
    "BNP Paribas CIB": "https://careers.cib.bnpparibas/job-contract-type/internship/",
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
}
CAREER_LISTINGS = {
    "Crédit Mutuel / CIC": ("https://recrutement.creditmutuel.fr/fr/nos_offres.html?offres=true&tc=3",
                            "recrutement.creditmutuel.fr", "/fr/offre.html"),
    "Marex": ("https://www.marex.com/careers/career-opportunities",
              "www.marex.com", "/careers/career-opportunities/"),
    "Kepler Cheuvreux": ("https://keplercheuvreux.teamtailor.com/jobs",
                        "keplercheuvreux.teamtailor.com", "/jobs/"),
    "CACEIS": ("https://jobs.caceis.com/pages/offre/listeoffre.aspx?lcid=1036",
               "jobs.caceis.com", "/offre-de-emploi/"),
    "CFM": ("https://jobs.cfm.com/go/Internship/9276655/", "jobs.cfm.com", "/job/"),
    "La Banque Postale": ("https://www.labanquepostale.com/candidats/offres-d-emploi/nos-offres-d-emploi.html",
                          "www.labanquepostale.com", "/candidats/offres-d-emploi/nos-offres-d-emploi.job-"),
    "Ofi Invest": ("https://ofiinvestassetmanagement.flatchr.io/fr/company/ofiinvestassetmanagement/",
                   "ofiinvestassetmanagement.flatchr.io", "/fr/company/ofiinvestassetmanagement/vacancy/"),
}
ODDO_ALTAYS_LISTING = "https://recrutement.altays-progiciels.com/oddo/en/recherche.html"
ORACLE_CAREER_BOARDS = {
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
    r"credit desk|credit trading|credit derivatives|market risk|risque de marche|"
    r"salle des marches|dcm|ecm|alm|broker|broking|pricing|valuation|valorisation|negociat\w*|"
    r"portfolio management|portfolio manager|portfolio analytics|portfolio engineering|"
    r"portfolio construction|gestion de portefeuille\w*|gerant de portefeuille\w*|"
    r"multi.?gestion|obligataire\w*|"
    r"market research|recherche de marche|execution|negociation|buy.side|"
    r"treasury sales|liquidity sales|stir|repo|repurchase|fx swaps?)\b", re.IGNORECASE,
)
_NON_MARKET_ROLE = re.compile(
    r"\b(?:private equity|capital investissement|venture capital|growth equity|"
    r"leveraged finance|project finance|financement de projet|investment banking|"
    r"corporate finance|finance d.entreprise|mergers? and acquisitions?|m\s*&\s*a|"
    r"transaction banking|trade finance|irb|retail credit|credit retail|"
    r"risque de credit|back.office|middle.office|administrat\w*|accounting|comptabilit\w*|"
    r"corporate treasury|tresorerie d.entreprise|payment\w*|payments?|settlement|"
    r"kyc|compliance|conformit\w*|fund accounting|fund dealing|"
    r"(?:collateral|processing|operations|forex) officer|"
    r"immobilier\w*|real estate|property management)\b", re.IGNORECASE,
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
_refresh_first_seen: dict[str, str] = {}
CACHE_REFRESH_SECONDS = 3600
CACHE_PATH = Path(__file__).resolve().parent / "data" / "internships_cache.json"
JOBTEASER_CACHE_PATH = CACHE_PATH.with_name("jobteaser_sitemap_cache.json")
CACHE_SECONDS = CACHE_REFRESH_SECONDS
PUBLIC_UPDATE_DELAY_SECONDS = 3 * 3600
JOBTEASER_CACHE_SECONDS = 24 * 3600
SOURCE_CONNECTOR_VERSIONS = {"Société Générale Careers": 3, "BNP Paribas": 2}
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
}

# Brand icons are requested from the employer's own site. If an icon is absent,
# the card keeps its initials; no third-party logo service receives the visit.
COMPANY_ICON_HOSTS = {
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
}


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


def _normalized_offer_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or "").casefold())
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", normalized)).strip()


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
        start_period=job.start_period or previous.start_period,
        description=job.description or previous.description,
    )


def _company_icon(company: str) -> str:
    host = COMPANY_ICON_HOSTS.get(_canonical_company(company))
    return f"https://{host}/favicon.ico" if host else ""


def _plain_text(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", value or ""))).strip()


def _canonical_title(title: str) -> str:
    text = unicodedata.normalize("NFKD", title.casefold())
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = re.sub(r"^(?:(?:stage|internship|intern|v\.?i\.?e\.?)\s*[:\-–]\s*)+", "", text)
    text = text.replace("marchs", "marches")
    return re.sub(r"\W+", "", text)


def _cross_source_title(title: str) -> str:
    """Normalize optional internship prefixes for direct-site/JobTeaser matching."""
    text = unicodedata.normalize("NFKD", title.casefold())
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = re.sub(r"^(?:(?:stage|internship|intern)\b\W*)+", "", text)
    return re.sub(r"\W+", "", text)


def _jobteaser_duplicate(job: Opportunity, official: list[Opportunity]) -> bool:
    """Prefer a direct posting when a sitemap URL describes the same vacancy.

    JobTeaser slugs can name the parent group instead of the hiring affiliate.
    Keep that exception explicit: sharing a corporate group alone is not enough.
    """
    company = _canonical_company(job.company)
    title = _cross_source_title(job.title)
    for other in official:
        other_company = _canonical_company(other.company)
        affiliate = (company, other_company) == ("natixis", "mirova")
        if company != other_company and not affiliate:
            continue
        if job.kind != other.kind:
            continue
        if job.location and other.location and _is_paris(job.location) != _is_paris(other.location):
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


def _without_jobteaser_duplicates(jobs: list[Opportunity]) -> list[Opportunity]:
    official = [job for job in jobs if job.source != "JobTeaser · sitemap"]
    return [job for job in jobs if job.source != "JobTeaser · sitemap"
            or not _jobteaser_duplicate(job, official)]


def _canonical_company(company: str) -> str:
    text = unicodedata.normalize("NFKD", company.casefold())
    text = "".join(char for char in text if not unicodedata.combining(char))
    compact = re.sub(r"\W+", "", text)
    for variants, canonical in (
        (("bnpparibasassetmanagement", "bnpparibasam"), "bnpparibasam"),
        (("bnpparibascib", "bnpparibas"), "bnpparibas"),
        (("societegenerale", "societegenerale4"), "societegenerale"),
        (("creditagricolecib", "cacib"), "creditagricolecib"),
        (("ostrumassetmanagement", "ostrum"), "ostrum"),
        (("cprassetmanagement", "cpram"), "cpram"),
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
_PERIOD = rf"(?:\d{{1,2}}[/.]\d{{1,2}}[/.]\d{{4}}|(?:{_MONTH})\s+\d{{4}})"
_START = re.compile(
    rf"(?:date de début|début du stage|date (?:prévue de )?prise de (?:poste|fonction)|prise de poste|à pourvoir|a pourvoir|"
    rf"à partir de|a partir de|dès|des|start date|starting in|starting on|"
    rf"starts in|starts on|beginning in|begins in|commence en)\s*[:|\-]*\s*(?:le|en|au|from|in)?\s*(?P<period>{_PERIOD})",
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
    match = _START.search(_plain_text(text))
    return match.group("period") if match else ""


def _title_period(title: str) -> str:
    """A month in an early-career title is an explicit advertised cohort period."""
    match = re.search(rf"\b(?:{_MONTH})\s+\d{{4}}\b", title, re.IGNORECASE)
    return match.group(0) if match else ""


def start_month(period: str) -> str:
    """Return a start month only when the advertised date is valid."""
    text = period.strip().casefold()
    date_match = re.search(r"\b(\d{1,2})[/.](\d{1,2})[/.](\d{4})\b", text)
    if date_match:
        try:
            parsed = date(int(date_match.group(3)), int(date_match.group(2)), int(date_match.group(1)))
        except ValueError:
            return ""
        return parsed.isoformat()[:7]
    iso_match = re.search(r"\b(20\d{2})-(\d{2})(?:-(\d{2}))?\b", text)
    if iso_match:
        try:
            parsed = date(int(iso_match.group(1)), int(iso_match.group(2)), int(iso_match.group(3) or 1))
        except ValueError:
            return ""
        return parsed.isoformat()[:7]
    month_match = re.search(rf"\b({_MONTH})\s+(20\d{{2}})\b", text)
    if month_match:
        return f"{month_match.group(2)}-{_MONTH_ALIASES[month_match.group(1)]:02d}"
    return ""


def _priority_start(job: Opportunity) -> bool:
    """Rank explicitly advertised April–September 2027 starts first."""
    return "2027-04" <= start_month(job.start_period) <= "2027-09"


def _opportunity_sort_key(job: Opportunity) -> tuple:
    published = int(job.published.replace("-", "")) if re.fullmatch(r"\d{4}-\d{2}-\d{2}", job.published) else 0
    return (-int(_priority_start(job)), -job.score, -published, job.company.casefold(),
            job.title.casefold(), job.url.casefold())


def _recent_sort_key(job: Opportunity) -> tuple:
    published = int(job.published.replace("-", "")) if re.fullmatch(r"\d{4}-\d{2}-\d{2}", job.published) else 0
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
    query = _offer_search_text(query or "")
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
      and (not query or query in _offer_search_text(f"{job.title} {job.company} {job.location}"))
      and (not only_new or job.url not in seen)
      and (not hide_dismissed or job.url not in dismissed)
      and (not weekly or _published_this_week(job.published, today))
      and (not daily or job.published == today.isoformat())]
    return sorted(filtered, key=_recent_sort_key if sort_by == "recent" else _opportunity_sort_key)


def _is_paris(location: str) -> bool:
    return any(place in location.casefold() for place in PARIS_AREA + (
        "montrouge", "levallois-perret", "boulogne-billancourt", "saint-denis",
        "saint-quentin-en-yvelines", "issy-les-moulineaux",
    ))


def _is_international_location(location: str) -> bool:
    text = "".join(char for char in unicodedata.normalize("NFKD", location.casefold())
                   if not unicodedata.combining(char))
    french_regions = (
        "auvergne-rhone-alpes", "bourgogne-franche-comte", "bretagne", "centre-val de loire",
        "corse", "grand est", "hauts-de-france", "normandie", "nouvelle-aquitaine",
        "occitanie", "pays de la loire", "provence-alpes-cote d'azur", "ile-de-france",
        "île-de-france",
    )
    if (not text or _is_paris(location) or "france" in text or re.search(r"(?:,\s*fr|\bfrance)\s*$", text)
            or any(region in text for region in french_regions)):
        return False
    return any(hub in text for hub in HUBS if hub != "paris") or bool(
        re.search(r",\s*[a-z][a-z .'-]{1,40}$", text)
    )


def _plausible_location(location: str) -> bool:
    if not location or len(location) > 120:
        return False
    return not bool(re.search(
        r"veuillez s[ée]lectionner|tout d[ée]selectionner|d[ée]tail de l.offre|description du poste|flux rss",
        location, re.IGNORECASE,
    ))


def _market_relevant(title: str, company: str = "") -> bool:
    normalized = unicodedata.normalize("NFKD", title.casefold())
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
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


def _market_relevant_with_context(title: str, context: str = "") -> bool:
    """Allow investment-team roles only when an official description confirms context."""
    if _market_relevant(title):
        return True
    normalized = unicodedata.normalize("NFKD", context.casefold())
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    normalized_title = unicodedata.normalize("NFKD", title.casefold())
    normalized_title = "".join(char for char in normalized_title if not unicodedata.combining(char))
    if _NON_MARKET_ROLE.search(normalized_title):
        return False
    confirmed = re.search(
        r"equity investment teams|analysts?\s*/\s*portfolio managers?|"
        r"financial analysis of companies|investment opportunities|"
        r"cash and executions? on (?:the )?different markets|cash.*executions?.{0,60}marches|"
        r"portfolio liquidity|liquidite des portefeuilles|risque des portefeuilles|"
        r"market risk|risk management.*(?:markets?|portfolios?)|"
        r"credit analyst.{0,100}(?:issuer|bond|fixed income)|"
        r"analyste.{0,80}credit.{0,100}(?:obligat|obligation|bond)|"
        r"analyses? credit.{0,120}(?:emetteur|obligataire|obligations)",
        normalized,
    )
    return bool(confirmed)


def _excluded_employer(company: str) -> bool:
    """Only the user's explicit Palatine exclusion; no inferred affiliations."""
    normalized = unicodedata.normalize("NFKD", company.casefold())
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    return bool(re.search(r"\bpalatine\b", normalized))


def _family(title: str) -> str:
    title = unicodedata.normalize("NFKD", title.casefold())
    title = "".join(char for char in title if not unicodedata.combining(char))
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
    if re.search(r"\btrading\b|\btrader\b|\bstructur\w*\b|\bpricing\b|\bderivat\w*\b|\bfx\b|\brates\b", title):
        return "Trading / Structuring"
    if re.search(
        r"asset management|portfolio|fund management|investment management|"
        r"gestion d.?actifs|gestion de portefeuille|asset allocation|fund manager",
        title,
    ):
        return "Asset Management"
    if any(term in title for term in ("quant", "research", "analyst", "investment", "portfolio")):
        return "Quant / Research"
    return "Risk / Support"


def _kind(title: str, employment: str = "") -> str | None:
    text = f"{title} {employment}".casefold()
    if re.search(r"\bv\.?i\.?e\b", text):
        return "VIE"
    if ("graduate" in text or "new grad" in text or "new analyst" in text
            or "analyst program" in text or "analyst programme" in text):
        return "Graduate"
    if any(term in text for term in ("intern", "stage", "stagiaire", "seasonal employee",
                                     "off-cycle", "off cycle", "summer analyst", "summer associate")):
        return "Stage"
    return None


def _opportunity(title: str, company: str, location: str, employment: str,
                 url: str, published: str, start_period: str = "",
                 role_context: str = "") -> Opportunity | None:
    title = title.strip()
    location = location.strip()
    kind = _kind(title, employment)
    if not kind or not _market_relevant_with_context(title, role_context) or _excluded_employer(company) or not _plausible_location(location):
        return None
    parsed = urlparse(url)
    if not is_trusted_offer_url(url):
        return None
    paris = _is_paris(location)
    market_focus = any(term in title.casefold() for term in (
        "trading", "trader", "sales", "structur", "fixed income", "rates", "fx", "derivative", "dérivé"
    ))
    score = (100 if paris and kind == "Stage" else 70 if paris else 45) + (15 if market_focus else 0)
    return Opportunity(title, company, location, kind, url, published[:10], score, start_period,
                       _family(title), "", datetime.now(timezone.utc).date().isoformat())


def is_trusted_offer_url(url: str) -> bool:
    """Accept HTTPS job URLs only from career and provider hosts used by connectors."""
    allowed_hosts = {
        "jobs.smartrecruiters.com", "boards.greenhouse.io", "job-boards.greenhouse.io",
        "jobs.lever.co", "jobs.eu.lever.co", "jobs.ashbyhq.com",
        "careers.societegenerale.com", "mon-vie-via.businessfrance.fr",
        "group.bnpparibas", "careers.cib.bnpparibas", "bnppapply.tal.net", "jobs.ca-cib.com", "recrutement.creditmutuel.fr",
        "jobs.amundi.com", "www.jobs.amundi.com", "recrutement.arkea.com",
        "www.recrutement.arkea.com",
        "www.marex.com", "keplercheuvreux.teamtailor.com",
        "recrutement.bpce.fr", "jobs.caceis.com", "tikehau-capital-career.talentview.io", "jobs.cfm.com",
        "cm.comgest.com", "coveafinance-recrute.talent-soft.com",
        "www.labanquepostale.com", "icbpjb.fa.ocs.oraclecloud.com",
        "jpmc.fa.oraclecloud.com", "hdpc.fa.us2.oraclecloud.com", "ekbq.fa.em2.oraclecloud.com",
        "ofiinvestassetmanagement.flatchr.io", "recrutement.altays-progiciels.com",
        "www.groupama-gan-recrute.com", "bdf.wd103.myworkdayjobs.com",
        *(board[0] for board in WORKDAY.values()),
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
    for offset in range(0, 1000, 100):
        response = requests.get(
            url, params={"limit": 100, "offset": offset, "destination": "PUBLIC"}, timeout=(4, 12)
        )
        response.raise_for_status()
        payload = response.json()
        rows = payload.get("content") or []
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
        if len(rows) < 100 or offset + 100 >= int(payload.get("totalFound") or 0):
            break
    def enrich(job: Opportunity) -> Opportunity:
        reused = _cached_detail(job)
        if reused and reused.description:
            return replace(reused, source=job.source)
        try:
            detail = requests.get(
                f"{url}/{job.url.rsplit('/', 1)[-1]}", timeout=(4, 12)
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
    response = requests.get(url, params={"content": "true"}, timeout=(4, 12))
    response.raise_for_status()
    jobs: list[Opportunity] = []
    for item in response.json().get("jobs", []):
        job = _opportunity(
            str(item.get("title") or ""), company,
            str((item.get("location") or {}).get("name") or ""), "",
            str(item.get("absolute_url") or ""), "",
            _start_period(str(item.get("content") or "")) or _title_period(str(item.get("title") or "")),
        )
        if job:
            job = replace(job, description=_plain_text(str(item.get("content") or ""))[:12_000])
            jobs.append(replace(job, source=f"Site carrière · Greenhouse · {company}"))
    return jobs


def _lever_jobs(slug: str, company: str) -> list[Opportunity]:
    """Read the employer's published postings from Lever's public job-board API."""
    response = requests.get(
        f"https://api.lever.co/v0/postings/{slug}", params={"mode": "json"}, timeout=(4, 12)
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
        )
        if job:
            job = replace(job, description=_plain_text(description)[:12_000])
            jobs.append(replace(job, source=f"Site carrière · Lever · {company}"))
    return jobs


def _ashby_jobs(slug: str, company: str) -> list[Opportunity]:
    """Read only publicly listed roles from Ashby's public job-board API."""
    response = requests.get(
        f"https://api.ashbyhq.com/posting-api/job-board/{slug}", timeout=(4, 12)
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
        )
        if job:
            job = replace(job, description=_plain_text(description)[:12_000])
            jobs.append(replace(job, source=f"Site carrière · Ashby · {company}"))
    return jobs


def _socgen_jobs(_slug: str = "", _company: str = "") -> list[Opportunity]:
    """Read Société Générale's global public offer index, not only its French feed."""
    listing_url = "https://careers.societegenerale.com/en/Technical/all-job-offers"
    response = requests.get(listing_url, timeout=(4, 15))
    response.raise_for_status()
    listing = _CareerHTML()
    listing.feed(response.text)
    candidates: dict[str, str] = {}
    for href, label in listing.links:
        url = urljoin(listing_url, href)
        parsed = urlparse(url)
        title = re.sub(r"\s+", " ", _plain_text(label)).strip()
        if (parsed.scheme == "https" and parsed.hostname == "careers.societegenerale.com"
                and parsed.path.startswith("/en/job-offers/") and _market_relevant(title)):
            candidates[url] = title
    if not candidates:
        raise ValueError("catalogue mondial Société Générale lisible, mais aucun lien marchés détecté")

    hub_pattern = "|".join(re.escape(hub) for hub in sorted(HUBS, key=len, reverse=True))

    def read_detail(item: tuple[str, str]) -> Opportunity | None:
        url, fallback_title = item
        try:
            detail = requests.get(url, timeout=(4, 12))
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
                            if start_match else "")
            contract_match = re.search(
                r"\b(Internship|V\.I\.E\.|VIE|Graduate(?:\s+Programme|\s+Program)?|Trainee)\b",
                text, re.IGNORECASE,
            )
            employment = contract_match.group(1) if contract_match else ""
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
        self.links: list[tuple[str, str]] = []
        self.events: list[tuple[str, str, str]] = []
        self._skip = 0
        self._heading: list[str] | None = None
        self._heading_tag: str | None = None
        self._anchor: tuple[str, list[str]] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "nav", "footer"}:
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
        if tag in {"script", "style", "nav", "footer"}:
            self._skip = max(0, self._skip - 1)
            return
        if self._skip:
            return
        if tag == self._heading_tag and self._heading is not None:
            heading = " ".join(self._heading)
            self.headings.append(heading)
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


def _career_detail(url: str, company: str, fallback_title: str = "",
                   html_override: str | None = None) -> Opportunity | None:
    portal_company = company
    if html_override is None:
        response = requests.get(url, timeout=(4, 12))
        response.raise_for_status()
        page_html = response.text
    else:
        page_html = html_override
    page = _CareerHTML()
    page.feed(page_html)
    text = " ".join(page.parts)
    explicit_start = ""
    offer_text = text.split("Détail de l'offre", 1)[-1]
    if company == "BNP Paribas" and "cette offre est déjà pourvue" in text.casefold():
        return None
    if company == "Crédit Mutuel / CIC" and "CREDIT INDUSTRIEL ET COMMERCIAL" in text:
        company = "CIC"
    if portal_company == "Crédit Mutuel / CIC" and "Crédit Mutuel Asset Management" in text:
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
    structured_title = str(structured.get("title") or "").strip()
    title = next((heading for heading in page.headings if _market_relevant(heading)), "") or structured_title or fallback_title
    if not _market_relevant_with_context(title, _plain_text(str(structured.get("description") or ""))):
        return None
    location = ""
    published = _jsonld_job_posted(page_html)
    employment = str(structured.get("employmentType") or "")
    if isinstance(structured.get("jobLocation"), dict):
        address = structured["jobLocation"].get("address") or {}
        if isinstance(address, dict):
            location = ", ".join(filter(None, (str(address.get("addressLocality") or ""),
                                                str(address.get("addressRegion") or ""),
                                                str(address.get("addressCountry") or ""))))
    if company == "Marex":
        location_match = re.search(rf"{re.escape(title)}\s+(.+?)\s*,\s*(?:Capital Markets|Marex Solutions|Full-Time)", text)
        location = location_match.group(1) if location_match else ""
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
            published = datetime.strptime(published_match.group(1).replace(".", "/"), "%d/%m/%Y").date().isoformat()
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
                published = datetime.strptime(posted_match.group(1), "%d/%m/%Y").date().isoformat()
    if company == "BNP Paribas" and not location:
        location_match = re.search(rf"{re.escape(title)}\s+Stage\s+Temps plein\s+(.+?)\s+Postuler", text)
        location = location_match.group(1) if location_match else ""
    if portal_company == "BNP Paribas" and urlparse(url).hostname == "group.bnpparibas":
        location = re.sub(r"\s*\(Ce lien s'ouvre dans un nouvel onglet\)\s*$", "", location).strip()
    if company == "BNP Paribas" and urlparse(url).hostname == "careers.cib.bnpparibas":
        location_match = re.search(r"\bLocation:\s*(.+?)(?=\s+(?:Job/mission:|Reference:|About the job))", text)
        location = location_match.group(1).strip() if location_match else ""
        contract_match = re.search(r"\bEmployment contract:\s*(Internship|Trainee|VIE|Graduate)", text, re.IGNORECASE)
        employment = contract_match.group(1) if contract_match else employment
    if company == "Marex" and not location:
        location_match = re.search(rf"{re.escape(title)}\s+(.+?),\s+.+?,\s+Full-Time", text)
        location = location_match.group(1) if location_match else ""
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
    job = _opportunity(title, company, location, employment, url, published,
                       explicit_start or _start_period(full_description) or _title_period(title), role_context=role_context)
    return replace(job, source=f"Site carrière · {urlparse(url).hostname}", description=full_description[:12_000]) if job else None


def _render_public_career_page(url: str, link_selector: str) -> str:
    """Render a public careers page when its listings are JavaScript-only."""
    try:
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise ValueError("Playwright requis pour lire la liste publique rendue en JavaScript") from exc
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
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


def _bnp_group_jobs(company: str, listing_url: str) -> list[Opportunity]:
    """Read BNP's public career listings in a regular browser window."""
    try:
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise ValueError("Playwright requis pour lire les offres publiques BNP Paribas") from exc

    host, path_prefix = "group.bnpparibas", "/emploi-carriere/offre-emploi/"
    errors: list[str] = []
    candidates: dict[str, str] = {}
    try:
        with sync_playwright() as playwright:
            # BNP serves the public listings to graphical Chromium, but returns HTTP 403 headless.
            browser = playwright.chromium.launch(headless=False)
            try:
                page = browser.new_page()
                response = page.goto(listing_url, wait_until="domcontentloaded", timeout=20_000)
                if response is not None and response.status >= 400:
                    raise ValueError(f"liste BNP en HTTP {response.status}; aucun contournement tenté")
                try:
                    page.locator(f'a[href*="{path_prefix}"]').first.wait_for(timeout=8_000)
                except PlaywrightTimeoutError:
                    pass

                # Use the site's ordinary public "show more" control, with a strict cap.
                for _ in range(40):
                    hrefs = page.locator("a").evaluate_all("els => els.map(a => a.href)")
                    before = len({href for href in hrefs if urlparse(href).hostname == host
                                  and urlparse(href).path.startswith(path_prefix)})
                    more = page.get_by_text(re.compile(r"voir plus d.?offres", re.IGNORECASE)).last
                    try:
                        if not more.is_visible(timeout=500):
                            break
                        more.click(timeout=1_500)
                        page.wait_for_timeout(500)
                    except PlaywrightTimeoutError:
                        break
                    hrefs = page.locator("a").evaluate_all("els => els.map(a => a.href)")
                    after = len({href for href in hrefs if urlparse(href).hostname == host
                                 and urlparse(href).path.startswith(path_prefix)})
                    if after <= before:
                        break

                listing_page = _CareerHTML()
                listing_page.feed(page.content())
                for href, label in listing_page.links:
                    offer_url = urljoin(listing_url, href)
                    parsed = urlparse(offer_url)
                    if (parsed.scheme == "https" and parsed.hostname == host
                            and parsed.path.startswith(path_prefix) and _market_relevant(label)):
                        candidates[offer_url] = label

                detail_company = "BNP Paribas" if company == "BNP Paribas Asset Management" else company
                jobs: list[Opportunity] = []
                for offer_url, label in candidates.items():
                    try:
                        detail_response = page.goto(offer_url, wait_until="domcontentloaded", timeout=8_000)
                        if detail_response is not None and detail_response.status >= 400:
                            errors.append(f"fiche HTTP {detail_response.status}")
                            continue
                        job = _career_detail(offer_url, detail_company, label, html_override=page.content())
                        if job and company == "BNP Paribas Asset Management" and job.company == "BNP Paribas":
                            job = replace(job, company="BNP Paribas Asset Management")
                        if job:
                            jobs.append(job)
                    except (PlaywrightTimeoutError, ValueError, TypeError) as exc:
                        errors.append(type(exc).__name__)
                if jobs:
                    return list({job.url: job for job in jobs}.values())
                if errors:
                    raise ValueError(f"fiches BNP non lisibles ({errors[0]})")
                if candidates:
                    raise ValueError("liens directs trouvés, mais aucune fiche ne correspond aux filtres")
                raise ValueError("aucun lien direct visible dans la liste BNP rendue")
            finally:
                browser.close()
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError(f"navigateur public BNP indisponible ({type(exc).__name__})") from exc


def _oddo_jobs() -> list[Opportunity]:
    """Read ODDO BHF's public Altays listing and parse official offer PDFs."""
    response = requests.get(ODDO_ALTAYS_LISTING, timeout=(4, 15))
    response.raise_for_status()
    listing = _CareerHTML()
    listing.feed(response.text)
    pdf_links: dict[str, str] = {}
    for href, label in listing.links:
        url = urljoin(ODDO_ALTAYS_LISTING, href)
        parsed = urlparse(url)
        if (parsed.scheme == "https" and parsed.hostname == "recrutement.altays-progiciels.com"
                and parsed.path.startswith("/oddo/") and parsed.path.casefold().endswith(".pdf")):
            pdf_links[url] = label
    if not pdf_links:
        rendered = _render_public_career_page(ODDO_ALTAYS_LISTING, "a[href$='.pdf']")
        listing = _CareerHTML()
        listing.feed(rendered)
        for href, label in listing.links:
            url = urljoin(ODDO_ALTAYS_LISTING, href)
            parsed = urlparse(url)
            if (parsed.scheme == "https" and parsed.hostname == "recrutement.altays-progiciels.com"
                    and parsed.path.startswith("/oddo/") and parsed.path.casefold().endswith(".pdf")):
                pdf_links[url] = label
    if not pdf_links:
        if "an error has occurred" in response.text.casefold():
            raise ValueError("moteur public Altays ODDO en erreur de chargement, aucune annonce lisible")
        raise ValueError("liste Altays ODDO accessible, mais aucun lien PDF direct")
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise ValueError("pypdf nécessaire pour lire les fiches PDF publiques ODDO BHF") from exc
    jobs: list[Opportunity] = []

    def read_offer(item: tuple[str, str]) -> tuple[str, str, str]:
        url, fallback_title = item
        try:
            offer = requests.get(url, timeout=(4, 15))
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
        published = datetime.strptime(posted_match.group(1), "%d/%m/%Y").date().isoformat() if posted_match else ""
        job = _opportunity(title, "ODDO BHF", location_match.group(1).strip() if location_match else "",
                           employment, url, published, _start_period(description) or _title_period(title), description)
        if job:
            jobs.append(replace(job, source="Site carrière · ODDO BHF Altays", description=description[:12_000]))
    if not jobs and detail_failures == min(len(pdf_links), 60):
        raise ValueError("les liens PDF ODDO sont exposés, mais aucune fiche n'a pu être chargée")
    return jobs


def _tikehau_jobs() -> list[Opportunity]:
    """Read Tikehau's public Talentview vacancies, rendering its JS-only board."""
    listing_url = "https://tikehau-capital-career.talentview.io/jobs"
    response = requests.get(listing_url, timeout=(4, 15))
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
    response = requests.get(listing_url, timeout=(4, 15))
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


def _career_page_jobs(company: str, config: tuple[str, str, str]) -> list[Opportunity]:
    listing, host, path_prefix = config
    links: dict[str, str] = {}
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
    successful_pages = 0
    direct_links = 0
    visited: set[str] = set()
    def read_listing(listing_url: str) -> tuple[str, str]:
        response = requests.get(listing_url, timeout=(4, 15))
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
                    continue
                successful_pages += 1
                page = _CareerHTML()
                page.feed(html)
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
                    market_label = _market_relevant(label) or (
                        company == "Ofi Invest" and bool(re.search(
                            r"analyste\s+(?:cr[eÃ©]dit|obligataire)|fixed\s+income\s+analyst|credit\s+analyst",
                            label, re.IGNORECASE,
                        ))
                    )
                    if market_label:
                        links[url] = label
    if not successful_pages and last_error:
        raise last_error
    if successful_pages and not direct_links:
        raise ValueError("aucun lien d'offre directe dans les pages carrières publiques")
    detail_errors: list[Exception] = []
    def load(pair: tuple[str, str]) -> Opportunity | None:
        try:
            job = _career_detail(pair[0], "BNP Paribas" if company == "BNP Paribas Asset Management" else company, pair[1])
            return replace(job, company="BNP Paribas Asset Management") if job and company == "BNP Paribas Asset Management" else job
        except (requests.RequestException, ValueError, TypeError) as exc:
            detail_errors.append(exc)
            return None
    with ThreadPoolExecutor(max_workers=5) as pool:
        jobs = [job for job in pool.map(load, list(links.items())) if job]
    if not jobs and detail_errors:
        raise detail_errors[0]
    return jobs


def _comgest_jobs(_slug: str = "", _company: str = "") -> list[Opportunity]:
    """Read Comgest's official internship page and validate each role from its PDF."""
    listing = "https://cm.comgest.com/fr/about-us/nos-collaborateurs/carrieres/stages"
    response = requests.get(listing, timeout=(4, 15))
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
            pdf_response = requests.get(pdf_url, timeout=(4, 15))
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
            jobs.append(replace(job, source="Site carrière · Comgest"))
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
    for base, pages in archives:
        for page_number in range(1, pages + 1):
            listing = base if page_number == 1 else f"{base}page/{page_number}/"
            try:
                response = requests.get(listing, timeout=(4, 10))
                response.raise_for_status()
                successful_pages += 1
            except requests.RequestException as exc:
                last_error = exc
                break
            page = _CareerHTML()
            page.feed(response.text)
            visible_text = " ".join(page.parts)
            for href, title in page.links:
                url = urljoin(listing, href)
                parsed = urlparse(url)
                if parsed.scheme != "https" or parsed.hostname != "careers.cib.bnpparibas" or not parsed.path.startswith("/jobs/"):
                    continue
                if not _market_relevant(title):
                    continue
                date_match = re.search(rf"{re.escape(title)}\s+(\d{{1,2}} [A-Za-z]+ \d{{4}})", visible_text)
                try:
                    published = datetime.strptime(date_match.group(1), "%d %B %Y").date().isoformat() if date_match else ""
                except ValueError:
                    published = ""
                candidates[url] = (title, published)

    if not successful_pages and last_error:
        raise last_error

    def load(pair: tuple[str, tuple[str, str]]) -> Opportunity | None:
        url, (title, published) = pair
        try:
            job = _career_detail(url, "BNP Paribas", title)
            return replace(job, published=published) if job else None
        except (requests.RequestException, ValueError, TypeError):
            return None

    with ThreadPoolExecutor(max_workers=5) as pool:
        return [job for job in pool.map(load, list(candidates.items())) if job]


def _bnp_tal_jobs(_slug: str = "", _company: str = "") -> list[Opportunity]:
    """Read BNP's public APAC applicant board and verify trainee descriptions."""
    board = "https://bnppapply.tal.net/candidate/jobboard/vacancy/3/adv/"
    response = requests.get(board, timeout=(4, 12))
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
            detail = requests.get(url, timeout=(4, 12))
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
    links: dict[str, str] = {}
    last_error: requests.RequestException | None = None
    successful_feeds = 0
    for contract in contracts:
        try:
            response = requests.get(
                f"https://{host}/handlers/offerRss.ashx",
                params={"LCID": 1036, "Rss_Contract": contract}, timeout=(4, 15),
            )
            response.raise_for_status()
            root = ElementTree.fromstring(response.content)
        except requests.RequestException as exc:
            last_error = exc
            continue
        successful_feeds += 1
        for item in root.findall(".//item"):
            title = _plain_text(item.findtext("title") or "")
            url = (item.findtext("link") or "").strip()
            if not _market_relevant(title) or urlparse(url).hostname not in {host, f"www.{host}"}:
                continue
            links[url] = title
    if not successful_feeds and last_error:
        raise last_error
    def load(pair: tuple[str, str]) -> Opportunity | None:
        try:
            return _career_detail(pair[0], company, pair[1])
        except (requests.RequestException, ValueError, TypeError):
            return None
    with ThreadPoolExecutor(max_workers=5) as pool:
        return [job for job in pool.map(load, list(links.items())) if job]


def _ca_cib_jobs(_slug: str = "", _company: str = "") -> list[Opportunity]:
    return _career_rss_jobs("Crédit Agricole CIB", "jobs.ca-cib.com", (579, 1478))


def _amundi_jobs(_slug: str = "", _company: str = "") -> list[Opportunity]:
    return _career_rss_jobs("Amundi", "jobs.amundi.com", (579, 1478))


def _arkea_jobs(_slug: str = "", _company: str = "") -> list[Opportunity]:
    return _career_rss_jobs("Crédit Mutuel Arkéa", "recrutement.arkea.com", (1798,))


def _covea_finance_jobs(_slug: str = "", _company: str = "") -> list[Opportunity]:
    """Read Covéa Finance's public Talentsoft RSS feed for internship offers."""
    return _career_rss_jobs("Covéa Finance", "coveafinance-recrute.talent-soft.com", (579,))


def _bpce_open_data_jobs(_slug: str = "", _company: str = "") -> list[Opportunity]:
    """Use the public BPCE dataset; never synthesize a direct offer URL."""
    endpoint = ("https://bpce.opendatasoft.com/api/explore/v2.1/catalog/datasets/"
                "groupe-bpce-offres-emploi/exports/json")
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
            published = datetime.strptime(published, "%d/%m/%Y").date().isoformat()
        job = _opportunity(title, company, location, contract, link, published,
                           _start_period(description) or _title_period(title))
        if job:
            jobs.append(replace(job, source="Site carrière · BPCE Open Data"))
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
    """Read public sitemap URLs once daily; JobTeaser detail pages are not queried."""
    now = datetime.now(timezone.utc)
    cached: list[Opportunity] = []
    try:
        payload = json.loads(JOBTEASER_CACHE_PATH.read_text(encoding="utf-8"))
        if payload.get("version") == 2:
            cached = [Opportunity(**row) for row in payload.get("jobs", [])]
            if (now - datetime.fromisoformat(payload["updated"])).total_seconds() < JOBTEASER_CACHE_SECONDS:
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
        temporary.write_text(json.dumps({"version": 2, "updated": now.isoformat(),
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


def _workday_jobs(company: str, board: tuple[str, str, str]) -> list[Opportunity]:
    host, tenant, site = board
    base = f"https://{host}/wday/cxs/{tenant}/{site}"
    def search(term: str) -> list[tuple[str, Opportunity]]:
        found: list[tuple[str, Opportunity]] = []
        for offset in range(0, 400, 20):
            response = requests.post(
                f"{base}/jobs",
                json={"appliedFacets": {}, "limit": 20, "offset": offset, "searchText": term},
                timeout=(4, 12),
            )
            response.raise_for_status()
            payload = response.json()
            rows = payload.get("jobPostings") or []
            for item in rows:
                path = str(item.get("externalPath") or "")
                if not path.startswith("/job/"):
                    continue
                job = _opportunity(
                    str(item.get("title") or ""), company, str(item.get("locationsText") or ""), "",
                    f"https://{host}/en-US/{site}{path}",
                    _workday_publication_date(posted_on=item.get("postedOn")),
                )
                if job:
                    found.append((path, replace(job, source=f"Workday {company}")))
            if len(rows) < 20 or offset + 20 >= int(payload.get("total") or 0):
                break
        return found

    candidates: dict[str, Opportunity] = {}
    with ThreadPoolExecutor(max_workers=4) as pool:
        for result in pool.map(search, ("Paris", "Trading", "Graduate", "VIE",
                                        "Intern", "Markets", "Quantitative")):
            candidates.update(result)

    def enrich(pair: tuple[str, Opportunity]) -> Opportunity:
        path, job = pair
        reused = _cached_detail(job)
        if reused and reused.description:
            return replace(reused, source=f"Workday career site · {company}")
        try:
            response = requests.get(base + path, timeout=(4, 12))
            response.raise_for_status()
            info = response.json().get("jobPostingInfo") or {}
            description = str(info.get("jobDescription") or "")
            detail_company = job.company
            if re.search(r"Rothschild\s*&\s*Co\s+Redburn|\bRedburn\b", description, re.IGNORECASE):
                detail_company = "Rothschild & Co Redburn"
            elif re.search(r"Rothschild\s*&\s*Co\s+(?:Asset|Wealth) Management", description[:1_500], re.IGNORECASE):
                detail_company = "Rothschild & Co Asset Management"
            return replace(
                job,
                company=detail_company,
                start_period=_start_period(description) or _title_period(job.title),
                location=str(info.get("location") or job.location),
                published=_workday_publication_date(info.get("startDate"), info.get("postedOn")) or job.published,
                description=_plain_text(description)[:12_000],
                source=f"Workday career site · {detail_company}",
            )
        except (requests.RequestException, ValueError, TypeError):
            return job

    selected = sorted(candidates.items(), key=lambda pair: -pair[1].score)[:50]
    with ThreadPoolExecutor(max_workers=6) as pool:
        enriched = dict(zip((path for path, _ in selected), pool.map(enrich, selected)))
    return [enriched.get(path, job) for path, job in candidates.items()]


def _banque_de_france_jobs(_slug: str = "", _company: str = "") -> list[Opportunity]:
    """The Banque de France lists contract type only on Workday detail pages."""
    host, tenant, site = "bdf.wd103.myworkdayjobs.com", "bdf", "recrutement-banque-de-France"
    base = f"https://{host}/wday/cxs/{tenant}/{site}"
    candidates: dict[str, tuple[str, str, str]] = {}
    detail_errors: list[Exception] = []
    for term in ("march", "quant", "trading", "ALM"):
        for offset in range(0, 200, 20):
            response = requests.post(base + "/jobs", json={
                "appliedFacets": {}, "limit": 20, "offset": offset, "searchText": term,
            }, timeout=(4, 12))
            response.raise_for_status()
            payload = response.json()
            rows = payload.get("jobPostings") or []
            for item in rows:
                path = str(item.get("externalPath") or "")
                title = str(item.get("title") or "")
                if path.startswith("/job/") and (_market_relevant(title) or "analyste des marchés" in title.casefold()):
                    candidates[path] = (title, str(item.get("locationsText") or ""),
                                        str(item.get("postedOn") or ""))
            if len(rows) < 20 or offset + 20 >= int(payload.get("total") or 0):
                break

    def load(pair: tuple[str, tuple[str, str, str]]) -> Opportunity | None:
        path, (title, location, posted_on) = pair
        try:
            response = requests.get(base + path, timeout=(4, 12))
            response.raise_for_status()
            info = response.json().get("jobPostingInfo") or {}
            description = _plain_text(str(info.get("jobDescription") or ""))
            if not re.search(r"Type de recrutement\s*:[\s\u200e\u200f]*Stage\b", description, re.IGNORECASE):
                return None
            job = _opportunity(title, "Banque de France", str(info.get("location") or location),
                               "Stage", f"https://{host}/fr-FR/{site}{path}",
                               _workday_publication_date(info.get("startDate"), info.get("postedOn") or posted_on),
                               _start_period(description), description)
            return replace(job, description=description[:12_000], source="Site carrière · Banque de France") if job else None
        except (requests.RequestException, ValueError, TypeError) as exc:
            detail_errors.append(exc)
            return None

    with ThreadPoolExecutor(max_workers=6) as pool:
        jobs = [job for job in pool.map(load, candidates.items()) if job]
    if not jobs and detail_errors:
        raise detail_errors[0]
    return jobs


def _oracle_jobs(board_name: str, board: tuple[str, str, str]) -> list[Opportunity]:
    """Read public Oracle Candidate Experience postings and their public details."""
    root, site, employer = board
    board_url = f"{root}/hcmUI/CandidateExperience/en/sites/{site}/jobs"
    endpoint = f"{root}/hcmRestApi/resources/11.13.18.05/recruitingCEJobRequisitions"
    session = requests.Session()
    session.headers.update({"Accept": "application/json", "User-Agent": "MarketsCareerDesk/1.0"})
    response = session.get(board_url, timeout=(4, 12))
    response.raise_for_status()
    site_number_match = re.search(
        r"(?:siteNumber|site_number)\s*[\"']?\s*[:=]\s*[\"']?([A-Za-z0-9_-]+)",
        response.text, re.IGNORECASE,
    )
    site_number = site_number_match.group(1) if site_number_match else site

    def requisitions(offset: int) -> tuple[list[dict], int]:
        response = session.get(endpoint, params={
            "onlyData": "true", "expand": "requisitionList",
            "finder": f"findReqs;siteNumber={site_number},limit=100,offset={offset}",
        }, timeout=(4, 12))
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
        return rows, total

    candidates: dict[str, tuple[Opportunity, str]] = {}
    for offset in range(0, 3000, 100):
        rows, total = requisitions(offset)
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
            short_description = str(row.get("ExternalDescription") or row.get("ShortDescription") or "")
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
            )
            if job:
                job = replace(job, description=description_text[:12_000])
                candidates[job_id] = (replace(job, source=f"Site carrière · Oracle · {board_name}"), description_text)
        if not rows or offset + len(rows) >= total:
            break

    def enrich(item: tuple[str, tuple[Opportunity, str]]) -> Opportunity:
        job_id, (job, existing_description) = item
        reused = _cached_detail(job)
        if reused and reused.description:
            return reused
        detail_url = f"{root}/hcmRestApi/resources/11.13.18.05/recruitingCEJobRequisitionDetails/{job_id}"
        try:
            response = session.get(detail_url, params={"onlyData": "true", "expand": "all",
                                                       "finder": f"ById;Id={job_id},siteNumber={site_number}"},
                                   timeout=(4, 12))
            response.raise_for_status()
            payload = response.json()
            nodes = [payload]
            while nodes:
                node = nodes.pop()
                if isinstance(node, list):
                    nodes.extend(node)
                elif isinstance(node, dict):
                    nodes.extend(value for value in node.values() if isinstance(value, (dict, list)))
                    for key in ("ExternalDescription", "JobDescription", "Description", "ShortDescription"):
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

    selected = list(candidates.items())[:60]
    with ThreadPoolExecutor(max_workers=6) as pool:
        enriched = dict(zip((job_id for job_id, _ in selected), pool.map(enrich, selected)))
    return [enriched.get(job_id, item[0]) for job_id, item in candidates.items()]


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
                timeout=(4, 12),
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
                    datetime.fromisoformat(str(item.get("updated") or ""))
                except (TypeError, ValueError):
                    continue
                _source_job_cache[str(name)] = {
                    "updated": item["updated"], "jobs": jobs,
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
    if name == "JobTeaser · sitemap":
        return JOBTEASER_CACHE_SECONDS
    if name in {"BNP Paribas", "BNP Paribas VIE", "BNP Paribas Asset Management", "ODDO BHF", "Tikehau Capital"}:
        return 4 * 3600
    if name in {"Comgest", "Groupama AM", "Cov\u00e9a Finance", "BPCE Open Data",
                "Cr\u00e9dit Mutuel Ark\u00e9a", "Amundi", "Cr\u00e9dit Agricole CIB"} or loader in {
            _career_page_jobs, _career_rss_jobs, _comgest_jobs, _groupama_am_jobs}:
        return 3 * 3600
    return CACHE_REFRESH_SECONDS


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
    if (not force and not connector_version_changed and cached_at and
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
    except Exception as exc:
        elapsed = round((time.perf_counter() - started) * 1000)
        if isinstance(exc, requests.HTTPError) and exc.response is not None:
            reason = f"HTTP {exc.response.status_code}"
        elif isinstance(exc, requests.Timeout):
            reason = "délai dépassé"
        elif isinstance(exc, ValueError):
            reason = str(exc)[:90] or "réponse invalide"
        else:
            reason = type(exc).__name__
        checked_at = datetime.now(timezone.utc).isoformat()
        if cached_jobs:
            check = {"status": "stale", "count": len(cached_jobs), "checked_at": checked_at,
                     "last_success": str((cached or {}).get("updated") or ""), "error": reason,
                     "duration_ms": elapsed, "cache_status": "stale"}
            return cached_jobs, check, f"{name}: {reason} (anciennes offres conservées)"
        check = {"status": "error", "count": None, "checked_at": checked_at,
                 "last_success": previous_check.get("last_success", ""), "error": reason,
                 "duration_ms": elapsed, "cache_status": "none"}
        return [], check, f"{name}: {reason}"


def _deduplicate_opportunities(jobs: list[Opportunity]) -> list[Opportunity]:
    jobs = _without_jobteaser_duplicates(jobs)
    unique: dict[tuple[str, str, str], Opportunity] = {}
    for job in jobs:
        if (_excluded_employer(job.company) or not _market_relevant_with_context(job.title, job.description)
                or (job.source != "JobTeaser · sitemap" and not _plausible_location(job.location))):
            continue
        location_key = "paris-area" if _is_paris(job.location) else job.location.casefold()
        key = (_canonical_title(job.title), _canonical_company(job.company), location_key)
        previous = unique.get(key)
        if previous is None or (previous.source == "JobTeaser · sitemap" and job.source != "JobTeaser · sitemap") or (
            previous.source == job.source and not previous.start_period and job.start_period
        ) or (previous.source == job.source and not previous.description and job.description):
            unique[key] = job
    return sorted(unique.values(), key=_opportunity_sort_key)


def _date_detected_offer(job: Opportunity, previous: Opportunity | None, today: date) -> Opportunity:
    if job.published and not job.published_inferred:
        return job
    if previous and previous.published and not previous.published_inferred:
        return replace(job, published=previous.published, published_inferred=False)
    candidates = [value for value in (job.published, previous.published if previous else "",
                                      _refresh_first_seen.get(job.url, ""))
                  if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value)]
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



def _fetch_opportunities_progressive() -> tuple[list[Opportunity], list[str]]:
    """Collect source caches concurrently and publish each completed source immediately."""
    global _source_counts, _source_checks
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
        ("Soci\u00e9t\u00e9 G\u00e9n\u00e9rale Careers", _socgen_jobs, ("", "")),
        ("Business France VIE", _vie_jobs, ("", "")),
        ("Cr\u00e9dit Agricole CIB", _ca_cib_jobs, ("", "")),
        ("BNP Paribas CIB", _bnp_cib_jobs, ("", "")),
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
        ("BPCE Open Data", _bpce_open_data_jobs, ("", "")),
        ("JobTeaser \u00b7 sitemap", _jobteaser_jobs, ("", "")),
        ("ODDO BHF", lambda *_: _oddo_jobs(), ()),
        ("Tikehau Capital", lambda *_: _tikehau_jobs(), ()),
        ("Groupama AM", lambda *_: _groupama_am_jobs(), ()),
    ])
    tasks.extend((company, _workday_jobs, (company, board)) for company, board in WORKDAY.items())
    tasks.extend((name, _oracle_jobs, (name, board)) for name, board in ORACLE_CAREER_BOARDS.items())
    tasks.extend((company, _career_page_jobs, (company, config))
                 for company, config in CAREER_LISTINGS.items())

    with _lock:
        checks = {name: dict(check) for name, check in _source_checks.items()}
    collected: list[Opportunity] = []
    errors: list[str] = []
    counts: dict[str, int] = {}
    with ThreadPoolExecutor(max_workers=12, thread_name_prefix="internships") as pool:
        futures = {pool.submit(_collect_source, name, loader, args, _force_source_refresh): name
                   for name, loader, args in tasks}
        for future in as_completed(futures):
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
            _write_source_job_cache()
            _publish_refresh_progress(collected, errors)
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
                and _market_relevant(str(item.get("title") or ""), str(item.get("company") or ""))
                and (item.get("source") == "JobTeaser · sitemap"
                     or _plausible_location(str(item.get("location") or "")))
                and not _excluded_employer(str(item.get("company") or ""))
                and (not item.get("deadline") or date.fromisoformat(item["deadline"]) >= today)]
        jobs = [replace(job, family=_family(job.title)) for job in jobs]
        # Older snapshots had undated offers. Their snapshot date is the
        # earliest detection date we can recover without inventing history.
        jobs = [replace(job, published=updated.date().isoformat(), published_inferred=True)
                if not job.published else job for job in jobs]
        first_seen = _first_seen_from_history(_read_history_document())
        jobs = [replace(job, published=min(job.published, first_seen[job.url]))
                if job.published_inferred and job.url in first_seen else job for job in jobs]
        jobs = _without_jobteaser_duplicates(jobs)
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
            }
    except (OSError, ValueError, TypeError, AttributeError):
        pass
    return {"version": 1, "baseline": None, "snapshots": [], "first_seen": {}}


def _first_seen_from_history(payload: dict) -> dict[str, str]:
    """Recover the earliest detection, including snapshots from before the durable index existed."""
    dates: dict[str, str] = {}
    def remember(url: object, value: object) -> None:
        if isinstance(url, str) and url and isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            dates[url] = min(dates.get(url, value), value)
    for url, value in (payload.get("first_seen") or {}).items():
        remember(url, value)
    for snapshot in [payload.get("baseline"), *(payload.get("snapshots") or [])]:
        if not isinstance(snapshot, dict):
            continue
        for job in snapshot.get("jobs") or []:
            if isinstance(job, dict) and job.get("published_inferred"):
                remember(job.get("url"), job.get("published"))
    return dates


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
                if job.published_inferred and job.published:
                    first_seen[job.url] = min(first_seen.get(job.url, job.published), job.published)
            payload["first_seen"] = first_seen
            if baseline:
                if payload.get("baseline") is not None:
                    return
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


def refresh_opportunities(force: bool = False, *, notify_email: bool = True,
                          fail_if_busy: bool = False) -> tuple[list[Opportunity], list[str], datetime]:
    global _cache, _last_attempt, _force_source_refresh, _refresh_previous_jobs, _refresh_first_seen
    if not _refresh_guard.acquire(blocking=False):
        if fail_if_busy:
            raise RuntimeError("Une autre collecte est déjà en cours.")
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
        _refresh_first_seen = _first_seen_from_history(_read_history_document())
        for job in previous_jobs.values():
            if job.published_inferred and job.published:
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
        stale = snapshot is None or not _source_checks or (now - snapshot[0]).total_seconds() >= CACHE_SECONDS
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
                threading.Event().wait(CACHE_SECONDS)
                load_opportunities(force=False)

        _hourly_worker = threading.Thread(target=run, daemon=True, name="internship-hourly-refresh")
        _hourly_worker.start()


def _utc_display_stamp(value: datetime) -> str:
    # Legacy timestamps without an offset already represent UTC.
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")


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
        f'<span class="results-updated">Mis à jour {html.escape(stamp)}</span>'
        + (f'<span class="results-warning">{len(visible_errors)} sources indisponibles</span>' if visible_errors else '')
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
            f'<span class="job-fact kind">{html.escape(job.kind)}</span>'
            f'<span class="job-fact">{html.escape(job.family)}</span>'
            + (f'<span class="job-fact start">Début : {html.escape(job.start_period)}</span>'
               if job.start_period else '')
            + (f'<span class="job-fact deadline">Limite : {html.escape(job.deadline)}</span>'
               if job.deadline else '')
        )
        publication = (f'Publication inconnue<br>Détectée le {html.escape(job.published)}'
                       if job.published_inferred else f'Publié {html.escape(job.published or "date inconnue")}')
        content = (
            '<span class="job-card-header">'
            f'<span class="job-company-mark" aria-hidden="true">{html.escape(initials)}{company_mark}</span>'
            '<span class="job-company-block">'
            f'<span class="job-company">{html.escape(job.company)}</span>'
            f'<span class="job-location">{html.escape(job.location or "Lieu non indiqué")}</span></span>'
            f'<span class="job-published">{publication}</span>'
            '</span>'
            f'<strong class="job-title" title="{html.escape(job.title, quote=True)}">{html.escape(job.title)}</strong>'
            + f'<span class="job-card-tags">{details}{badges}</span>'
        )
        escaped_url = html.escape(job.url, quote=True)
        link = f'<a class="job-card-main" href="{escaped_url}" target="_blank" rel="noopener noreferrer">{content}</a>'
        footer = (
            '<div class="job-card-footer">'
            f'<span class="job-card-source"><span class="job-checked">{html.escape(job.source)} · '
            f'{"Sitemap lu le" if job.source == "JobTeaser · sitemap" else "Vérifié le"} '
            f'{html.escape(job.checked_at)}</span></span>'
            '<span class="job-card-actions">'
            f'<a class="internship-open" href="{escaped_url}" target="_blank" rel="noopener noreferrer">'
            f'{"Voir sur JobTeaser" if job.source == "JobTeaser · sitemap" else "Voir l’offre"} ↗</a>'
            '</span></div>'
        )
        tracked_status = normalize_status(entry.get("status")) if isinstance(entry, dict) else ""
        cards.append(
            '<article class="internship-card-container internship-card"'
            f' data-offer-url="{escaped_url}"'
            f' data-offer-title="{html.escape(job.title, quote=True)}"'
            f' data-offer-company="{html.escape(job.company, quote=True)}"'
            f' data-tracking-status="{html.escape(tracked_status, quote=True)}">'
            + link + footer + '</article>'
        )
    empty = ("Chargement des offres en cours…" if refreshing and not jobs else
             "Aucune offre pour ce filtre. Essaie une autre recherche ou actualise les sources.")
    body = "".join(cards) or f'<div class="calendar-empty">{empty}</div>'
    vie_link = (
        '<a class="internship-source-link" href="https://mon-vie-via.businessfrance.fr/en/offres" '
        'target="_blank" rel="noopener noreferrer">Explorer toutes les offres VIE sur le portail officiel Business France ↗</a>'
        if category in {"Toutes", "VIE"} else ""
    )
    checks = {} if delayed_updates else source_checks()
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
        duration = check.get("duration_ms")
        duration_label = f"{duration} ms" if isinstance(duration, (int, float)) else "-"
        if check.get("cache_status") == "fresh":
            duration_label = "Cache · " + duration_label
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
        + (f'<p>Indisponibles : {html.escape(", ".join(visible_errors))}</p>' if visible_errors else '')
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
            f'{source_details}{jobteaser_link}{bnp_link}'
            f'<div class="internship-grid">{body}</div>{vie_link}</section>')


def _published_this_week(published: str, today: date) -> bool:
    """Include publication dates from today and the preceding six calendar days."""
    try:
        published_date = date.fromisoformat(published)
    except (TypeError, ValueError):
        return False
    return today - timedelta(days=6) <= published_date <= today


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
        parsed = urlparse(url)
        if parsed.scheme != "https" or not parsed.hostname or len(url) > 2000:
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
