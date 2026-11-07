# City — contrats de rôles (version 2)

Les identifiants SQLite existants sont conservés pour ne pas perdre l'historique.
`job_hunter` désigne désormais Jules Software Engineer ; `finance_tutor` Noé Quant Research ;
`developer` Axel Interview Coach. `innovation_lab` désigne Nova. Ces identifiants ne
donnent aucun accès aux anciens outils. Le Desk Manager est l'unique chat utilisateur.

La ville occupe la largeur disponible. Une bulle au-dessus d'un agent en mission
affiche son travail en cours et ouvre la mission au clic. La fiche de l'agent
s'ouvre en fenêtre au clic sur son personnage ou son bureau. Missions et
Notifications conservent les décisions et les résultats détaillés.
Les étapes affichées proviennent du dernier événement enregistré, sans progression
inventée. Seules les missions en attente proposent une annulation ; les décisions
restent dans leurs écrans de validation existants. Les diagnostics et l'usage API
sont accessibles dans Réglages. Le chat du Manager et les contacts conservent leurs fenêtres.

| Agent | Opérations serveur | Récurrence (Europe/Paris) | Livrable |
|---|---|---|---|
| Jules | `repository_audit`, `codex_review`, `develop`, préparation de branche historique | Audit quotidien et six missions de développement autonomes par jour pendant un mois | Correction City, commit local et vérifications dans un worktree isolé |
| Camille | `develop` | Six créneaux autonomes par jour pendant un mois, espacés de quatre heures | Correction visuelle concrète dans City ou Internships, build et commit local |
| Sacha | `develop` | Six créneaux par jour pendant un mois, dont le premier dédié à une nouvelle source | Une source carrière vérifiée par jour visée, priorité aux petites banques et sociétés de gestion françaises ; autres créneaux consacrés notamment à la vitesse et à la fiabilité de collecte |
| Maël | `develop` | Six missions autonomes par jour pendant un mois | Correction de régression ou fiabilisation, test et commit local |
| Noé | `quant_report` | Sur demande uniquement | Courbe de capital, rendement net, Sharpe à taux sans risque nul, volatilité, drawdown, hypothèses et limites |
| Axel | `daily_questions`, `mock_interview`, `evaluate_answer` | Sur demande uniquement | Questions Sales/S&T/Global Markets, HireVue, grille de couverture indicative et historique des réponses |
| Nova | `innovation_review` | Deux fois par semaine : lundi et jeudi | Deux projets publics GitHub non déjà proposés par revue, licence, spécification de prototype isolé, complexité et coûts à mesurer |
| Lina | Recherche de contacts existante + `refresh_internships` | Collecte quotidienne de contacts inchangée | Contacts ; collecte réelle des offres sur demande |
| Clara | `discover_service_contacts` | Sur demande uniquement | Contacts publics en services titres et collateral, ajoutés au carnet partagé sans appel API payant ; BP2S = BNP Paribas Securities Services |
| Hugo | `refresh_internships` via le service Python existant | Chaque jour + sur demande | Bilan des nouveaux stages détectés dans la synthèse du Manager ; recherche des publications du jour sur demande |
| Mira | `collect_markets` via le service Python Markets | Chaque jour + sur demande | Brief de marché et sentiment sourcé dans la synthèse quotidienne |

Iris et le Desk Manager conservent leurs autres responsabilités.

