# Assistant IA · Mail

Le sous-onglet **Mail** importe jusqu'à 20 profils LinkedIn PDF à la fois (8 Mo par PDF), extrait leur texte et enregistre les contacts dans la base privée du compte. Un PDF déjà importé est reconnu par son empreinte ; les profils ayant la même URL LinkedIn sont regroupés. Les liens intégrés au PDF sont prioritaires sur l'URL affichée et éventuellement coupée sur plusieurs lignes. L'employeur et le poste actuels sont tirés de la première expérience datée lorsque celle-ci est lisible. Les noms, postes, entreprises, lieux, expériences et formations sont modifiables. Une initiale de nom ne permet jamais de générer une adresse.

## Formats d'adresse

Les adresses proposées sont **supposées**, même lorsque le format est documenté par un exemple public. Un domaine valide ne prouve pas qu'une boîte existe. Les filiales ne sont couvertes que lorsqu'elles figurent explicitement dans la liste d'alias du format. Les noms composés, apostrophes et prénoms multiples demandent une vérification manuelle. Le registre est modifiable par compte ; une référence ajoutée par l'utilisateur reste non vérifiée dans l'application.

| Établissement | Format probable | Exemple public consulté le 29/10/2026 |
| --- | --- | --- |
| Société Générale / SG CIB | `{prenom}.{nom}@socgen.com` | [Contacts presse officiels](https://www.societegenerale.com/fr/actualites/newsroom/contacts-presse) |
| BNP Paribas / BNP Paribas CIB | `{prenom}.{nom}@bnpparibas.com` | [Recherche économique BNP Paribas](https://economic-research.bnpparibas.com/teams/economic-projections/Jean-Luc-PROUTAT/) |
| Natixis / Natixis CIB | `{prenom}.{nom}@natixis.com` | [Publication de recherche Natixis CIB](https://home.cib.natixis.com/site/dt7uf2li9bnv/api-website-feature/files/download/12321/natixis_research_-_green_bonds_review_q1-22__market_enters_a_more_mature_phase.pdf?file_type=media_files) |
| Crédit Agricole CIB | `{prenom}.{nom}@ca-cib.com` | [Brochure officielle CA-CIB](https://www.ca-cib.com/sites/default/files/2022-01/20220118_Credit_Agricole_CIB_Complaint_Handling_Brochure_EN.pdf) |
| ODDO BHF | `{prenom}.{nom}@oddo-bhf.com` | [Espace presse officiel ODDO BHF](https://www.oddo-bhf.com/press-media-kit/) |
| Amundi | `{prenom}.{nom}@amundi.com` | [Équipe officielle Amundi](https://www.amundi.com/institutional/private-equity) |
| TP ICAP | `{prenom}.{nom}@tpicap.com` | [Communiqué officiel TP ICAP](https://tpicap.com/tpicap/media/press-releases/2026/icap-launches-global-nuclear-fuels-brokerage-desk-support-growing-energy-transition-demand) |
| Carmignac | `{prenom}.{nom}@carmignac.com` | Format non documenté : saisie manuelle |
| Kepler Cheuvreux | `{initiale_prenom}{nom}@keplercheuvreux.com` | Format non documenté : saisie manuelle |

Des boîtes génériques ou des exemples trouvés chez un groupe ne documentent pas le format individuel des autres établissements. Aucun autre format n'est appliqué automatiquement.

## Rédaction et envoi

La génération transmet à OpenAI le profil candidat enregistré et les informations du contact sélectionné uniquement au clic sur **Générer le mail**. L'objet, le corps et la relance sont éditables. L'import n'appelle pas l'IA et n'envoie rien. Le CV est joint uniquement si un PDF a été choisi pour le lot ; aucune lettre n'est jointe automatiquement.

L'envoi exige de sélectionner 1 à 10 contacts complets, de prévisualiser leurs adresses, messages et CV éventuel, puis de cocher la confirmation. Une adresse supposée garde ce statut après validation. La revue est invalidée si le message, le destinataire ou le CV change. L'état est enregistré avant toute tentative ; un résultat incertain n'est jamais retenté automatiquement. Par défaut : plafond de 10 messages par jour et 60 secondes entre envois, configurables par `INTERNSHIPS_MAIL_DAILY_LIMIT` (1–50) et `INTERNSHIPS_MAIL_DELAY_SECONDS` (15–600). Pause, reprise et annulation s'appliquent aux messages qui n'ont pas encore commencé à partir.

Le transport utilise `INTERNSHIPS_MAIL_PROVIDER=smtp` par défaut, avec les variables SMTP des alertes. Pour Railway Hobby, utiliser `INTERNSHIPS_MAIL_PROVIDER=resend`, `RESEND_API_KEY` et `INTERNSHIPS_MAIL_FROM` (une adresse d'un domaine autorisé dans Resend). La clé doit rester dans les variables serveur. Le destinataire peut être chez n'importe quel fournisseur. L'envoi HTTPS Resend ne nécessite pas le SDK Resend.

La relance est préparée à 7 ou 14 jours. Son envoi automatique est **désactivé pour chaque nouveau contact** et nécessite une activation explicite dans sa fiche. Le contrôle tourne seulement tant que l'application est active. Il s'arrête dès que le statut est marqué Réponse, Refus ou Erreur définitive. La boîte de réception et les retours d'erreur différés ne sont pas synchronisés : l'utilisateur doit reporter ces événements dans le suivi avant l'échéance. Aucune ouverture n'est suivie.
