# MarketDesk City — architecture

Les règles de travail du dépôt sont dans @AGENTS.md (trois applications séparées, tests via `scripts/city_test.py`, données privées hors commits). Ce fichier décrit l'architecture de **City** et le cadre de la refonte visuelle.

## Lancer et vérifier

- Serveur : `.venv\Scripts\python.exe -m internships_project.city_app` → http://127.0.0.1:7862/city/ (connexion requise). Le Python de `.codex-tools/python312` n'a pas les dépendances du serveur.
- Tests : `.venv\Scripts\python.exe scripts/city_test.py tests/test_city_*.py -q`.
- Frontend : `cd City/internships_project/city_frontend && npm run build` (`tsc --noEmit` puis esbuild). Node n'est pas dans le PATH ; il est sous `.codex-tools/node24/`.
- Le bundle compilé `city_assets/city.js` est versionné : tout changement dans `city_frontend/src` doit être recompilé et committé avec lui.

## Stack

| Couche | Technologie | Emplacement (`City/internships_project/`) |
|---|---|---|
| Serveur | FastAPI + uvicorn, session par cookie signé | `city_app.py` |
| Frontière HTTP | Routes `/city/api/*`, JSON + un flux SSE (chat) | `city_routes.py` |
| Données | SQLite `internships_project/data/accounts.sqlite3` (racine du dépôt), tables `city_*` | `marketdesk_city.py` (`CityStore`) |
| Logique | File de missions, planification, workflows, agents | `marketdesk_city.py` (`CityWorker`), `city_agents.py`, `city_services.py`, `city_specialists.py`, `city_coding.py`, `city_chat.py` |
| Rendu de la scène | Canvas 2D, moteur Pixel Agents (MIT) vendorisé | `city_frontend/src/PixelFloorGame.tsx`, `Tower*.ts`, `nightLighting.ts`, `GolfPractice.ts`, `city_frontend/vendor/pixel-agents/` |
| UI | React 18 + TypeScript, une seule feuille CSS | `city_frontend/src/main.tsx` + composants, `city_assets/city.css` |
| Assets | PNG servis par `/city/pixel-assets/*` | `city_assets/pixel-agents/assets/` |

Pas de routeur, pas de store global, pas de framework CSS. `pixelfloor.html` et `campus.svg` sont des restes d'anciennes versions (Phaser), encore servis mais plus utilisés par l'interface.

## Flux des données vers l'écran

1. `CityWorker` exécute les missions et écrit dans `city_tasks` / `city_events`.
2. `GET /city/api/state` renvoie `CityStore.snapshot(username)` : `agents` (statut, xp, niveau, santé, dernière mission), `tasks` (100 dernières + toutes les actives), `events` (80 derniers), `workflows`, `api_usage`, `workspace`, compteurs du jour.
3. `main.tsx` interroge cet endpoint **toutes les 4 s** (pas de WebSocket) et garde le résultat dans un `useState`.
4. `PixelFloorGame` reçoit `agents`, `tasks`, `events` en props. Un `useEffect` traduit les statuts en animations : `running` → agent actif au poste, `waiting_approval` → bulle de permission, nouvel événement `running` avec dépendance → l'agent source marche jusqu'au poste de l'agent cible. Le golf est une animation d'ambiance purement cliente.
5. Clic dans le canvas → `onPick(agentId)` ou `onTaskPick(taskId)` → `main.tsx` change `windowMode`.

Autres lectures périodiques : `/city/api/notifications` (4 s), `/city/api/chat/desk_manager` (10 s), `/city/api/internship-highlight` (60 s), `/city/api/coding-history` (15 s, panneau Développement ouvert), `/city/api/network` (panneau Contacts).

## Structure des pages

Il n'y a qu'une page. `App` (dans `main.tsx`, ~940 lignes) porte tout l'état et un `windowMode` qui choisit le panneau affiché par-dessus la ville :

| `windowMode` | Section | Composant |
|---|---|---|
| `none` | Ville | `PixelFloorGame` |
| `code` | Développement | `codePanel()` dans `main.tsx` |
| `contacts` | Contacts | `NetworkContacts.tsx` (+ `OutreachTracker`, `LinkedInAssisted`, `ContactCollectionReport`) |
| `missions` | Missions | `managerPanel()` dans `main.tsx` (onglets Suivi / Lancer et organiser / Projets) |
| `agents` | Équipe | JSX en ligne dans `main.tsx` |
| `agent` | Fiche d'un agent | `Cockpit.tsx` |
| `internships` | Stages | JSX en ligne dans `main.tsx` |
| `activity` | Notifications | `NotificationCenter.tsx` |
| `settings` | Réglages | dialogue en ligne dans `main.tsx` |
| `chat` | Desk Manager | `ManagerChatWindow.tsx` + `managerChat` dans `main.tsx` |