Du 4 novembre au 3 décembre 2026 inclus, chaque agent de développement reçoit six
missions quotidiennes. Le choix du changement concret lui appartient. Jusqu'à quatre
missions de développement peuvent s'exécuter ensemble, une par agent et par compte,
dans des worktrees Git distincts, avec Codex connecté à
l'abonnement ChatGPT et `gpt-6.1-sol` en raisonnement moyen. Aucun appel API payant
n'est utilisé pour ce développement. Le réglage « Missions simultanées » de chaque
compte s'applique aussi. City mesure la progression du quota hebdomadaire pendant
les appels des programmeurs, de Jules et de Clara, puis la compare à un budget
commun de 1/7 du quota par jour (14,3 points), remis à zéro à minuit heure de Paris.
Sacha peut consulter en lecture seule les sites carrières publics pour vérifier une
nouvelle source. L'objectif d'une source fonctionnelle par jour dépend des offres
publiquement accessibles : une source inaccessible ou vide est signalée, jamais comptée
comme ajout réussi.
L'usage personnel de Codex entre deux appels City n'entre pas dans ce calcul.
Si Codex ne renvoie pas sa mesure, City autorise au plus six appels partagés par jour.
Quand le budget est atteint, le développement reprend le lendemain.
Une mission déjà lancée peut faire dépasser ce seuil ; il ne s'agit pas d'un plafond
imposé par OpenAI à l'abonnement.

City contrôle le périmètre des fichiers, la syntaxe Python, un test ciblé et le build
frontend lorsque nécessaire. Les intégrations sont successives : si une autre mission
a avancé le dépôt, City rebase la branche et relance les vérifications avant de l'intégrer.
Un conflit laisse la branche disponible pour examen.
Il n'y a ni push GitHub ni déploiement automatique. Une mission qui échoue conserve
son worktree pour examen. Le bilan quotidien du Desk Manager liste les commits
intégrés et les missions non intégrées. Les anciennes propositions Jules qui attendent
une validation suivent leur circuit historique.

Le Desk Manager propose un bouton « Briefing du matin » dans son chat et un outil
de lecture sur demande. Il rassemble les derniers résultats enregistrés de Lina,
Hugo et Mira avec leurs dates, puis les propositions et validations en attente.
Ce briefing déterministe est isolé par compte, conservé dans le chat et ne lance
ni collecte ni appel IA supplémentaire. Il est aussi publié automatiquement une fois
par jour, après les missions prévues ; une mission en erreur y est signalée avec sa date.

Hugo classe les stages actualisés selon les métiers, lieux et mois de début
explicitement renseignés dans le premier profil enregistré. Le classement est
indicatif ; sans profil, l'ordre général est conservé. Une date limite apparaît
uniquement si l'offre porte une date ISO encore valable, avec son lien source.
La synthèse quotidienne reprend ces indications dans le chat du Manager et garde
la liste complète dans le résultat. Le texte du CV n'est pas envoyé au collecteur.

## Relance et notifications

Le Manager accepte les noms Jules, Noé/Noe, Axel et Nova, ainsi que les identifiants
techniques conservés. Son outil expose des choix explicites et choisit l'opération
principale si elle n'est pas fournie. Une opération incompatible produit un message
actionnable ; `prepare_branch` reste exclue du schéma de l'outil et de la relance directe.
Le bouton « Relancer l'audit de Jules » utilise une route authentifiée qui ne peut
exécuter que l'opération principale autorisée, sans appel IA de coordination.

Le centre Notifications affiche une entrée par mission, les décisions en premier,
les résultats récents, les erreurs et un journal d'événements. Les propositions non
résolues restent chargées même au-delà des cent dernières missions. Les marqueurs
de lecture sont persistants et isolés par compte ; ils n'autorisent ni n'annulent rien.
Les actions réutilisent les routes de validation, approbation, annulation et relance
existantes. Les erreurs d'action sont affichées dans le centre. Un ancien audit Jules
sans révision Git explique le blocage de préparation et propose de relancer un audit.
Le résultat d'une branche indique le chemin du fichier local ; il ne s'agit pas d'une
publication automatique sur GitHub.

## Collectes sans interfaces ouvertes

Depuis le chat du Manager : « Mira, actualise les données Markets », ou « Hugo,
cherche les stages publiés aujourd’hui ». Le tool `collect_dashboard_data` ajoute une mission SQLite.
Le worker appelle `src.data` / `internships.refresh_opportunities` directement.
Il ne lance ni navigateur, ni processus Gradio. Les boutons de collecte des panneaux
utilisent les mêmes routes authentifiées. Publication, observation et détection restent distinctes.
La collecte Internships n'envoie aucun e-mail (`notify_email=False`).

