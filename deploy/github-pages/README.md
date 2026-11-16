# MarketDesk — offres publiques

Site statique consacré aux stages, VIE et programmes graduate en finance de marché.
Les lieux affichés sont normalisés en français, sans confondre Paris et ses
communes voisines ni supprimer les lieux multiples. Le libellé public d'origine
reste dans `location_source` pour la recherche et les identifiants des alertes ;
les lieux contradictoires ne sont pas corrigés par supposition.
Commerzbank est collecté via son catalogue public paginé, Standard Chartered via
son sitemap et ses fiches publiques. Les dates de début et de publication restent
distinctes ; les annonces expirées sont écartées avant publication.
Candriam est collecté directement depuis son RSS public et BNY depuis son portail
Oracle. Les postes de relation clients en gestion d'actifs sont classés Sales
uniquement lorsqu'une mission au sein de l'équipe commerciale est documentée.
Le filtre « Graduate / Junior » inclut les intitulés Junior Analyst / Analyste junior
pertinents en marchés et gestion d'actifs. Les intitulés génériques nécessitent une
description confirmant le desk ; les exigences explicites de trois ans d'expérience
minimum et les métiers Middle Office, KYC et finance corporate restent exclus.
GitHub Pages sert uniquement les fichiers HTML/CSS/JS, logos PNG et offres publiques.
La collecte Python vise une actualisation horaire, de 8 h à Paris jusqu'à
22 h à New York inclus, tous les jours et indépendamment du PC. Trois créneaux
à h 07, h 27 et h 47 permettent de rattraper un déclenchement manqué. La collecte
est ignorée si les données publiées ont moins de 55 minutes ; les lancements
manuels restent disponibles. Une erreur de lecture de la date autorise la reprise.
La plage se ferme à 5 h le lendemain à Paris, ou à 4 h pendant les semaines
de décalage des changements d'heure entre les deux pays.
Un contrôle des deux fuseaux bloque les collectes hors plage. Les caches des
sources expirent après 55 minutes pour permettre une nouvelle vérification à
chaque cycle ; les délais de reprise des sources en erreur restent respectés.
GitHub peut retarder ou omettre des déclenchements : ces créneaux réduisent le
risque sans garantir une cadence horaire stricte.

## Sécurité

- Aucun compte, CV, contact, suivi de candidature, outil IA ou clé IA dans ce dépôt.
- Aucun fichier `.env`, historique Git du projet principal ou base utilisateur transféré.
- Aucune clé IA. Les seuls paramètres privés nécessaires sont les paramètres SMTP
  et les adresses, chiffrés dans l'environnement GitHub `email-alerts`, limité à
  la branche `main`. Ils ne sont fournis qu'à l'étape d'envoi, après publication.
- Le collecteur, le site public et les artefacts de publication ne reçoivent pas
  ces secrets. Les jetons temporaires GitHub sont gérés par la plateforme.
- Actions officielles épinglées par SHA ; aucun workflow de pull request privilégié.
- Le job de collecte n'a pas de droit d'écriture sur le dépôt et ne conserve pas
  les identifiants Git dans sa copie de travail.
- Publication limitée au répertoire `_site` construit depuis une liste explicite.
- Contrôle des motifs de clés et des variables secrètes avant l'export, validation
  des liens HTTPS, affichage des textes via `textContent`, politique CSP restrictive.
- Les descriptions, erreurs brutes et diagnostics internes ne sont pas publiés.
- Les données des offres sont publiques. Aucun faux écran de connexion ne protège
  ce site : les données personnelles restent dans l'application locale.

## Mise en service

Dans Settings → Pages, choisir « GitHub Actions ». Activer HTTPS. Le workflow
« Collect and publish public offers » peut être lancé manuellement depuis Actions.
Il n'utilise que des endpoints publics et un navigateur sur écran virtuel.
L'actualisation manuelle se lance uniquement depuis GitHub Actions, en étant
connecté avec un compte disposant des droits d'écriture sur le dépôt, puis en
confirmant « Run workflow ». Le site public ne contient aucun bouton de lancement,
jeton GitHub, lien d'administration ou suivi des exécutions. Les collectes
automatiques restent actives aux horaires configurés.
Une collecte manuelle contourne les caches des sources ; les collectes planifiées
conservent leurs délais de cache pour éviter de surcharger les sites carrières.
Certaines sources peuvent refuser les IP des centres de données : l'état affiché
signale les indisponibilités et le cache conserve les offres précédentes.
Une collecte sans aucune offre bloque la publication et conserve l'ancien site.

## Alertes email

Après chaque publication réussie (planifiée ou manuelle), une étape séparée compare
les offres à l'historique des alertes. Elle envoie un seul récapitulatif s'il y a
de nouvelles offres employeurs et aucun mail sinon. Les liens issus uniquement
du sitemap JobTeaser, dont l'ouverture n'est pas confirmée, ne déclenchent pas
d'alerte. Le même poste retrouvé chez une autre source n'est pas renvoyé.

