# MarketDesk — Markets, City et Internships

Ce dépôt contient trois applications distinctes. Elles conservent leurs interfaces,
leurs processus et leurs liens entre services ; aucun écran City n’est intégré à Internships.

| Projet | Code et documentation | Lancement depuis la racine | Adresse locale par défaut |
|---|---|---|---|
| **Markets** | [Markets/](Markets/README.md), `Markets/src/` | `python Markets/app.py` | http://127.0.0.1:7860 |
| **City** | [City/](City/README.md), `City/internships_project/` | `python City/app.py` | http://127.0.0.1:7862 |
| **Internships** | [Internships/](Internships/README.md), `Internships/internships_project/` | `python Internships/app.py` | http://127.0.0.1:7861 |

## Liens conservés

- City importe les services Markets via `src.*` et les services Internships via
  `internships_project.*`, sans lancer leurs interfaces.
- Les petits fichiers `src/__init__.py` et `internships_project/__init__.py` à la
  racine assurent la compatibilité des imports. Le code applicatif se trouve dans
  les trois dossiers ci-dessus, sans copies ni liens Windows nécessaires.
- Les anciens lancements `python app.py`, `python app_internships.py` et
  `python -m internships_project.city_app` fonctionnent toujours. Le superviseur
  `scripts/city_start.py` et le worker planifié gardent leurs chemins.
- Les comptes, contacts, missions et caches existants restent dans
  `internships_project/data/` (ou dans les emplacements configurés par
  l’environnement). Ce stockage partagé et privé n’est pas déplacé ni publié.
- `.env`, les dépendances Python et les outils locaux restent communs à la racine.
  Installation complète : `python -m pip install -r requirements.txt`.

## Publications

Le dépôt principal reste [MarketVillage](https://github.com/caruanatheo-beep/MarketVillage).
La CI demeure dans `.github/workflows/` et vérifie les trois applications.

Le site [Internships en ligne](https://caruanatheo-beep.github.io/Internships-Offres/)
reste publié par le dépôt séparé
[Internships-Offres](https://github.com/caruanatheo-beep/Internships-Offres).
Ses fichiers de déploiement sont maintenant dans `Internships/deploy/`.
Le packager et la publication des missions Sacha traduisent les nouveaux chemins
locaux vers les chemins existants du dépôt public. Le service Cloudflare de
recommandations reste dans `Internships/deploy/source-suggestions/` et conserve
son adresse et sa base distante.

Les scripts communs restent dans `scripts/`, les tests dans `tests/`.
Pour reconstruire le cockpit :

```powershell
cd City/internships_project/city_frontend
npm run build
```

Les ressources compilées restent versionnées dans
`City/internships_project/city_assets/`. Pour les tests :

```powershell
python scripts/city_test.py -q -m "not live"
```