Hugo possède un poste dans le village et appelle directement
`refresh_jobs_workflow(published_today=True)` puis `internships.refresh_opportunities`.
Le bouton Stages lui confie désormais cette mission. Son accès au code est un appel
au service Python autorisé : aucun navigateur ni serveur Gradio nécessaire.
Les dates de publication inconnues ou estimées et les VIE sont exclus du bilan des
stages du jour. Les offres déjà en cache publiées aujourd’hui restent incluses ;
« nouvellement détecté » et « publié aujourd’hui » sont deux notions distinctes.
Les erreurs de sources sont signalées : la collecte ne garantit pas l’exhaustivité.
Le worker Windows peut exécuter les missions sans serveur City ouvert. La collecte quotidienne Hugo rapporte
les stages nouvellement détectés pendant son actualisation, sans les confondre avec des
publications du jour. Le chat du Manager reçoit une synthèse commune avec Mira, Hugo,
Lina et Jules, y compris pour zéro résultat ou une erreur ; aucun appel LLM supplémentaire ni envoi externe.
Les 20 premières offres sont listées dans le chat ; le résultat conserve la liste complète.
Lina conserve son ancien accès Internships pour compatibilité.

Nova utilise deux périodes : lundi–mercredi et jeudi–dimanche, heure de Paris, avec
un seul lancement par période. Une ancienne revue
hebdomadaire compte pour la première période lors du changement de configuration.
Les tâches automatiques Axel/Noé encore en attente sont annulées ; les tâches manuelles,
les missions déjà en cours et l'historique sont conservés.

Lina conserve GPT-5.4 mini et sa collecte quotidienne. L'objectif est désormais le coût
d'un lot de dix nouveaux contacts : Sales en priorité, puis traders, structureurs, quants
de marché, analystes Market Risk, brokers et gérants de portefeuille pour compléter.
Aucun quota minimum de Sales ne bloque les métiers proches. Les métiers hors cible,
sources invérifiables et doublons restent exclus.
La recherche IA comporte un plan explicite : équipes et biographies de banques/sociétés
de gestion, puis articles de marchés, interviews, nominations, experts cités et biographies
d'intervenants d'associations professionnelles. Les domaines proposés sont des exemples,
sans restriction à LinkedIn ni liste fermée. Les mots-clés combinent français et anglais,
y compris négociateur de taux, gérant obligataire, ingénieur financier et stratégiste marchés.
Le complément change de types de publications et d'employeurs. Les plafonds de deux
appels d'outils initiaux et d'un seul appel pour le complément restent inchangés.
Une fiche peut être sourcée uniquement par un site bancaire ou un article. Une source
distincte peut prouver la localisation si elle nomme la même personne et le même employeur.
Les dates publiées sont conservées ; une source datée de plus de deux ans est rejetée
comme preuve principale. L'absence de date ne certifie pas l'actualité du poste.
Paris/Île-de-France et plusieurs communes du secteur de La Défense sont acceptés sur
preuve explicite ; un nom de famille contenant « Paris » ne prouve pas la localisation.
La fiche affiche le type et la date de source, le lien principal et la preuve de localisation.
Le collecteur public sans IA conserve son extraction bornée de profils LinkedIn ;
l'élargissement aux articles et biographies est porté par la recherche Web IA.

