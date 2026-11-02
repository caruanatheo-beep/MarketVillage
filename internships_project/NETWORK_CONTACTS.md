# Lina — collecte quotidienne de contacts

L'onglet **Contacts**, dans la navigation supérieure de MarketDesk City, ouvre une fenêtre dédiée au dossier de Lina (deux colonnes sur ordinateur, une sur mobile, fermeture avec Échap). Cliquer sur Lina ou son bureau Network ouvre également ce dossier. Les vues Sales prioritaires (par défaut), Tous les contacts et Autres métiers conservent l'accès à toutes les fiches existantes. La recherche par nom/métier, les filtres de spécialité et d'entreprise et les détails des sources sont disponibles. Le ciblage est recalculé depuis l'intitulé enregistré et son contexte, sans modifier les informations d'origine ni prétendre que le poste est vérifié. Les fiches sont aussi enregistrées dans le dossier Mail d'Internships pour les étapes de vérification et de rédaction existantes.

## Planification et données

- À la première connexion à City, chaque compte dispose de sa propre planification active. Le worker vérifie les collectes dues toutes les minutes. Une tentative est créée par jour civil **Europe/Paris**, dès que le serveur est disponible ; aucun horaire fixe n'est imposé.
- La planification et le dernier identifiant de mission sont conservés dans SQLite (`city_network_schedule`). Une transaction empêche plusieurs workers de lancer la même collecte quotidienne. Une mission Lina déjà active retarde la nouvelle collecte.
- L'objectif est **10 nouveaux contacts**, principalement des **Sales en finance de marché**, à Paris/Île-de-France. Les recherches ciblent Fixed Income, Rates, Credit, FX, Equities, produits structurés et Sales institutionnels. Après déduplication, un profil connexe au maximum est retenu pour quatre nouveaux Sales, avec deux profils connexes maximum. Si trop peu de Sales sont documentés, le lot est plus petit. Les Sales sans périmètre marché identifiable et les Sales hors cible ne servent pas à compléter le quota. La collecte demande jusqu'à 15 pistes pour absorber les doublons. Si les sources fournissent moins de profils documentés, le bilan donne le nombre réel ; aucun contact n'est inventé pour compléter le quota.
- Déduplication sur l'URL LinkedIn canonique, puis nom + entreprise normalisés, y compris contre les contacts importés. Les fiches existantes et corrections manuelles ne sont jamais écrasées. L'enregistrement est transactionnel.
- Nom, poste, entreprise, localisation, URL publique, extrait de source, date de détection et incertitudes sont conservés. Les postes sont **à confirmer**, toutes les nouvelles fiches sont **À vérifier / Non contacté**, adresse vide et contrat non confirmé. Les initiales restent des initiales.
- Les profils et résultats sont isolés par compte. La suppression administrative d'un compte supprime également sa planification.
- **Suspendre** arrête les prochaines collectes, sans interrompre une requête déjà partie. Une collecte échouée n'est pas automatiquement retentée le même jour. Son erreur reste visible dans Contacts et dans les missions existantes.
- La fenêtre du navigateur peut être fermée ; le processus FastAPI doit continuer à tourner. Ordinateur éteint et serveur non hébergé : aucune collecte.

## Recherche Web et coût

Par défaut, Lina utilise **GPT-5.4 mini**, l'API Responses et l'outil `web_search`, avec la clé `OPENAI_API_KEY` déjà configurée côté serveur. Les autres agents gardent leurs modèles.

Un seul appel modèle par mission, quatre appels d'outil au maximum, 6 500 jetons de sortie au maximum, aucun retry HTTP, un délai de lecture borné et une limite de durée de lecture de 110 secondes. Les domaines et pages consultés sont récupérés dans `web_search_call.action.sources`. Une fiche sans URL effectivement retournée par l'outil, ni indice d'identité ou de localisation pertinent, est écartée. Une source indexée ne prouve pas que le poste est toujours actuel.

Le contexte exclut les contacts déjà présents (jusqu'aux 200 derniers pour limiter les tokens) ; la déduplication finale couvre tout le dossier. Aucun CV, mot de passe, email privé ou clé API n'est envoyé dans ce contexte.

Le verrou de génération et les budgets IA existants sont réutilisés. Avant l'appel, une marge de budget restant estimée à **0,20 $** est requise. C'est une précaution budgétaire, pas un montant facturé ni une garantie de plafond fournisseur. Les jetons et recherches sont ajoutés au registre `llm_usage` sous l'action `lina_contact_discovery` et attribués à la mission Lina.

Tarifs vérifiés le 1 novembre 2026 : GPT-5.4 mini 0,75 $ / million de jetons d'entrée, 0,075 $ en cache, 4,50 $ en sortie ; recherche Web 0,01 $ par recherche, plus les jetons. Deux appels réels de validation ont totalisé environ 0,0963 $ ; le coût futur dépend des recherches et des tokens utilisés.

Documentation officielle :
- https://developers.openai.com/api/docs/models/gpt-5.4-mini
- https://developers.openai.com/api/docs/guides/tools-web-search
- https://developers.openai.com/api/docs/pricing

`MARKETDESK_NETWORK_SEARCH_MODE=public` sélectionne l'alternative sans LLM : HTML public DuckDuckGo, puis flux RSS public Bing. Six requêtes ciblées, deux connexions simultanées, aucune authentification ni contournement. Lors des vérifications locales, DuckDuckGo refusait l'accès et Bing renvoyait des résultats non pertinents : ce mode doit alors signaler un échec, pas inventer des contacts. Le mode IA est celui retenu et testé pour la collecte quotidienne.

## Vérification

Tests dédiés : `pytest -q tests/test_network_discovery.py`. Ils couvrent filtrage, sources, doublons, corrections manuelles, transactions concurrentes, planification persistante, pause, isolation, CSRF et une mission complète avec API simulée. Les tests n'envoient aucun message. Le test réel de recherche n'a pas écrit dans les contacts des comptes existants.

Build frontend : `npm run build` dans `internships_project/city_frontend`. Vérification navigateur isolée : `check_network_preview.py` avec `preview-command.mjs`, après une recherche publique enregistrée dans les artefacts locaux. Résolutions vérifiées : 1920×1080, 1366×768 et 390×844.