La fenêtre « Résultat de mission » (`resultTaskId`) se superpose à n'importe quel mode.

## Rendu actuel de la ville

- Un seul `<canvas>` 2D. Le moteur Pixel Agents dessine une carte de tuiles 16 px **vue de dessus** (49 × ~38 tuiles), mobilier et personnages triés en profondeur.
- Passes : sol et façade mis en cache → mobilier et personnages → lumières (`soft-light` + `screen`) → luminaires → golf → projection → étiquettes de zones et bulles de mission.
- `TowerPerspective.ts` redessine la scène bande par bande en rétrécissant le haut (facteur 0,72 → 1) pour simuler une tour en perspective.
- Échelle : `fitScale × zoom`, nombre réel quelconque ; `devicePixelRatio` plafonné à 1,5.
- Assets : moteur et mobilier de base Pixel Agents (MIT, Pablo De Lucca) ; 6 planches de personnages MetroCity (CC0, JIK-A-4) ; mobilier, tour et golf MarketDesk générés par script (`city_assets/marketdesk_pack/*.mjs`). Crédits : `city_assets/pixel-agents/ASSET_CREDITS.txt`.

## Agents (identifiants stables — ne pas renommer)

`desk_manager` Desk Manager · `market_analyst` Mira · `finance_tutor` Noé · `job_hunter` Jules · `city_ui_engineer` Camille · `internships_engineer` Sacha · `quality_engineer` Maël · `networker` Lina · `securities_scout` Clara · `prime_services_scout` Élodie · `outreach_agent` Iris · `developer` Axel · `innovation_lab` Nova · `internship_scout` Hugo.

Statuts : `idle`, `queued`, `running`, `waiting_approval`, `completed`, `failed`, `cancelled`. « À examiner » = `waiting_approval` ou proposition en attente (`isPendingProposal` dans `notifications.ts`).

## Refonte visuelle (branche `redesign`)

Objectif : remplacer le rendu (immeuble en coupe) et l'UI (HUD de jeu) sans toucher aux données ni à la logique. La nouvelle interface vit à côté de l'ancienne, sur **`/city/next/`**, jusqu'à couvrir tout l'inventaire ci-dessous ; l'ancienne (`/city/`) n'est ni modifiée ni supprimée d'ici là.

- **Intouchable** : tout le Python métier, le schéma SQLite, les routes `/city/api/*` et leurs formats, l'authentification. Seul ajout serveur : les deux routes statiques `/city/next/…` dans `city_routes.py`.
- **Quatre couches** dans `city_frontend/src/` :

| Couche | Dossier | Règle |
|---|---|---|
| Accès aux données | `client/` (`types.ts`, `api.ts`, `useCity.ts`) | Seul endroit qui appelle `/city/api/*`. Aucun JSX, aucun dessin. |
| Rendu | `scene/` | Reçoit `agents` et `tasks`, renvoie des clics et l'état de la caméra. N'appelle jamais l'API. |
| UI | `next/` | HUD et panneaux React. Passe par `client/` pour toute action. |
| Ancienne interface | `main.tsx`, `PixelFloorGame.tsx`, composants à la racine de `src/`, `vendor/` | Gelée ; garde ses propres copies des types et de `api()`. |

- Compilation : `node build-next.mjs` → `city_assets/next/app.js` (versionné, comme `city.js`). Feuille de style écrite à la main : `city_assets/next/app.css`.
- Aperçu sans connexion ni base : `node preview-next.mjs` (port 7879, données inventées), puis `python shots_next.py <dossier>` pour les captures 1920×1080.

### Palette (8 couleurs, extraites de `references/lofi-wallpaper.png`)

| Nom | Hex | Rôle |
|---|---|---|
| `ink` | `#100a0e` | Contours, ombres, fond des panneaux |
| `night` | `#14224d` | Ciel haut, pénombre |
| `indigo` | `#202f64` | Ciel, écrans, Global Markets |
| `plum` | `#3b2a2f` | Murs dans l'ombre, boutons |
| `rust` | `#824c2b` | Bois, cuir, terre cuite, erreurs |
| `amber` | `#e7a856` | Lampes, accents, « à examiner » |
| `glow` | `#f9e4b9` | Lumière chaude, texte, papier |
| `sage` | `#4f6444` | Plantes, « au travail » |