Le mode LinkedIn assisté est distinct : les liens de recherche sont préparés localement,
et l'utilisateur ouvre LinkedIn et sélectionne lui-même les profils. Le formulaire
authentifié importe uniquement les informations professionnelles saisies et un extrait
qui les appuie, dans son propre dossier. Les comptes, cookies et mots de passe LinkedIn
ne sont ni demandés ni stockés. Aucun scraping de session, clic automatisé, invitation
ou message n'est effectué. L'import ne consomme aucun appel LLM et utilise la
déduplication existante, sans écraser les fiches déjà enregistrées. Sa provenance est
« Sélection LinkedIn » et reste distincte des résultats de recherche Web automatique.
La première requête combine Sales et métiers proches avec deux appels d'outils maximum,
contexte Web faible, extraits courts et plafond de 4 500 tokens. Si dix contacts sont
enregistrés, aucun complément n'est lancé. Sinon, une seule requête supplémentaire vise
uniquement le nombre manquant, avec un seul appel d'outil, une réponse plus courte et
un contrôle du budget restant. Les premiers contacts sont conservés si le complément
échoue ou dépasse le budget ; la limite de dix et la déduplication restent transactionnelles.
Test réel isolé : dix contacts (un Sales, neuf métiers proches) en une requête pour
0,0351202 $ estimé, soit 0,003512 $ par contact. Ce test ne garantit pas un minimum global
de coût ni dix résultats pour chaque recherche : aucune fiche non sourcée n'est inventée.

Lina extrait aussi l'école ou l'université fréquentée si les sources publiques déjà
consultées l'indiquent. Le nom, l'établissement et l'extrait doivent être accompagnés
d'une URL effectivement retournée par la recherche. Aucune recherche supplémentaire
n'est lancée uniquement pour la formation. La fiche Contacts affiche l'établissement,
l'extrait et la source, ou « Non renseignée ». Aucun diplôme n'est déduit ; les anciens
contacts et les corrections manuelles ne sont pas remplacés par la collecte.

Le bouton « Rechercher les écoles » et l'outil `enrich_contact_schools` lancent aussi
un enrichissement ciblé des fiches existantes : cinq contacts sans école par lot,
avec trois appels d'outils Web maximum et le budget IA habituel. Les fiches jamais
recherchées passent en premier. Seules l'école et ses preuves sont ajoutées dans une
transaction ; les changements manuels survenus pendant la recherche sont conservés.
Une source doit identifier la personne et sa formation, et correspondre au profil
enregistré ou citer aussi son employeur pour limiter les homonymes. Un simple événement
dans une école ne suffit pas. Les recherches infructueuses laissent le champ vide.

Lina peut aussi rechercher de nouveaux contacts à tout moment via « Rechercher
maintenant » dans Contacts ou son outil de recherche depuis le Manager. La limite
d'une collecte par jour concerne uniquement l'automatisation : les recherches
manuelles restent disponibles après une collecte réussie ou échouée et lorsque
l'automatisation est suspendue. Une mission Lina déjà active empêche un doublon ;
les limites de dépenses API et la déduplication des contacts restent appliquées.
Test réel du 2 novembre 2026 : appel OpenAI avec recherche Web terminé, huit
contacts validés et aucune fiche rejetée, sur un compte de test isolé.

Le worker Windows est lancé à 08 h et à l'ouverture de session, même si le navigateur
et le serveur City sont fermés. Le PC doit être allumé et la session ouverte. Les planifications
sont rattrapées au prochain contrôle : Mira, Jules, Hugo, Lina et Nova regroupent les périodes
manquées depuis leur dernière mission planifiée en une seule actualisation par agent.
Le résultat et les paramètres indiquent la plage de dates et le nombre de périodes.
Toutes les périodes couvertes sont enregistrées pour éviter les doublons au redémarrage.
Une première utilisation ne déclenche pas de rattrapage antérieur à l'activation.
Les sources sont interrogées maintenant : aucun état historique indisponible n'est inventé,
et Hugo distingue toujours détection et publication. Les limites de dépenses et les
interrupteurs de suspension restent appliqués. Axel et Noé restent sur demande ;
Iris n'a pas de récurrence à rattraper. Les missions déjà en attente restent en file.
`auto_tasks=false` suspend les nouvelles récurrences spécialistes ; Lina garde son interrupteur existant.

## Périmètre réel et limites

- Pour proposer une amélioration via l'abonnement, le Manager délègue `codex_review`.
  Le bouton « Proposer une amélioration avec Codex » lance la même opération.
  Le serveur fournit jusqu'à 60 000 caractères d'extraits de fichiers City suivis par Git
  (7 000 par fichier). Codex travaille en lecture seule, avec outils shell, apps, plugins
  et recherche Web désactivés. Il explique le problème, cite les éléments observés,
  rédige une consigne de développement et les vérifications attendues, et signale les limites
  des extraits. La proposition exige ensuite une validation humaine avant toute réalisation.
  Cette analyse est sur demande ; l'audit quotidien AST reste sans appel Codex.
