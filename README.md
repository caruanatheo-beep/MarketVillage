# MarketVillage — MarketDesk City

**Un village d’agents pour organiser la recherche en finance de marché, le networking et la recherche de stages.**

MarketDesk City est le produit principal de ce dépôt : une interface pixel-art avec neuf postes de travail, un **Desk Manager** qui centralise les échanges et huit agents spécialisés. Les missions, résultats, propositions et conversations sont conservés par compte dans SQLite.

Le Manager transforme tes demandes en missions, suit leur avancement et te présente les résultats. Cliquer sur son personnage ouvre le chat dans une fenêtre ; Lina dispose de sa propre fenêtre de contacts.

Le **centre de notifications** regroupe décisions à prendre, résultats récents, missions
en cours et erreurs. Ses filtres, indicateurs de lecture par compte et journal détaillé
permettent d’ouvrir les résultats et d’autoriser, refuser ou réessayer les missions
concernées. Marquer comme lu ne valide jamais une proposition.

Pour Jules, demande « Lance une nouvelle revue du code avec Jules » au Manager ou
utilise **Notifications → Relancer l’audit de Jules**. Le Manager accepte les noms des
spécialistes et leurs identifiants techniques ; la préparation de branche exige toujours
le bouton de validation d’une proposition. Les fichiers préparés sont indiqués dans le résultat.

## Ce que tu peux faire

- Confier une demande au Desk Manager et suivre son exécution dans Mission Control.
- Actualiser les données de marché et les offres de stages depuis les services Python existants.
- Constituer un réseau de contacts Sales et métiers proches, avec des sources publiques et une déduplication.
- Enrichir certaines fiches avec l’école ou l’université fréquentée, lorsqu’une source l’atteste.
- Demander une analyse quantitative, préparer un entretien ou produire un brouillon de communication.
- Examiner les audits de Jules et les propositions de Nova avant toute préparation de branche isolée.

## Les agents

| Agent | Responsabilité | Missions automatiques |
|---|---|---|
| **Desk Manager** | Interlocuteur principal, coordination, suivi et validations | Coordination des missions |
| **Mira** | Analyse des marchés et lecture des indicateurs | Sur demande |
| **Jules** | Audit du code City et propositions sur branche isolée | Chaque jour |
| **Lina** | Contacts Sales, puis métiers proches en finance de marché à Paris | Chaque jour |
| **Iris** | Préparation de brouillons à partir des contacts et du profil | Sur demande |
| **Axel** | Questions techniques, entretiens blancs et retours sur les réponses | Sur demande |
| **Noé** | Recherche quantitative et backtests | Sur demande |
| **Nova** | Veille open source et propositions d’innovation | Lundi et jeudi |
| **Hugo** | Actualisation Internships et suivi des nouveaux stages détectés | Chaque jour, avec un bilan dans le chat du Manager |

Les opérations exactes, restrictions et limites sont décrites dans les [contrats de rôles](internships_project/CITY_AGENT_ROLES.md).

### Récurrences et rattrapages

City vérifie les échéances environ toutes les minutes, selon le fuseau **Europe/Paris**, sans heure de lancement fixe. Le serveur doit rester en cours d’exécution.

Au redémarrage, les périodes manquées sont regroupées en **une actualisation par agent automatique**, avec les dates concernées et sans relancer plusieurs fois la même période. Cette actualisation consulte les sources disponibles maintenant ; elle ne reconstitue pas un historique absent.

Les tâches automatiques peuvent être suspendues dans les réglages ; Lina conserve son interrupteur dans Contacts. Les missions sur demande restent disponibles. Les limites de dépenses et la protection contre les missions simultanées sont conservées.

### Networking et stages

**Lina** vise dix nouveaux contacts sourcés : Sales en priorité, puis traders, structureurs, quants de marché, analystes Market Risk, brokers et gérants de portefeuille. Si le premier lot est incomplet, un seul complément ciblé est possible, sous réserve du budget. Le résultat peut rester inférieur à dix si les sources sont insuffisantes.

La recherche Web combine sites de banques et sociétés de gestion, équipes, biographies,
articles de marchés, interviews et intervenants d’associations professionnelles, avec des
mots-clés français et anglais. LinkedIn est facultatif. Les fiches conservent les liens,
les dates disponibles et, si nécessaire, une source distincte prouvant la localisation.

Le bouton **Rechercher les écoles** enrichit jusqu’à cinq fiches existantes par lot. L’établissement, l’extrait et le lien source sont affichés ; une école ou un diplôme ne sont jamais déduits pour remplir une case vide.

Dans **Contacts → LinkedIn · mode assisté**, choisis une requête Sales, trading ou
recherche/gestion, puis ouvre-la sur LinkedIn. Tu te connectes et navigues toi-même.
Le formulaire permet ensuite d’ajouter un profil sélectionné avec son lien et un
extrait confirmant nom, poste, entreprise, localisation et éventuellement école.
L’import est local, sans appel IA ni accès à la session LinkedIn ; il conserve les
fiches existantes et écarte les doublons. City ne pilote pas la navigation LinkedIn.