L'historique durable est conservé sur la branche `notification-state`. Il contient
uniquement des empreintes SHA-256 d'offres publiques et une date, jamais d'adresse,
de mot de passe ou de profil. Cette branche ne déclenche pas de collecte. En cas
de réinitialisation de cet historique, la première exécution établit une référence
silencieuse pour éviter l'envoi massif d'anciennes offres.

L'envoi utilise SMTP avec TLS vérifié. Une erreur de mail reste visible dans le
job `notify`, mais ne retire pas le site publié. Les offres ne sont enregistrées
comme notifiées qu'après acceptation du message par le serveur SMTP ; un refus
d'envoi peut donc être retenté à la mise à jour suivante. Une interruption entre
l'acceptation SMTP et l'enregistrement peut exceptionnellement causer un doublon.

Le lancement manuel peut cocher « Envoyer un mail de test » pour vérifier la
configuration sans marquer d'offre comme notifiée.

L'envoi reste désactivé tant que la variable GitHub `EMAIL_ALERTS_ENABLED` n'est
pas définie à `true`. Ne l'activer qu'après avoir configuré les sept secrets SMTP
dans l'environnement `email-alerts`, limité à `main`, et initialisé la branche
`notification-state`. Les valeurs doivent être chiffrées avec la clé publique
GitHub avant leur transfert. Ne jamais les placer dans le code ou les artefacts.

GitHub peut désactiver les horaires après 60 jours sans activité sur un dépôt
public. Vérifier périodiquement l'onglet Actions et réactiver le workflow au besoin.
Les caches GitHub peuvent être évincés ; `public_seed.json` constitue une base
initiale publique, pas une garantie de fraîcheur. La date affichée fait foi.

## Catalogue des sources et suggestions

L’onglet Sources est construit à partir du registre des collecteurs actifs.
Les portails d’une même entreprise sont regroupés ; le catalogue n’annonce
pas de disponibilité en temps réel et ne publie aucun diagnostic privé.

Le formulaire est activé par la variable publique `SOURCE_REQUEST_ENDPOINT`,
limitée à `https://marketdesk-source-suggestions.source-suggestions.workers.dev/suggestions`.
Le récepteur Cloudflare stocke les suggestions dans D1,
hors du dépôt Git, avec des limites atomiques de 3 dépôts par IP et par jour,
50 dépôts par jour au total et un dédoublonnage. Seule une empreinte HMAC de
l’IP est conservée, avec une clé privée et une rotation journalière. Les liens
reçus ne sont jamais ouverts par le récepteur. Les propositions apparaissent
publiquement dans Sources : entreprise, lien et commentaire uniquement.
Les empreintes réseau restent privées. Le formulaire l’annonce
avant l’envoi et refuse les adresses email dans le texte.
`POST /archive`, protégé par le même secret, retire les propositions intégrées.
Les archives de plus de 30 jours sont purgées lors du prochain archivage authentifié.

Les suggestions ne déclenchent aucun email. Elles sont consultables dans Sources
après enregistrement par le récepteur public. Les alertes des nouvelles offres
continuent séparément avec le SMTP GitHub existant.

Le récepteur est déployé séparément avec `deploy/source-suggestions/wrangler.jsonc`.
Le formulaire reste désactivé si `SOURCE_REQUEST_ENDPOINT` est vide ; cette variable
publique ne doit être renseignée qu'après validation d'une écriture réelle.
Aucun Google Form n'est utilisé. Le site GitHub Pages est statique : le fichier
des offres est écrit par GitHub Actions, et la saisie des visiteurs nécessite
un récepteur distant pour devenir visible aux autres visiteurs.

## Développement

`python scripts/build_internships_pages.py --collect --output _site`

Sur GitHub Actions, la collecte tourne sous `xvfb-run` : Chromium dispose d'un
écran virtuel pour les pages BNP rendues en JavaScript. Aucune fenêtre ne
s'ouvre sur l'ordinateur de l'utilisateur, aucun compte BNP n'est utilisé.
Le lecteur PDF `pypdf` est installé pour les fiches ODDO et Comgest. Les erreurs
des sources publiques sont diagnostiquées dans les logs de collecte, sans
paramètres SMTP ni clés IA. Une liste lisible sans poste correspondant aux
critères est distinguée d'un échec de chargement.

Le répertoire de sortie doit être vide. Pour une prévisualisation hors ligne,
préparer un cache d'offres publiques puis omettre `--collect`.
Les critères géographiques et les dates de début sont calculés par le collecteur
existant. La pertinence suit son classement ; recherche et filtres s'appliquent
instantanément dans le navigateur. Aucun appel réseau n'est requis pour filtrer.

La barre de tri sous les filtres propose Pertinence et Publication récente.
Les deux choix sont exclusifs et accessibles au clavier. Les fichiers CSS et JS
portent une version calculée sur leur contenu pour éviter les mélanges de versions
dans le cache du navigateur.

La pertinence combine le score poste/localisation normalisé sur 50 points, la
fenêtre avril–septembre 2027 sur 35 points et la proximité d'avril 2027 sur 15
points (2,5 points de moins par mois d'écart). La publication la plus récente
départage uniquement les scores égaux. Un score source inhabituellement élevé
est plafonné pour qu'il ne puisse pas écraser les deux critères de disponibilité.