- Pour une correction ou fonctionnalité, le Manager délègue à Jules avec `code_change`
  et conserve la consigne exacte du message. Le centre de notifications propose aussi
  un formulaire « Confier une correction ou fonctionnalité à Jules ».
  La proposition mentionne la consommation des limites Codex et attend la validation humaine.
  Après validation, City lance le **Codex CLI local connecté avec ChatGPT**, dans un worktree
  `.city-worktrees/<id>/`, avec les outils de lecture, modification et tests de Codex.
  La clé API de City n'est pas transmise au processus ; aucune solution de repli API n'est utilisée.
  Les appels du chat Manager restent indépendants et utilisent l'API existante.
  Codex doit être installé sur la machine qui exécute City et connecté via `codex login`.
  Le binaire est détecté dans PATH ou dans l'extension VS Code Windows ;
  `MARKETDESK_CODEX_BIN` permet une surcharge locale facultative.
  Le processus ignore la configuration utilisateur, désactive apps, plugins et recherche Web,
  utilise le profil workspace avec réseau des commandes désactivé et revue automatique
  des demandes d'approbation des outils Codex, et expire après 15 minutes.
  Aucun `.env`, fichier de données ou secret n'est copié dans le worktree ; les clés du serveur
  sont retirées de son environnement. Les consignes demandent de préserver l'authentification
  et de ne pas consulter de données privées. Le rapport affiche les fichiers, le diff (extrait
  au-delà de 120 000 caractères), les commandes capturées et le bilan de tests rapporté par Codex.
  Un code de sortie indique l'exécution d'une commande, pas la qualité fonctionnelle du changement.
  Un refus d'outils, une absence de modifications ou un rapport incomplet ne valent pas succès.
  Pas de commit, push, merge ni intégration automatique par City. Les modifications sont locales
  et non commitées dans le worktree. La branche part du commit de la proposition validée,
  même si le dépôt principal a évolué depuis ou contient des changements non commités.
  Le résultat indique la révision de base, la révision courante et la nécessité de revoir le
  diff et les tests avant intégration si elles diffèrent. Les changements non commités du
  dépôt principal ne sont pas copiés. Une révision validée introuvable reste bloquante.
  « Réessayer » sur une préparation échouée conserve l'identifiant de mission lié à la
  validation humaine, sans créer une nouvelle approbation ni écraser un worktree existant.
- L'audit quotidien de Jules analyse les modules Python City locaux sans exécuter leur code. Ce dossier de
  travail possède désormais un dépôt Git local initialisé le 2 novembre 2026.
  Les anciens audits sans révision Git doivent être relancés avant validation.
  Le remote `origin` référence MarketVillage ; la synchronisation GitHub reste distincte.
  Dans un clone, la validation humaine crée une branche `marketdesk/jules-*` et un worktree
  `.city-worktrees/`, avec un nouveau test AST vérifié. Aucun fichier existant n'est remplacé,
  aucun commit, push, merge, installation ou déploiement automatique. Le test AST n'est pas
  présenté comme une suite complète de performance. Jules reconnaît automatiquement un
  remote `origin` GitHub HTTPS ou SSH ; `MARKETDESK_GITHUB_REPO=owner/repo` reste une
  surcharge facultative. Il consulte cinq commits publics et indique si le HEAD local
  correspond au dernier commit consulté, s'il diffère ou si la comparaison est indisponible.
  Cette lecture ne lance aucun fetch/pull et ne certifie pas l'absence de modifications
  locales, lesquelles sont signalées séparément. Le rapport dit clairement que le test
  attend encore la validation de l'utilisateur avant sa création en branche isolée.
