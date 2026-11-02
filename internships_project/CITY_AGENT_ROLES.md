# City — contrats de rôles (version 2)

Les identifiants SQLite existants sont conservés pour ne pas perdre l'historique.
`job_hunter` désigne désormais Jules Software Engineer ; `finance_tutor` Noé Quant Research ;
`developer` Axel Interview Coach. `innovation_lab` désigne Nova. Ces identifiants ne
donnent aucun accès aux anciens outils. Le Desk Manager est l'unique chat utilisateur.

| Agent | Opérations serveur | Récurrence (Europe/Paris) | Livrable |
|---|---|---|---|
| Jules | `repository_audit`, préparation de branche après validation humaine | Quotidienne | Audit AST, risques à examiner, proposition, révision Git ; branche de test isolée |
| Noé | `quant_report`, `collect_markets` | Rapport hebdomadaire | Courbe de capital, rendement net, Sharpe à taux sans risque nul, volatilité, drawdown, hypothèses et limites |
| Axel | `daily_questions`, `mock_interview`, `evaluate_answer` | 5 questions par jour + entretien hebdomadaire | Questions Sales/S&T/Global Markets, HireVue, grille de couverture indicative et historique des réponses |
| Nova | `innovation_review` | Hebdomadaire | Deux projets publics GitHub non déjà proposés, licence, spécification de prototype isolé, complexité et coûts à mesurer |
| Lina | Recherche de contacts existante + `refresh_internships` | Collecte quotidienne de contacts inchangée | Contacts ; collecte réelle des offres sur demande |
| Hugo | `refresh_internships` via le service Python existant | Sur demande, renouvelable chaque jour ou plusieurs fois par jour | Stages avec date de publication confirmée aujourd’hui, heure de Paris |

Mira, Iris et le Desk Manager conservent leurs autres responsabilités.

## Collectes sans interfaces ouvertes

Depuis le chat du Manager : « Noé, actualise les données Markets », ou « Hugo,
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
City doit fonctionner pour exécuter la demande ; aucune collecte automatique
supplémentaire n'est activée pour Hugo. Lina conserve son ancien accès pour compatibilité.

Lina peut aussi rechercher de nouveaux contacts à tout moment via « Rechercher
maintenant » dans Contacts ou son outil de recherche depuis le Manager. La limite
d'une collecte par jour concerne uniquement l'automatisation : les recherches
manuelles restent disponibles après une collecte réussie ou échouée et lorsque
l'automatisation est suspendue. Une mission Lina déjà active empêche un doublon ;
les limites de dépenses API et la déduplication des contacts restent appliquées.
Test réel du 2 novembre 2026 : appel OpenAI avec recherche Web terminé, huit
contacts validés et aucune fiche rejetée, sur un compte de test isolé.

Le serveur City doit rester démarré. Fermer les interfaces Markets/Internships est possible ;
éteindre l'ordinateur arrête aussi City sauf s'il est hébergé ailleurs. Les planifications
sont rattrapées une fois au prochain contrôle, sans rejouer tous les jours d'absence.
`auto_tasks=false` suspend les nouvelles récurrences spécialistes ; Lina garde son interrupteur existant.

## Périmètre réel et limites

- Jules analyse les modules Python City locaux sans exécuter leur code. Ce dossier de
  travail possède désormais un dépôt Git local initialisé le 2 novembre 2026.
  Les anciens audits sans révision Git doivent être relancés avant validation.
  Aucun dépôt distant n'est configuré ; la synchronisation GitHub reste distincte.
  Dans un clone, la validation humaine crée une branche `marketdesk/jules-*` et un worktree
  `.city-worktrees/`, avec un nouveau test AST vérifié. Aucun fichier existant n'est remplacé,
  aucun commit, push, merge, installation ou déploiement automatique. Le test AST n'est pas
  présenté comme une suite complète de performance. `MARKETDESK_GITHUB_REPO=owner/repo`
  permet de consulter les cinq derniers commits publics ; cette lecture ne synchronise pas le clone.
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
