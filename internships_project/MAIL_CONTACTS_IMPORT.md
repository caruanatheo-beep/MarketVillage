# Répertoire initial de contacts Mail

La source unique intégrée au dépôt est `data/contacts_50_paris.csv`. Le JSON
fourni dans la même archive est une copie des mêmes données et n'est pas importé.

À la première ouverture de **Assistant IA > Mail** par un compte, les 50 lignes
sont persistées dans son enregistrement privé `mail_contacts` de la base SQLite
existante. Les nouveaux comptes reçoivent le même répertoire lors de leur
première ouverture de Mail. L'import ne contacte aucune source externe et ne
lance ni IA, ni proposition d'adresse, ni brouillon, ni envoi.

Les identifiants `PARIS-MKT-xxx` sont conservés dans `external_id`, séparément de
la clé interne. Les URL d'annuaires et publications sont conservées comme sources
et ne sont pas prises pour des URL LinkedIn individuelles. À l'import, les
contacts ont tous le statut **À vérifier**, la prospection **Non contacté**, le
contrat **Non confirmé**, une adresse et une date de vérification vides. La date
`research_date` est la date de recherche du répertoire, pas une vérification du
poste actuel ou du type de contrat.

La réimportation rapproche les identifiants externes, les URL LinkedIn
individuelles canoniques, puis le nom et l'établissement normalisés. Elle
n'écrase pas une fiche existante ; les différences par rapport à l'instantané
source sont remontées dans le bilan de l'import. Les trois contacts Citi restent
séparés malgré leur URL de publication commune.

Les fiches exposent l'identifiant, les sources, le type de source, le desk, le
lieu tel que fourni, la date de recherche, la date de vérification réelle, le
statut du poste et du contrat, ainsi que les notes d'origine. Le tableau est
filtrable par établissement, desk, localisation, type de source, vérification et
prospection. L'export CSV utilise le séparateur `;` et l'encodage UTF-8 avec BOM
pour Excel.