- Noé utilise les historiques FRED du collecteur Markets, sans interface ni LLM. Les
  stratégies exécutables initiales sont momentum et retour à la moyenne, long/cash sur
  SP500 ou NASDAQCOM. Signaux décalés, coûts à l'entrée/sortie, liquidation finale. Les
  indices prix excluent les dividendes et ne sont pas directement négociables. FX carry,
  ETF factors et arbitrage de paires nécessitent encore des adaptateurs de données et
  modèles validés ; ils sont refusés, jamais remplacés par un faux backtest. Les marchés
  à taux fixe exigent des prix/flux obligataires, pas l'assimilation d'un rendement à un prix.
- Axel utilise une banque locale de questions et une grille de notions. Sa pré-évaluation
  persistante ne certifie pas la justesse d'une réponse et n'invente pas de note LLM.
- Nova interroge la recherche GitHub publique et vérifie la licence ; aucune dépendance
  n'est téléchargée/exécutée. Si deux nouveaux projets documentés ne sont pas accessibles,
  la mission échoue explicitement. L'estimation précise de coût et l'essai du prototype
  restent à mesurer avant intégration. La validation transmet le cahier des charges à
  une revue Jules, sans installer l'innovation.

## Migration et sécurité

La migration annule les tâches actives des anciennes spécialisations, conserve tâches,
résultats, coûts et décisions historiques. Les workflows enregistrés incompatibles sont
archivés (`role_version=1`) et ne peuvent plus être exécutés. Les workflows ne concernant
que Mira/Lina/Iris restent utilisables. Les tâches sont contrôlées à la création **et** au
retrait de file ; les anciens résultats ne deviennent pas la dernière activité du nouveau rôle.

Les validations passent par un POST authentifié, protégé par origine et clé d'en-tête,
isolé par propriétaire et dédupliqué. Le modèle ne dispose d'aucun outil de validation.
Les nouveaux services spécialisés n'appellent aucune API LLM ; les appels Manager et
les services existants conservent leurs limites et journaux de coûts. Aucun service payant ajouté.

Vérifications : `tests/test_city_specialists.py`, tests de capacités/services, build frontend
avec huit postes et 80 trajets aller-retour golf, aperçu navigateur isolé explicitement étiqueté.
Les tests Git travaillent dans un dépôt jetable ; aucun test n'envoie de message externe.

## Revalidation du 2 novembre 2026

- Build TypeScript et bundle réussis après ajout du champ `result` au contrat des tâches
  du village. Huit postes accessibles, 80 trajets golf et tests de projection validés.
- 64 tests réussis dans les cinq suites City : spécialistes, capacités, collaboration,
  persistance et HTTP. Les anciens tests suivent désormais Lina pour les collectes et
  les nouveaux workflows ; concurrence, reprise et isolation restent vérifiées.
- Instance HTTP City redémarrée avec base et compte jetables : connexion, huit agents,
  bundle, chat Manager avec outil, workflow Nova, validation explicite, audit Jules,
  déduplication et refus anonyme vérifiés. Modèle et recherche simulés pour ce parcours ;
  routes, worker, audit local et SQLite réels. Aucun compte utilisateur réel utilisé.
- Appels réels séparés : Nova a retourné deux dépôts publics avec licences MIT et
  Apache-2.0 ; Noé a calculé son backtest sur 1 192 observations FRED SP500.
  Cela confirme l'accès aux sources, pas la pertinence d'une intégration des projets.
- Vérification visuelle finale **non effectuée** : le navigateur intégré signale
  `browser access host is unavailable`. Les boutons ont été vérifiés par leurs routes,
  sans confirmation de leur rendu ou de leur clic dans le navigateur.
- Le dossier reste sans dépôt Git exploitable. L'interpréteur référencé par `.venv`
  est absent ; les tests ont utilisé `.codex-tools/python312/python.exe` avec les
  dépendances déjà présentes dans `.venv/Lib/site-packages`, sans réinstallation.

La validation finale du rendu reste ouverte. Les limites fonctionnelles décrites
ci-dessus (stratégies quant, grille Axel, prototype Jules) restent applicables.
