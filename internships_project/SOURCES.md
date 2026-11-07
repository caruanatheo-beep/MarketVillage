# Sources d'offres : état au 26 octobre 2026

L'inventaire exhaustif des établissements demandés est dans [`source_coverage.py`](source_coverage.py). Les statuts ont un sens précis :

- **`connected`** : un connecteur interroge effectivement un flux, une API publique ou une liste de liens d'annonces officielles, puis vérifie les annonces. Cela ne garantit pas qu'une annonce pertinente existe actuellement.
- **`shared`** : un connecteur de groupe peut porter les annonces d'une filiale. Une filiale n'est attribuée comme employeur que lorsque l'annonce permet de la reconnaître ; elle peut sinon apparaître sous le nom du groupe.
- **`indirect`** : offres issues d’un flux tiers public, sans lecture des fiches sur le site employeur.
- **`portal`** : page carrière officielle disponible, mais sans extraction fiable d'annonces branchée. Ces pages ne créent aucune offre dans l'application.
- **`blocked`** : l'accès public au portail a été refusé (HTTP 403 lors de la vérification). Aucun contournement n'est tenté.
- **`unverified`** : aucun endpoint d'offres officiel et publiquement exploitable n'a été confirmé. Aucune URL ni offre n'est inventée.

## Connecteurs actifs