**Hugo** appelle directement le collecteur Python Internships, sans ouvrir son site. Son bilan quotidien distingue les stages nouvellement détectés des offres dont la publication est confirmée aujourd’hui. Les erreurs de sources sont signalées.

## Démarrer City

Prérequis : **Python 3.12**, Git et les dépendances du projet. Node.js et npm ne sont nécessaires que pour reconstruire le frontend.

```powershell
git clone https://github.com/caruanatheo-beep/MarketVillage.git
cd MarketVillage
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m internships_project.city_app
```

Ouvrir **http://127.0.0.1:7862** et se connecter à son compte.

La configuration reste côté serveur, dans l’environnement ou un fichier `.env` local :

| Variable | Usage |
|---|---|
| `OPENAI_API_KEY` | Chat du Manager, recherche Web de Lina et services IA concernés |
| `INTERNSHIPS_USERS_JSON` | Comptes configurés pour la connexion |
| `INTERNSHIPS_USER_DB` | Emplacement de la base SQLite partagée par les services |
| `MARKETDESK_CITY_HOST` / `MARKETDESK_CITY_PORT` | Adresse d’écoute et port ; valeurs locales par défaut : `127.0.0.1` et `7862` |
| `MARKETDESK_CITY_SESSION_KEY` | Clé de session stable d’au moins 32 caractères pour un hébergement public ; générée en mémoire si absente en usage strictement local |
| `MARKETDESK_GITHUB_REPO` | Surcharge facultative `owner/repo` ; Jules détecte aussi GitHub depuis `origin`, consulte les commits publics et compare les révisions sans synchroniser les fichiers |

Les budgets IA sont réglables par compte dans City. La disponibilité des données dépend aussi des fournisseurs utilisés par les services partagés.

## Architecture et services partagés

| Partie | Emplacement |
|---|---|
| Serveur FastAPI, connexion et lancement | `internships_project/city_app.py` |
| Routes City | `internships_project/city_routes.py` |
| Missions, persistance et planification | `internships_project/marketdesk_city.py` |
| Agents et outils du Manager | `internships_project/city_agents.py` |
| Services métier et spécialistes | `internships_project/city_services.py`, `city_specialists.py` |
| Networking et enrichissement des écoles | `internships_project/network_discovery.py` |
| Interface React / TypeScript et village | `internships_project/city_frontend/` |
| Frontend compilé et ressources graphiques | `internships_project/city_assets/` |

Les trois applications gardent leurs propres interfaces et processus :

| Application | Lancement | Rôle dans ce dépôt |
|---|---|---|
| **MarketDesk City** | `python -m internships_project.city_app` | Village et coordination des agents |
| **Markets** | `python app.py` | Tableau de bord et services de données de marché |
| **Internships** | `python app_internships.py` | Tableau de bord et services de collecte des offres |

City peut réutiliser leurs services Python sans lancer leurs interfaces Gradio. La documentation historique du projet Markets est conservée dans [MARKETS_LEGACY.md](MARKETS_LEGACY.md) ; les rôles City qui y figurent sont anciens.

## Développement et vérifications

Le frontend compilé est inclus. Pour le reconstruire :

```powershell
cd internships_project/city_frontend
npm ci
npm run build
```

Le build vérifie TypeScript, les collisions du mobilier, l’accès aux neuf postes et les trajets vers le golf.

Depuis la racine, pour les tests City ciblés :

```powershell
python -m pytest -q tests/test_marketdesk_city.py tests/test_city_specialists.py tests/test_network_discovery.py tests/test_city_internship_scout.py
```

La suite complète se lance avec `python -m pytest -q -m "not live"`. Le dernier contrôle complet avant publication a donné **350 réussites et 10 échecs**, détaillés dans [MARKETDESK_CITY.md](MARKETDESK_CITY.md). La suite complète n’est donc pas présentée comme entièrement validée.

## Données et limites

Les clés, contacts, CV, conversations, bases SQLite, exports et fichiers locaux d’exécution sont exclus du dépôt. Les données utilisateur restent isolées par compte. Les licences des composants et ressources tiers sont conservées avec leurs fichiers.

Les audits, backtests et retours d’entretien ont un périmètre limité, documenté dans les contrats de rôles. Les propositions nécessitent une validation explicite ; City ne fusionne pas de code, ne déploie pas et n’envoie pas de messages ou de candidatures automatiquement.

## Documentation

- [Installation et fonctionnement de City](MARKETDESK_CITY.md)
- [Rôles, planifications, rattrapages et limites](internships_project/CITY_AGENT_ROLES.md)
- [Sources de données Internships](internships_project/SOURCES.md)
- [Service Mail partagé](internships_project/MAIL.md)
- [Documentation historique Markets / Internships](MARKETS_LEGACY.md)

Développé par **Théo Caruana**. Licence [MIT](LICENSE).
