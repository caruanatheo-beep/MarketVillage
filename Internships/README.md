# Internships

Le collecteur, le catalogue de sources et les interfaces Internships sont dans
`Internships/internships_project/`. City peut réutiliser ces services Python.

Depuis la racine du dépôt : `python Internships/app.py`.
L’ancien lancement `python app_internships.py` reste compatible.

- [Sources disponibles](internships_project/SOURCES.md)
- [Déploiement GitHub Pages](deploy/github-pages/README.md)
- [Service des recommandations](deploy/source-suggestions/README.md)
- [Site public](https://caruanatheo-beep.github.io/Internships-Offres/)
- [Dépôt publié](https://github.com/caruanatheo-beep/Internships-Offres)

Les scripts `scripts/package_internships_pages.py` et
`scripts/build_internships_pages.py` conservent le format du dépôt public.
Les missions Sacha publient leurs changements validés dans ce même dépôt.
Les comptes et contacts partagés avec City restent au stockage privé existant
`internships_project/data/` à la racine, sans duplication.

## Collectes et rattrapage

GitHub vérifie le catalogue aux minutes 13, 33 et 53 de chaque heure. La fenêtre
réelle reste de 8 h à Paris à 23 h à New York ; une publication datant de moins
de 55 minutes évite une nouvelle collecte.

Les déclenchements programmés de GitHub ne sont pas garantis. Le secours Windows
`scripts/install_internships_watchdog.ps1` vérifie le catalogue toutes les 15 minutes
quand la session est ouverte. Après une heure sans actualisation, il déclenche le
workflow existant seulement si aucun run n'est déjà actif. Il réutilise la connexion
Git Windows et ne stocke aucune clé dans le projet. Le contrôle est répété côté
GitHub pour écarter une relance devenue inutile.

Diagnostic sans relance : `python scripts/internships_refresh_watchdog.py`.
Rattrapage si nécessaire : ajouter `--recover`. Le dernier état est enregistré dans
`artifacts/internships-refresh-watchdog.json`. Quand le PC est éteint, seul le
déclenchement GitHub reste disponible.