Depuis le 3 novembre 2026, la [Banque de France](https://bdf.wd103.myworkdayjobs.com/fr-FR/recrutement-banque-de-France) est interrogée par son flux Workday public. Le collecteur lit chaque fiche candidate pour confirmer « Stage » et garde la date de publication fournie par Workday ; un essai réel a remonté six stages de marché. Bpifrance est suivi **indirectement** dans le [sitemap JobTeaser](https://assets-cf.jobteaser.com/sitemaps/sitemap.xml) : cinq URL de stages de marché admissibles y ont été observées, sans date de publication ni lieu vérifiés. Son [site carrière officiel](https://talents.bpifrance.fr/opportunites/) renvoie HTTP 403 au client HTTP et à Chromium dans cet environnement.

| Source | Mécanisme | Établissements concernés |
| --- | --- | --- |
| [Stages BNP Paribas](https://group.bnpparibas/emploi-carriere/toutes-offres-emploi/stage), [VIE BNP Paribas](https://group.bnpparibas/emploi-carriere/toutes-offres-emploi/vie) et [BNP Paribas AM](https://group.bnpparibas/emploi-carriere/toutes-offres-emploi/bnp-paribas-asset-management) | Listes officielles mondiales de stages et VIE, et liste dédiée à la marque AM ; chaque fiche est vérifiée pour le métier, le contrat et le lieu | BNP Paribas, BNP Paribas AM, Portzamparc si l'annonce du groupe l'identifie |
| [BNP Paribas CIB](https://careers.cib.bnpparibas/job-contract-type/internship/) | Archive de stages officielle et fiches d'annonces | BNP Paribas CIB |
| [BNP Paribas APAC](https://bnppapply.tal.net/candidate/jobboard/vacancy/3/adv/) | Portail de candidature public sur un autre domaine ; chaque fiche « Trainee » est lue pour confirmer stage, métier et lieu | BNP Paribas, notamment Hong Kong ; aucune offre parisienne déduite de ce portail |
| [Société Générale](https://careers.societegenerale.com/) | Connecteur carrière existant | Société Générale |
| [Crédit Agricole CIB](https://jobs.ca-cib.com/offre-de-emploi/liste-offres.aspx?mode=layer&lcid=1036) | Flux RSS officiel Stage/VIE | Crédit Agricole CIB |
| [AXA · stages](https://recrutement.axa.fr/recherche-d%27offres?acm=ALL&alrpm=ALL&ascf=%5B%7B%22key%22%3A%22custom_fields.LocalContractType%22%2C%22value%22%3A%22Stage%22%7D%5D) | Liste publique paginée, puis fiches officielles avec date de publication | AXA ; seuls les stages liés aux investissements et marchés sont retenus |
| [CACEIS](https://jobs.caceis.com/pages/offre/listeoffre.aspx?lcid=1036) | Pages officielles et fiches directes vérifiées | CACEIS |
| [Amundi](https://jobs.amundi.com/offre-de-emploi/liste-toutes-offres.aspx?lcid=1036) | Flux RSS officiel Stage/VIE | Amundi ; CPR AM, BFT IM, Société Générale Gestion, Étoile Gestion, Amundi Intermédiation si la fiche nomme l'entité |
| [Covéa Finance](https://coveafinance-recrute.talent-soft.com/offre-de-emploi/tous-les-flux-rss.aspx) | Flux RSS public Talentsoft, filtré sur Stage et validé sur les fiches officielles | Covéa Finance ; aucune offre de stage visible lors du dernier contrôle |
| [BPCE Open Data](https://bpce.opendatasoft.com/explore/assets/groupe-bpce-offres-emploi/) | Export JSON public publié par le groupe ; seuls les liens directs `recrutement.bpce.fr/job/` sont acceptés | Natixis, BRED, Ostrum, DNCA, Natixis TradEx Solutions si la donnée nomme l'entité |
| [Crédit Mutuel / CIC](https://recrutement.creditmutuel.fr/fr/nos_offres.html) | Pages publiques et fiches directes | CIC, Crédit Mutuel AM si la fiche le précise |
| [Crédit Mutuel Arkéa](https://recrutement.arkea.com/accueil.aspx) | Flux RSS officiel | Arkéa, Arkéa AM, Federal Finance Gestion si la fiche le précise |
| [Marex](https://www.marex.com/careers/career-opportunities) | Pages de carrière et fiches directes | Marex |
| [Kepler Cheuvreux](https://keplercheuvreux.teamtailor.com/jobs) | Page Teamtailor et fiches directes | Kepler Cheuvreux |
| [Sycomore](https://jobs.smartrecruiters.com/SycomoreAssetManagement) | API publique SmartRecruiters | Sycomore |
| [CFM](https://jobs.cfm.com/go/Internship/9276655/) | Liste de stages officielle et fiches directes | CFM |
| [Comgest](https://cm.comgest.com/fr/about-us/nos-collaborateurs/carrieres/stages) | Liste officielle de stages, fiches PDF analysées pour le métier et la disponibilité, lien de candidature direct | Comgest |
| [WisdomTree](https://jobs.lever.co/wisdomtree-2) | API publique Lever ; seules les offres correspondant aux critères de marché, de contrat et de lieu sont gardées | WisdomTree |
| [La Banque Postale](https://www.labanquepostale.com/candidats/offres-d-emploi/nos-offres-d-emploi.html) | Liste HTML officielle paginée, puis fiche détaillée ; dates relatives converties uniquement depuis le libellé « Il y a X jours/semaines/mois » | La Banque Postale |
| [Rothschild & Co](https://rothschildandco.wd3.myworkdayjobs.com/Rothschildandco_Lateral) | Workday public CXS, pages et descriptions directes ; les branches Redburn et Asset Management sont conservées quand nommées dans la fiche | Rothschild & Co, Redburn, Asset Management |
| [Barclays](https://barclays.wd3.myworkdayjobs.com/External_Career_Site_Barclays) | Workday public CXS, déjà interrogé par le connecteur existant | Barclays ; diagnostic local du 26 octobre 2026 : 12 annonces admissibles retournées |
| [Santander CIB](https://santander.wd3.myworkdayjobs.com/SantanderCareers) | Workday public CXS ; filtre métier, contrat et places financières appliqué par le pipeline existant | Santander CIB ; le site officiel CIB renvoie vers ce tableau public |
| [Lazard Student Careers](https://icbpjb.fa.ocs.oraclecloud.com/hcmUI/CandidateExperience/en/sites/LazardStudentCareers/jobs) et [Professional Careers](https://icbpjb.fa.ocs.oraclecloud.com/hcmUI/CandidateExperience/en/sites/LazardProfessionalCareers/jobs) | API Candidate Experience Oracle paginée et fiche publique par offre ; les branches sont conservées seulement si indiquées dans la description | Lazard, Lazard Asset Management, Lazard Frères Gestion |

Les API publiques Lever servent uniquement pour les tableaux carrière publics de l’employeur. Elles ne renvoient pas toutes des annonces de marché admissibles : l’application conserve uniquement les stages, VIE ou graduate programmes dont le titre, le lieu et le contrat passent les filtres. Une donnée de publication inconnue reste inconnue.

Les connecteurs existants pour d'autres employeurs restent disponibles. Adzuna n'est plus interrogé et ses anciennes offres sont exclues du cache à la lecture. Seuls les liens HTTPS des domaines officiels ou de leurs plateformes de recrutement autorisées entrent dans les résultats. Lorsqu'un site répond avec une erreur ou qu'une fiche ne contient pas assez d'information pour valider contrat, métier ou ville, le connecteur n'invente pas ces champs et l'offre n'est pas affichée. La date de publication et la date de début restent vides quand elles sont absentes ; la date de vérification n'est pas présentée comme une date de publication.

Dans **Offres → État des sources**, un tableau replié par défaut indique pour chaque connecteur interrogé le nombre d'offres remontées, l'heure de sa dernière vérification et l'un des états « Disponible », « Aucune offre remontée » ou « Vérification impossible ». Le nombre est mesuré à la sortie du connecteur, avant le dédoublonnage entre sources et les filtres de la page. Zéro signifie seulement que ce connecteur n'a remonté aucune offre admissible lors de cette vérification ; ce n'est pas une preuve que l'employeur ne recrute pas. En cas d'erreur, le nombre reste inconnu plutôt que zéro. Ces diagnostics sont enregistrés dans `internships_cache.json` et restaurés au redémarrage. Un ancien cache sans diagnostics déclenche une vérification en arrière-plan. Les erreurs BNP ne sont pas répétées dans les messages d'alerte de la page ; leur état reste consultable dans ce tableau.

Le [moteur public JobTeaser](https://www.jobteaser.com/fr/job-offers?locale=fr) est proposé comme lien de consultation. Le 25 octobre 2026, les pages de recherche et une fiche publique ont répondu HTTP 403 au client HTTP de l'application, tout comme le portail SKEMA. Le [sitemap officiel](https://assets-cf.jobteaser.com/sitemaps/sitemap.xml) reste accessible : un connecteur expérimental y lit les URLs des fiches une fois par jour et ne demande jamais les pages bloquées. Il ne retient qu'un employeur suivi, un type de contrat et un métier clairement lisibles dans l'URL. Le lieu reste inconnu s'il n'apparaît pas explicitement dans l'URL. La date de modification du sitemap n'est pas présentée comme une date de publication : la première détection est enregistrée. Ces cartes ouvrent la fiche JobTeaser précise, sans prétendre connaître son lien employeur. Une URL ne prouve pas qu'une annonce est toujours ouverte ; les résultats JobTeaser sont signalés comme liens de sitemap, dédoublonnés face aux offres directes et exclus des briefs IA faute de description vérifiée. Le cache séparé `jobteaser_sitemap_cache.json` évite de télécharger à chaque heure les fichiers volumineux du sitemap.

## Autres pages carrière recensées

Le portail officiel [UBS Careers](https://www.ubs.com/global/en/careers/search-jobs.html) utilise une interface Taleo/TGnewUI. La recherche publique indexe actuellement le poste « 2027 Graduate Talent Program - Global Markets - Paris », mais la page de détail consultable sans session indique que le lien n'est plus valide / que la session a expiré. Aucun connecteur d'extraction n'est activé tant qu'une route publique stable et des liens directs vérifiables ne sont pas confirmés. Le portail reste listé comme référence, sans produire d'offres synthétiques.

La Banque Postale, Rothschild & Co et Lazard ont depuis été ajoutés comme connecteurs actifs ; leurs URLs ci-dessous restent des références officielles. Le statut de chaque entrée est tenu à jour dans `source_coverage.py`.

Le portail public Tikehau charge ses annonces en JavaScript. Son connecteur utilise maintenant Playwright sans authentification pour lire la liste et les fiches ; voir la section de diagnostic ci-dessous.

Le [portail BGC Group](https://www.bgcg.com/careers/), également utilisé comme point d'entrée d'Aurel BGC, a répondu HTTP 403 pendant la vérification. Il est classé `blocked` ; aucune offre n'en est extraite.

Le connecteur BNP Paribas groupe utilisait auparavant `requests` et recevait HTTP 403, ce qui ralentissait chaque actualisation sans trouver d'offres. Cette voie a été retirée. Les listes BNP France et BNP Paribas AM passent maintenant par Playwright/Chromium, lisent les liens publics et le bouton normal « Voir plus d'offres », puis ouvrent les fiches directes. Aucun accès authentifié ni mécanisme anti-bot n'est contourné. Le 3 novembre 2026, le portail groupe a renvoyé HTTP 403 avec requests et Chromium sans interface. Le même portail a répondu HTTP 200 dans un Chromium graphique, sans profil utilisateur ni connexion, et le collecteur a lu une fiche de stage en France et des fiches Asset Management. Ce mode demande une session graphique locale ; le diagnostic reste en erreur si elle est absente. Le portail CIB distinct a expiré côté HTTP sur cette machine. Le connecteur CIB reste distinct et consulte aussi la [page officielle Global Markets](https://careers.cib.bnpparibas/who-we-are/global-markets/) et la [catégorie Temporary Status](https://careers.cib.bnpparibas/job-domain/temporary-status/). Les diagnostics BNP ne génèrent pas de notifications récurrentes dans l'interface.

Le portail de candidatures [BNP Paribas APAC](https://bnppapply.tal.net/candidate/jobboard/vacancy/3/adv/) fournit une autre voie officielle. Son tableau affiche des intitulés parfois trop vagues (« Trainee ») ; le connecteur n'admet ces annonces que si la fiche détaille explicitement un stage de marché et sa localisation. Cette source peut apporter des postes internationaux, mais ne remplace pas le portail France pour les stages à Paris. Les annonces parisiennes déjà pourvues sur le site du groupe sont exclues, même si un moteur de recherche les indexe encore.

Pour distinguer un refus du client HTTP d’une absence d’offres, comparer les codes HTTP des pages publiques dans le navigateur graphique local. Le collecteur BNP utilise ce navigateur et ne lit que les listes et fiches accessibles sans connexion. Si la session graphique n’est pas disponible ou si BNP refuse aussi cet accès, les diagnostics restent visibles dans l’état des sources ; les liens JobTeaser demeurent une source indirecte non vérifiée.

Pour Bernstein, Exoé et les gérants restants marqués `unverified`, il faut encore confirmer une liste officielle de postes et ses liens directs avant de créer un connecteur. Une absence d'offre dans l'application ne signifie pas que l'établissement ne recrute pas.

## Règles de sélection et de données

Le filtre accepte les stages, VIE et graduate programmes de finance de marché dans les localisations suivies. Il couvre notamment Sales, Trading, Structuring, Pricing, Valuation, Market Risk, gestion de portefeuille, recherche de marché, négociation buy-side, Treasury Sales, Liquidity Sales, STIR, repo et FX swaps. Il exclut les fonctions administratives, back-office, middle-office, opérations, conformité, trésorerie d'entreprise, private equity, finance d'entreprise et les métiers immobiliers. Le mot « marché » seul ne qualifie plus un poste : il doit désigner explicitement les marchés financiers ou un autre métier de marché. Le titre ne suffit pas toujours pour distinguer un rôle mixte ; les annonces ambiguës doivent être revues manuellement.

Banque Palatine et Palatine AM sont exclues, y compris lorsqu'une annonce provient du portail BPCE ou d'un ancien cache. Aucune exclusion liée à une religion n'est déduite d'un nom de société ou de dirigeant ; aucune affiliation institutionnelle religieuse n'a été ajoutée sans vérification explicite.

Chaque annonce conservée porte son lien direct, son employeur identifié, son intitulé, sa localisation, ses dates disponibles et sa source. Quand la source ne donne pas de date de publication, l'application enregistre le jour de sa première détection et affiche « Détectée » devant cette date. Une actualisation ultérieure ne rajeunit pas l'annonce ; une nouvelle annonce trouvée un autre jour reçoit ce jour-là. Pour les anciens caches sans date, le jour du cache est la plus ancienne date de détection récupérable. Les alias d'entreprise servent au dédoublonnage, sans fusionner toutes les filiales d'un même groupe.

Le processus `app_internships.py` démarre une récupération à son lancement, puis en déclenche une toutes les heures tant qu'il tourne. Le cache est valable une heure. Le bouton d'actualisation garde son fonctionnement manuel. Le portail Open Data BPCE annonce quatre publications par jour et un arrêt du portail à partir de mai 2027 ; ce connecteur devra alors être migré vers sa nouvelle source officielle.

## Connecteurs ajoutés (26 octobre 2026)

| Employeur | Méthode et données prises | Résultat de l’inspection | Limite |
|---|---|---|---|
| [ODDO BHF](https://www.oddo-bhf.com/fr/decouvrez-nos-offres-demplois/) | Liste officielle Altays, fiches PDF directes ; titre, description, localisation, contrat, date de publication et début lorsqu’ils figurent dans la fiche | Connecteur actif ; sélection limitée aux rôles marchés et aux stages/VIE/graduate admissibles | L’accès local à la liste n’a pas pu être exécuté dans cet environnement ; dépend de `pypdf` (déjà dans les dépendances) |
| [Ofi Invest](https://ofiinvestassetmanagement.flatchr.io/fr/company/ofiinvestassetmanagement/) | Liste publique Flatchr et fiches d’offre directes ; branche d’employeur préservée | Connecteur actif ; les annonces sont filtrées sur leur intitulé et leur description (crédit/obligataire inclus si confirmé) | Les offres PE, immobilier, conformité, middle-office et support ne doivent pas être interprétées comme finance de marché |
| [Tikehau Capital](https://tikehau-capital-career.talentview.io/jobs) | HTML public, puis rendu navigateur Playwright pour la liste et les fiches JavaScript ; contrat, lieu, dates et description extraits quand présents | Connecteur actif ; seules les fonctions admissibles en finance de marché sont conservées | Installation Chromium requise (`playwright install chromium`) |
| [Groupama AM](https://www.groupama-am.com/fra/fr/intermediaire/carriere/groupama-asset-management-carriere) | Offres directement liées depuis la page officielle, puis fiches détaillées Groupama Gan Recrute | Connecteur actif ; la fiche détaille l’entité, le contrat, le lieu et la description | Les postes marketing et support restent filtrés, même si la fiche mentionne la finance de marché |
| [ABC arbitrage](https://www.abc-arbitrage.com/fr/carriere/) | L’employeur renvoie vers Welcome to the Jungle | Source vérifiée, mais pas de collecte intégrée | La page WTTJ consultée ne fournit pas de liste publique exploitable à ce connecteur ; aucun endpoint public n’a été confirmé |

Les quatre connecteurs actifs sont interrogés lors de l’actualisation habituelle, avec le même cache horaire et les filtres de contrat, de métier et de localisation. Les pages ODDO sont des PDF officiels : le lien affiché reste la fiche source. Une date ou un lieu absent de la fiche reste vide. Les statuts complets et les sources mutualisées figurent dans `source_coverage.py`.

Exane AM a aussi été inspecté : sa page officielle ne propose pas de liste de postes, seulement une candidature spontanée. Elle reste classée comme portail sans collecte.

## Oracle Cloud additions and source diagnostics (26 October 2026)

Three public Oracle Candidate Experience boards are now configured:

| Employer | Public board | Connector |
| --- | --- | --- |
| J.P. Morgan | https://jpmc.fa.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1001/jobs | Oracle public requisition and detail APIs |
| Goldman Sachs | https://hdpc.fa.us2.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CampusHiring/jobs | Oracle Campus public requisition and detail APIs |
| Schroders | https://ekbq.fa.em2.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_2/jobs | Oracle public requisition and detail APIs |

The connectors use the same contract, market-role and location filters as other sources. Goldman Sachs early-career labels such as Seasonal/Off-cycle and Summer Analyst are normalized as internships. Company details and dates remain sourced from the actual posting; the employer page's availability does not guarantee a matching role is currently open.

Tikehau's official public Talentview/Kelio board requires JavaScript. The connector now tries the plain public HTML first and then an unauthenticated Playwright browser for the listing and detail pages. Install the browser runtime once after installing project requirements with `playwright install chromium`. No account, cookie consent, CAPTCHA, or access restriction is bypassed. If the browser runtime is missing, the source diagnostic reports that explicitly.

ODDO's official career page embeds the public Altays board. The connector now uses the board's current English route and retries discovery in a public browser when static HTML exposes no PDF links. During the latest public inspection Altays displayed a loading error and no offer links, including in its rendered page. In that condition the connector reports the public board error; this is not interpreted as proof that ODDO has no vacancies. It may remain unavailable until Altays restores the public listing.

## Additional public markets sources (27 October 2026)

| Employer | Platform | Coverage and verification |
| --- | --- | --- |
| CIBC Capital Markets | Workday CXS | Public campus board configured; Global Markets summer internship listing verified at [CIBC](https://cibc.wd3.myworkdayjobs.com/campus/job/London-GBR/Global-Markets-Summer-Intern---10-week-Summer-Programme--June---September-2027_2619190). |
| TD Securities | Workday CXS | Public careers board configured; 2027 Summer Global Markets Internship listing verified at [TD](https://td.wd3.myworkdayjobs.com/TD_Bank_Careers/job/XMLNAME-2027-Summer-Internship---Global-Markets_R_1513487). |
| OCBC Global Markets | Workday CXS | Public external board configured; Global Markets Digital Markets internship listing verified at [OCBC](https://ocbc.wd102.myworkdayjobs.com/External/job/Internship--Global-Markets--Digital-Markets--Jan---Jun-2027-_JR00011358). |
| Qube Research & Technologies | Greenhouse | Public board configured; its official Greenhouse listing includes a 2027 Quantitative Research and Trading internship in Paris and other financial hubs. |
| 21shares | Greenhouse | Public board configured; official listing verified for a Front-Office Data Support internship in London, within Capital Markets & Trading. |

These five additions use the existing public Workday CXS and Greenhouse board connectors. Their listings are visible without paid APIs or account access. The connector itself has not been live-run in this workspace because its Python runtime is unavailable; application-level results still need confirmation on the user's machine. Welcome to the Jungle remains excluded: the site does not expose a public job aggregation endpoint, and its terms restrict automated extraction. JobTeaser remains a public sitemap discovery source only; direct job detail access has previously been blocked. No scraping or authentication restrictions are bypassed.

## Refresh performance and per-source cache

The shared offers snapshot still loads immediately from disk/in-memory cache. Background collection now stores a separate cache by connector, with each completed source merged into the visible snapshot instead of waiting for the slowest connector. Checks record elapsed milliseconds, cache/live/stale state, count and last-check time. An in-process refresh guard prevents duplicate collection runs. Dynamic connectors use an hourly refresh interval; the previously expensive or low-change ODDO/Tikehau/BNP group pages use four hours, static career listings three hours, and the JobTeaser sitemap its existing 24-hour interval. A forced refresh bypasses these per-source intervals.

Detail descriptions returned by Greenhouse, Lever, Ashby and SmartRecruiters are retained with the offer. Workday and Oracle details are reused while URL and public listing metadata remain unchanged. A new/changed listing re-fetches its detail so start dates and role classification can be refreshed without repeating detail reads for every unchanged posting.

## Connector completeness fixes (28 October 2026)

| Source | Issue found | Change |
| --- | --- | --- |
| Société Générale | The collector queried the French-only legacy listing and inspected only its first 40 cards. International offers could also be rejected when their city was outside a hard-coded hub list. | The connector now reads the global English index, follows direct official offer links, and parses title, location, contract, publication date, start date and description. Market-relevant roles are no longer discarded solely for being outside the curated hubs; Paris remains a ranking priority, and the International stage filter accepts non-French locations with country/region data. The source-cache version was bumped after each connector change. |
| Workday banks (including Deutsche Bank, Barclays, Santander CIB, MUFG, CIBC, TD and OCBC) | Matching results beyond the first 50 were discarded even though their list records had already been collected. Search terms did not explicitly include general internships, markets or quantitative roles. | Added those terms, increased the bounded pagination window, and retained all matching listings while enriching only the 50 highest-scoring details. |
| Oracle boards (Lazard, J.P. Morgan, Goldman Sachs and Schroders) | The connector enriched only the first 60 eligible postings and silently dropped all remaining matches. | Increased the bounded requisition window and now retains every matching listing; detailed descriptions are fetched for up to 60 and shorter public descriptions remain available for the rest. |
| BNP Paribas public browser collector and Groupama AM | Both discarded eligible offer links after fixed 12/30 item limits. | Removed the silent truncation and process each eligible public link. |

The Société Générale offers [26000MO2](https://careers.societegenerale.com/en/job-offers/internship-equity-derivatives-quantitative-pricing-26000MO2-en) and [26000MH3](https://careers.societegenerale.com/en/job-offers/graduate-trainee-global-markets-sales-26000MH3-en) are both in the official global English index. The latter is a Global Markets Sales graduate trainee role in Sydney, published 2026-10-25 with a 2026-11-23 start date. The connector's mocked regression tests cover both global-market locations. The live collector still needs a runtime refresh to confirm the jobs appear in the user's local dashboard; no live result is claimed here.