Elles sont déclarées deux fois, à garder identiques : `P` dans `scene/pixels.ts` et les variables CSS de `app.css`. Toute autre couleur est un mélange de deux d'entre elles (`mix()` côté scène, `color-mix()` côté CSS). Polices : Jersey 15 (pixel, OFL, dans `city_assets/next/fonts/`) pour les titres et les chiffres, sans-serif système pour le texte long.

### Scène

- Tout est dessiné par code à la résolution native (immeuble de 640 px de large, étages de 96 px), puis agrandi par un **facteur entier** (`floor(largeur écran / 640)`, soit ×3 en 1920). Jamais de coordonnée ni d'échelle fractionnaire.
- `building.ts` : étages (`LEVELS`), sièges (`SEATS`), décor cuit une fois dans un canvas dont les fenêtres restent transparentes. `backdrop.ts` : ciel, trois couches de parallaxe, tour Eiffel. `people.ts` : personnages et bulles. `sim.ts` : humeurs dérivées de l'état serveur, déplacements, ascenseur, escalier, pauses. `Scene.tsx` : caméra, nuit (calque `multiply` par étage), lumières (halos additifs), sélection.
- Étages, de haut en bas : toit-terrasse · Head of Desk (Desk Manager) · Global Markets (Mira) · Quant & Innovation (Noé, Nova) · Atelier Code (Jules, Camille, Sacha, Maël) · Interviews & Stages (Axel, Hugo) · Réseau & Outreach (Lina, Clara, Élodie, Iris) · Hall & Café.

### Avancement

Prototype vertical fait : toit, Head of Desk, Global Markets, ascenseur et escalier, HUD complet, journal des missions, fiche d'agent, dialogue avec le Desk Manager. Les cinq autres niveaux sont des plateaux nus (`built: false`) et six sections de la barre renvoient encore vers l'ancienne interface.

### Inventaire à préserver

- **Ville** : agents à leur poste, état en direct, visite d'un agent à un autre lors d'une délégation, bulle de mission cliquable, bulle de validation, sélection d'un agent ou d'un poste, zoom, plein écran, recherche d'agent ou de mission, bouton de collecte des stages.
- **Desk Manager** : chat en flux (SSE) avec reçus d'outils, interruption, effacement, 5 demandes rapides + briefing du matin, suivi des missions actives, liens `[[mission:id]]`, validations en ligne.
- **Missions** : filtres (actives, en attente, terminées, erreurs, toutes), détail, journal, dépendances, tentatives liées, valider / réessayer / annuler ; lancement d'un projet (5 modèles, objectif, thème, priorité) ; constructeur de workflows (7 étapes max, dépendances, enregistrer, modifier, relancer) ; mémoire partagée (recherche, ajout) ; suivi des projets avec résultats réunis.
- **Développement** : journal des changements appliqués par jour, filtres période et agent, compteurs, nouvelle mission pour Jules / Camille / Sacha / Maël, file en cours, analyses seules, échecs, relance, détail (fichiers, diff, commandes, vérifications, état de publication).
- **Contacts** : répertoire Lina / Clara / Élodie avec filtres et tris, fiche d'un contact avec sources, lancement des recherches, planning réseau, complément des écoles, import assisté LinkedIn (profil seul ou page copiée), suivi des messages et relances, passage à Iris.
- **Équipe** : agents groupés (Coordination, Développement, Recherche de contacts, Agents métier), fiche agent (mission en cours, décisions, derniers résultats, journal, lancer une mission, xp et niveau).
- **Stages** : offres récentes sur 7 jours, provenance et fraîcheur du catalogue, alertes de sources, actualisation.
- **Notifications** : fil avec filtres, recherche, filtre par agent, lu / non lu, valider, refuser, autoriser, annuler, réessayer.
- **Résultat de mission** : brief de marché (séries, sentiment), courbe de capital, offres, contacts, question / correction, brouillon et relance, diff de code, validation de proposition.
- **Réglages** : modèle par agent, plafonds quotidien et mensuel, missions simultanées, lancement automatique, usage IA, diagnostics des services, état Codex et clé API.
- **Divers** : déconnexion, message d'erreur global, lancement local de Markets / Internships (`/city/api/local-apps/*`).
