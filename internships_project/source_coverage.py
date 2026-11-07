"""Audited source inventory. A portal entry is never treated as a live feed."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SourceCoverage:
    status: str  # connected, shared, indirect, portal, blocked, unverified
    url: str = ""
    via: str = ""


SOURCE_COVERAGE: dict[str, SourceCoverage] = {
    # Banks
    "BNP Paribas": SourceCoverage("connected", "https://group.bnpparibas/emploi-carriere/toutes-offres-emploi/stage/france", "Public Playwright collector in graphical Chromium; requires an interactive desktop"),
    "Société Générale": SourceCoverage("connected", "https://careers.societegenerale.com/en/Technical/all-job-offers", "Global English job index and direct public offer pages; includes international locations"),
    "Crédit Agricole CIB": SourceCoverage("connected", "https://jobs.ca-cib.com/offre-de-emploi/liste-offres.aspx?mode=layer&lcid=1036"),
    "AXA": SourceCoverage("connected", "https://recrutement.axa.fr/recherche-d%27offres?acm=ALL&alrpm=ALL&ascf=%5B%7B%22key%22%3A%22custom_fields.LocalContractType%22%2C%22value%22%3A%22Stage%22%7D%5D", "Public Stage listing and official offer pages; market-role filtering"),
    "Santander CIB": SourceCoverage("connected", "https://santander.wd3.myworkdayjobs.com/SantanderCareers", "Public Workday CXS board; filtered by existing market-role, contract and hub rules"),
    "CIBC Capital Markets": SourceCoverage("connected", "https://cibc.wd3.myworkdayjobs.com/campus", "Public Workday CXS board; detail pages provide the job posting when available"),
    "TD Securities": SourceCoverage("connected", "https://td.wd3.myworkdayjobs.com/TD_Bank_Careers", "Public Workday CXS board; detail pages provide the job posting when available"),
    "OCBC Global Markets": SourceCoverage("connected", "https://ocbc.wd102.myworkdayjobs.com/External", "Public Workday CXS board; detail pages provide the job posting when available"),
    "UBS": SourceCoverage("portal", "https://www.ubs.com/global/en/careers/search-jobs.html", "Official Taleo/TGnewUI board is JavaScript/session dependent; public detail URLs currently report expired sessions, so no scraper is enabled"),
    "Barclays": SourceCoverage("connected", "https://barclays.wd3.myworkdayjobs.com/External_Career_Site_Barclays", "Public Workday CXS board; existing connector verified with live source diagnostics"),
    "Qube Research & Technologies": SourceCoverage("connected", "https://job-boards.greenhouse.io/quberesearchandtechnologies", "Public Greenhouse board; 2027 quantitative research and trading internships include Paris, London and Zurich"),
    "21shares": SourceCoverage("connected", "https://job-boards.greenhouse.io/21shares", "Public Greenhouse board; currently no vacancies listed"),
    "Natixis": SourceCoverage("shared", "https://recrutement.bpce.fr/", "BPCE / Natixis / BRED"),
    "CIC": SourceCoverage("shared", "https://recrutement.creditmutuel.fr/fr/nos_offres.html", "Crédit Mutuel / CIC"),
    "BRED": SourceCoverage("shared", "https://recrutement.bpce.fr/", "BPCE / Natixis / BRED"),
    "La Banque Postale": SourceCoverage("connected", "https://www.labanquepostale.com/candidats/offres-d-emploi/nos-offres-d-emploi.html", "Official HTML listing and detail pages"),
    "Crédit Mutuel Arkéa": SourceCoverage("connected", "https://recrutement.arkea.com/accueil.aspx"),
    "ODDO BHF": SourceCoverage("connected", "https://www.oddo-bhf.com/fr/decouvrez-nos-offres-demplois/", "Official embedded Altays listing with static and JavaScript-rendered PDF discovery; currently reports an Altays loading error when no PDFs are exposed"),
    "CACEIS": SourceCoverage("connected", "https://jobs.caceis.com/pages/offre/listeoffre.aspx?lcid=1036"),
    "Banque de France": SourceCoverage("connected", "https://bdf.wd103.myworkdayjobs.com/fr-FR/recrutement-banque-de-France", "Public Workday CXS board; contract verified on each detail page"),
    "Bpifrance": SourceCoverage("indirect", "https://talents.bpifrance.fr/opportunites/", "JobTeaser public sitemap only; official career site returned HTTP 403 during local checks"),
    "Banque Richelieu": SourceCoverage("portal", "https://banquerichelieu.com/recrutements", "Public recruitment page checked on 2026-11-07; no direct vacancy links or public feed exposed, only unsolicited applications; automatic collection is not enabled"),
    # Brokers
    "Aurel BGC": SourceCoverage("blocked", "https://www.bgcg.com/careers/", "BGC Group"),
    "BGC": SourceCoverage("blocked", "https://www.bgcg.com/careers/"),
    "Kepler Cheuvreux": SourceCoverage("connected", "https://keplercheuvreux.teamtailor.com/jobs"),
    "Tradition/TSAF/TSAF OTC": SourceCoverage("portal", "https://www.tradition.com/careers/launching-your-career.aspx"),
    "Tradition Investment Solutions": SourceCoverage("portal", "https://www.tradition.com/careers/launching-your-career.aspx", "Tradition"),
    "Marex": SourceCoverage("connected", "https://www.marex.com/careers/career-opportunities"),
    "Portzamparc": SourceCoverage("shared", "https://group.bnpparibas/emploi-carriere/toutes-offres-emploi", "BNP Paribas"),
    "Bernstein": SourceCoverage("unverified"),
    # Buy-side execution desks
    "Amundi Intermédiation": SourceCoverage("shared", "https://jobs.amundi.com/offre-de-emploi/liste-toutes-offres.aspx?lcid=1036", "Amundi"),
    "Natixis TradEx Solutions": SourceCoverage("shared", "https://recrutement.bpce.fr/", "BPCE / Natixis / BRED"),
    "Ofi Invest Intermediation Services": SourceCoverage("shared", "https://ofiinvestassetmanagement.flatchr.io/fr/company/ofiinvestassetmanagement/", "Ofi Invest public Flatchr board; employer branch retained when stated in posting"),
    "Exoé": SourceCoverage("unverified"),
    # Asset managers
    "Amundi": SourceCoverage("connected", "https://jobs.amundi.com/offre-de-emploi/liste-toutes-offres.aspx?lcid=1036"),
    "BNP Paribas AM": SourceCoverage("shared", "https://group.bnpparibas/emploi-carriere/toutes-offres-emploi/bnp-paribas-asset-management", "Public Playwright collector in graphical Chromium; requires an interactive desktop"),
    "Ostrum": SourceCoverage("shared", "https://recrutement.bpce.fr/", "BPCE / Natixis / BRED"),
    "Ofi Invest AM": SourceCoverage("connected", "https://ofiinvestassetmanagement.flatchr.io/fr/company/ofiinvestassetmanagement/", "Public Flatchr postings parsed from direct offer pages"),
    "Groupama AM": SourceCoverage("connected", "https://www.groupama-am.com/fra/fr/intermediaire/carriere/groupama-asset-management-carriere", "Official AM career page and its directly linked vacancies"),
    "Covéa Finance": SourceCoverage("connected", "https://coveafinance-recrute.talent-soft.com/handlers/offerRss.ashx?LCID=1036&Rss_Contract=579", "Talentsoft public RSS; no internships currently listed"),
    "Crédit Mutuel AM": SourceCoverage("shared", "https://recrutement.creditmutuel.fr/fr/nos_offres.html", "Crédit Mutuel / CIC"),
    "LBP AM": SourceCoverage("portal", "https://www.lbpam.com/fr/carrieres/liste-des-postes"),
    "CPR AM": SourceCoverage("shared", "https://jobs.amundi.com/offre-de-emploi/liste-toutes-offres.aspx?lcid=1036", "Amundi"),
    "BFT IM": SourceCoverage("shared", "https://jobs.amundi.com/offre-de-emploi/liste-toutes-offres.aspx?lcid=1036", "Amundi"),
    "Société Générale Gestion": SourceCoverage("shared", "https://jobs.amundi.com/offre-de-emploi/liste-toutes-offres.aspx?lcid=1036", "Amundi"),
    "Étoile Gestion": SourceCoverage("shared", "https://jobs.amundi.com/offre-de-emploi/liste-toutes-offres.aspx?lcid=1036", "Amundi"),
    "ODDO BHF AM": SourceCoverage("shared", "https://recrutement.altays-progiciels.com/oddo/fr/recherche.html", "Official ODDO BHF Altays connector; branch retained when stated in PDF"),
    "Rothschild & Co": SourceCoverage("connected", "https://rothschildandco.wd3.myworkdayjobs.com/Rothschildandco_Lateral", "Workday public board"),
    "Rothschild & Co AM": SourceCoverage("shared", "https://rothschildandco.wd3.myworkdayjobs.com/Rothschildandco_Lateral", "Workday Rothschild & Co; branch kept when identified in the posting"),
    "Lazard": SourceCoverage("connected", "https://icbpjb.fa.ocs.oraclecloud.com/hcmUI/CandidateExperience/en/sites/LazardStudentCareers/jobs", "Oracle Candidate Experience student and professional boards"),
    "J.P. Morgan": SourceCoverage("connected", "https://jpmc.fa.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1001/jobs", "Public Oracle Candidate Experience API and public requisition details"),
    "Goldman Sachs": SourceCoverage("connected", "https://hdpc.fa.us2.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CampusHiring/jobs", "Public Oracle Campus Candidate Experience API and requisition details"),
    "Schroders": SourceCoverage("connected", "https://ekbq.fa.em2.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_2/jobs", "Public Oracle Candidate Experience API and requisition details"),
    "Lazard Asset Management": SourceCoverage("shared", "https://icbpjb.fa.ocs.oraclecloud.com/hcmUI/CandidateExperience/en/sites/LazardStudentCareers/jobs", "Oracle Lazard; branch kept when identified in the posting"),
    "Lazard Frères Gestion": SourceCoverage("shared", "https://icbpjb.fa.ocs.oraclecloud.com/hcmUI/CandidateExperience/en/sites/LazardProfessionalCareers/jobs", "Oracle Lazard; branch kept when identified in the posting"),
    "Edmond de Rothschild AM": SourceCoverage("portal", "https://www.edmond-de-rothschild.com/fr/carrieres"),
    "Arkéa AM": SourceCoverage("shared", "https://recrutement.arkea.com/accueil.aspx", "Crédit Mutuel Arkéa"),
    "Federal Finance Gestion": SourceCoverage("shared", "https://recrutement.arkea.com/accueil.aspx", "Crédit Mutuel Arkéa"),
    "Schelcher Prince Gestion": SourceCoverage("unverified"),
    "Carmignac": SourceCoverage("portal", "https://www.carmignac.com/en-fr/about-us/careers"),
    "DNCA": SourceCoverage("shared", "https://recrutement.bpce.fr/", "BPCE / Natixis / BRED"),
    "La Financière de l’Échiquier": SourceCoverage("portal", "https://www.lfde.com/fr-fr/nous-connaitre/carrieres/"),
    "Sycomore": SourceCoverage("connected", "https://jobs.smartrecruiters.com/SycomoreAssetManagement"),
    "Moneta": SourceCoverage("portal", "https://www.moneta.fr/contact/stagiaires-apprentis"),
    "Comgest": SourceCoverage("connected", "https://cm.comgest.com/fr/about-us/nos-collaborateurs/carrieres/stages", "Official internship list and role PDFs; direct application links"),
    "Arbevel": SourceCoverage("unverified"),
    "Amiral Gestion": SourceCoverage("unverified"),
    "Mandarine Gestion": SourceCoverage("unverified"),
    "La Financière de l’Arc": SourceCoverage("unverified"),
    "Tocqueville Finance": SourceCoverage("unverified"),
    "Tikehau Capital": SourceCoverage("connected", "https://tikehau-capital-career.talentview.io/jobs", "Public Kelio/Talentview listings and detail pages rendered with Playwright when JavaScript is required; relative publication dates normalized"),
    "Axiom AI": SourceCoverage("unverified"),
    "LFIS": SourceCoverage("unverified"),
    "Ellipsis AM": SourceCoverage("unverified"),
    "IVO Capital Partners": SourceCoverage("unverified"),
    "Anaxis AM": SourceCoverage("unverified"),
    "Sanso IS": SourceCoverage("unverified"),
    "Richelieu Gestion": SourceCoverage("unverified"),
    "CFM": SourceCoverage("connected", "https://jobs.cfm.com/go/Internship/9276655/"),
    "ABC arbitrage": SourceCoverage("portal", "https://www.abc-arbitrage.com/fr/carriere/", "Employer routes vacancies to Welcome to the Jungle; no public listing endpoint has been confirmed"),
    "Exane AM": SourceCoverage("portal", "https://www.exaneam.com/fr/institutional/recrutement", "Official recruitment page only invites unsolicited applications; no public vacancy feed"),
    "Syquant": SourceCoverage("unverified"),
    "Quantology": SourceCoverage("unverified"),
    # Public ATS job board for an asset manager with markets products
    "WisdomTree": SourceCoverage("connected", "https://jobs.lever.co/wisdomtree-2", "Lever public job board"),
}
