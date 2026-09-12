# Guide utilisateur complet — MedData Bridge

Dernière mise à jour : 12 septembre 2026.

MedData Bridge est un environnement local de qualification et d'exploitation
des échanges IHE PAM France, HL7 MFN, HPRIM XML et FHIR R4 / FR Core. Il permet
également de gérer la structure hospitalière, les patients, les dossiers, les
venues et les mouvements associés.

Ce guide est destiné aux intégrateurs, référents identité et structure,
équipes de recette et exploitants. Les spécifications des partenaires restent
prioritaires.

## Sommaire

1. Démarrage et accès
2. Contextes et données métier
3. Validation et IHE PAM France
4. Endpoints, HPRIM, MFN et FHIR
5. Journaux, outbox, scénarios et roundtrips
6. Diagnostic et glossaire

## Démarrage et accès

Depuis la racine du dépôt :

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python init_db.py
uvicorn app.app:app --reload --port 8000
```

En installation ou mise à niveau, appliquer également les migrations et le
catalogue de scénarios livré :

```bash
alembic upgrade head
```

Ouvrir ensuite <http://localhost:8000>.

| Adresse | Usage |
|---|---|
| `/` | Accueil et accès aux modules |
| `/guide` | Guide rapide dans l'IHM |
| `/documentation` | Index de la documentation rendue par l'application |
| `/api/docs` | Contrat OpenAPI des API HTTP |
| `/health/live` | Vérification de disponibilité |

Pour une recette, utiliser une BDD et des répertoires d'artefacts dédiés. Ne
pas mélanger un corpus de qualification avec les données de démonstration.

## Contextes et données métier

Les contextes limitent les données visibles et les émissions au bon périmètre.
Les badges de l'en-tête indiquent le contexte actif.

```text
GHT → Entité juridique (EJ) → Entité géographique (EG)
                                ↓
                        Patient → dossier → venue → mouvement
```

### Sélectionner le contexte

1. Ouvrir **Administration → GHT et établissements** (`/admin/ght`).
2. Sélectionner le GHT, puis l'EJ ou l'EG si nécessaire.
3. Vérifier les badges avant une importation, génération ou émission.
4. Depuis une fiche, activer le patient ou le dossier avec l'action de contexte.

`/context/clear` efface le contexte voulu. Un changement de GHT ou d'EJ retire
automatiquement les contextes incompatibles afin d'éviter un travail dans le
mauvais établissement.

### Structure hospitalière

La hiérarchie utilisée par l'application est :

```text
GHT → EJ → EG → Pôle → Service → UF → UH → Chambre → Lit
```

Utiliser `/structure` pour la vue d'ensemble et les écrans spécialisés :
`/structure/eg`, `/structure/poles`, `/structure/services`, `/structure/ufs`,
`/structure/uh`, `/structure/chambres` et `/structure/lits`.

`/structure/interactive` permet de relire l'arborescence, modifier certains
libellés ou identifiants, déplacer des entités et réaliser des actions
groupées. Vérifier tout déplacement avant confirmation : il modifie les liens
réutilisés par les exports MFN et FHIR.

### Patients, dossiers, venues et mouvements

1. Créer ou rechercher le patient dans `/patients`.
2. Contrôler ses identifiants, en particulier l'IPP et son espace d'identifiants.
3. Créer le dossier dans `/dossiers`, avec l'EJ, le type et les dates.
4. Créer la venue dans `/venues`, avec l'UF et la localisation si elles sont
   connues.
5. Créer les mouvements dans `/mouvements`.

Avant toute émission, vérifier que le patient, le dossier, la venue, l'UF et
la localisation appartiennent au même périmètre. La vue
`/workflow/venue/{id}/view` aide à relire les transitions autorisées.

## Validation et IHE PAM France

L'écran `/validation` accepte un message HL7 v2 ou un XML HPRIM collé dans le
formulaire et détecte automatiquement son format.

### Valider un message HL7

1. Coller le message complet, avec `MSH` en premier segment.
2. Choisir le sens `inbound` ou `outbound`.
3. Lancer la validation du profil IHE PAM France.
4. Lire les diagnostics par couche : HL7 de base, structure, types de données
   et règles IHE PAM.

| Niveau | Signification |
|---|---|
| Erreur | Écart bloquant ; l'émission applicative est empêchée |
| Avertissement | Écart toléré, à qualifier avec le partenaire |
| Information | Indication ou normalisation sans blocage |

`MSH-18=8859/1` est accepté comme valeur préconisée par le profil français.
L'absence de `ZBE-8` est un avertissement, non un rejet systématique. Les
valeurs connues comme erronées de `ZBE-9` sont diagnostiquées pour traiter les
corpus CPage avec une politique adaptée.

### Injecter et contrôler un message PAM

1. Sélectionner le GHT et l'EJ de destination.
2. Ouvrir `/messages/send`.
3. Choisir `MLLP`, l'endpoint attendu ou aucun endpoint pour une simulation
   locale, puis coller le message HL7.
4. Soumettre et lire l'ACK retourné.
5. Vérifier le journal dans `/messages`, puis le patient, dossier, venue ou
   mouvement créé.

| ACK | Interprétation |
|---|---|
| `AA` | Message accepté par l'application |
| `AE` | Erreur applicative à diagnostiquer |
| `AR` | Message rejeté |

Un ACK positif ne suffit pas : il faut toujours vérifier le résultat métier.
Les endpoints PAM peuvent appliquer une politique `warn` ou `reject`.
Commencer une recette partenaire en `warn`, analyser les écarts puis activer le
rejet après accord bilatéral. `/conformity` présente la vue par EJ et les
diagnostics associés.

Le guide fonctionnel est [IHE_PAM.md](IHE_PAM.md). Le corpus de référence est
dans `data/pam/` et son roundtrip est décrit dans
[ROUNDTRIP_CPAGE_PAM_20260911.md](reports/ROUNDTRIP_CPAGE_PAM_20260911.md).

```bash
python3 scripts/true_roundtrip_cpage.py run
```

## Endpoints et échanges

Configurer les systèmes dans `/endpoints`, après avoir sélectionné le GHT ou
l'EJ concernée.

### Créer un endpoint

1. Cliquer sur **Nouveau système**.
2. Donner un nom explicite, par exemple `CPage recette MLLP`.
3. Choisir le transport : `MLLP` pour HL7 v2, `FHIR` pour les Bundles HTTP,
   `FILE` pour un échange par répertoire, ou `SFTP`/`FTP` pour un dépôt de
   fichiers lorsqu'il est configuré.
4. Renseigner l'hôte/port MLLP ou l'URL de base FHIR.
5. Définir le rôle `sender`, `receiver` ou `both` et le contexte GHT/EJ.
6. Tester avec un corpus non nominatif avant activation.

Un endpoint désactivé reste conservé mais n'est pas utilisé pour l'émission.
`/endpoints/admin` affiche tous les endpoints, sans filtre de contexte.

### Importer et qualifier HPRIM XML

1. Ouvrir `/hprim/import`.
2. Charger ou coller le XML d'actes.
3. Vérifier la validation XML/XSD et l'acquittement.
4. Consulter l'historique persistant dans `/hprim/messages`.

Le périmètre qualifié couvre CCAM, NGAP, UCD et LPP. Pour saisir un acte,
utiliser `/dossier/{dossier_id}/saisie` et contrôler le dossier, le code, la
date d'exécution, la quantité, l'exécutant et le montant avant validation.

Le roundtrip HPRIM automatisé expose :

| Besoin | Endpoint |
|---|---|
| Générer un XML | `POST /roundtrip-hprim/generate` |
| Télécharger le résultat | `GET /roundtrip-hprim/download/{filename}` |
| Réintégrer un XML | `POST /roundtrip-hprim/reintegrate` |

Le payload de génération indique `CCAM`, `NGAP`, `UCD` ou `LPP` et un code
d'acte. Si un montant est fourni, `montant_total` doit être égal à
`prix_unitaire × quantite`. Le contrat complet est visible dans `/api/docs`.

Les API d'émission CCAM et NGAP HPRIM génèrent, valident puis placent le XML
dans l'outbox durable. Transmettre `endpoint_id` pour sélectionner la
destination ; à défaut, l'application recherche un endpoint émetteur ayant
pour `target_system_key` l'identifiant du destinataire. La réponse indique
`delivery_status=queued` et `outbox_id` lorsqu'une livraison est prête, ou
`delivery_status=validated` lorsqu'aucun endpoint n'est configuré : un XML
validé n'est jamais présenté comme déjà envoyé.

### Importer un MFN^M05

L'import MFN utilise le GHT actif :

```bash
curl -X POST http://localhost:8000/structure/import/hl7 \
  -H 'Content-Type: text/plain' \
  --data-binary @structure.mfn
```

Le message contient un `MSH` et annonce normalement `MFN^M05`. Après import,
contrôler dans `/structure` les liens EJ → EG et les parents des services, UF,
UH, chambres et lits.

### Échanger une structure FHIR R4 / FR Core

L'API IHM historique `/fhir/Location` n'est pas le contrat partenaire FR Core.
Utiliser :

| Besoin | Endpoint |
|---|---|
| Exporter la structure d'une EJ | `GET /api/fhir/export/structure/{ej_id}` |
| Importer un Bundle | `POST /api/fhir/import/bundle` |
| Obtenir le contrat complet | `/api/docs` |

Exemple d'import :

```bash
curl -X POST http://localhost:8000/api/fhir/import/bundle \
  -H 'Content-Type: application/json' \
  --data '{"ej_id": 1, "bundle": {"resourceType": "Bundle", "type": "transaction", "entry": []}}'
```

L'import traite les `Organization` avant les `Location`, résout les références
`partOf` et est idempotent au rejeu. Voir le périmètre vérifié dans
[VERIFICATION_FHIR_FRANCE_FR_CORE_2_2_0_20260912.md](reports/VERIFICATION_FHIR_FRANCE_FR_CORE_2_2_0_20260912.md).

## Journaux, outbox, scénarios et roundtrips

### Journaux et rejeu

| Écran | Utilité |
|---|---|
| `/messages` | Historique général, filtres par statut, sens, type et période |
| `/messages/rejections` | Rejets et erreurs à traiter |
| `/messages/by-dossier` | Messages liés à un dossier |
| `/messages/{message_id}` | Payload, ACK, endpoint et validation |
| `/hprim/messages` | Historique HPRIM persistant |

Avant un rejeu, corriger la cause et vérifier que l'événement est encore
pertinent pour l'état métier. Les mouvements PAM dépendent de la chronologie.

### Reprendre une émission sortante

L'outbox persistante couvre les émissions MLLP, FHIR et les dépôts de fichiers
FILE, SFTP ou FTP (notamment HPRIM) :

| Action | Endpoint |
|---|---|
| Lister les lignes | `GET /outbox?status=retry` |
| Récupérer les journaux sortants en échec | `POST /outbox/recover` |
| Traiter les tentatives échues | `POST /outbox/process?limit=100` |
| Rejouer une ligne corrigée | `POST /outbox/{id}/retry` |

Les statuts sont `pending`, `retry`, `sent` et `failed`. Un ACK MLLP `AE` ou
`AR`, ou une réponse FHIR non 2xx, est traité comme un échec. Consulter
[OUTBOX.md](OUTBOX.md) pour le détail d'exploitation.

Le planificateur de l'application reprend automatiquement les lignes `pending`
et `retry` dont l'échéance est atteinte. Les actions HTTP restent disponibles
pour une reprise immédiate ou un diagnostic manuel.

### Scénarios et roundtrips

Les scénarios sont gérés dans `/scenarios`, avec les exécutions dans
`/scenarios/runs` et les outils de qualification dans `/interface-testing`.

Un scénario est un modèle réutilisable. Chaque clic sur **Envoyer** ou
**Prévisualiser le jeu** crée un jeu distinct : IPP, NDA, venue, identité
démonstrative et messages techniques sont générés une seule fois pour ce jeu,
puis figés. Un lancement suivant produit donc de nouveaux identifiants et ne
doit pas écraser le patient/dossier du lancement précédent chez le partenaire.

1. Préparer GHT, EJ, namespaces, structure et endpoint cible.
2. Créer ou importer le scénario dans `/scenarios`.
3. Dans le scénario, sélectionner un ou plusieurs destinataires. Grouper les
   endpoints d'un même partenaire avec la même clé de système cible dans la
   configuration des endpoints ; cela rend explicite leur appartenance au même
   système, par exemple MLLP PAM + dépôt HPRIM + FHIR.
4. Paramétrer le profil clinique du partenaire dans
   `/scenario-target-profiles`. Pour chaque rôle (hospitalisation, externe,
   urgences, mutation, hôpital de jour/séance ou laboratoire), choisir l'UF,
   la chambre/le lit éventuels et le médecin responsable. Le profil est lié à
   la clé de système cible, pas au transport : un endpoint PAM, HPRIM et FHIR
   du même logiciel utilisent donc les mêmes valeurs.
5. Ajouter les étapes dans leur ordre métier. Les boutons ↑/↓ réordonnent une
   étape, et **Modifier** permet de corriger son type, son format ou son
   payload. Les formats pris en charge sont HL7 v2 (MLLP ou FILE), FHIR/JSON
   (FHIR) et HPRIM XML (HPRIM ou FILE).
6. Utiliser **Prévisualiser le jeu** avant l'envoi : la page de résultat montre
   les identifiants générés, la matrice étape × endpoint, et le payload compilé
   réellement destiné au partenaire. Aucune émission n'a lieu dans ce mode.
7. Envoyer le jeu et contrôler chaque livraison/ACK. Une livraison en erreur
   peut être **Réessayée** : le payload et les identifiants restent exactement
   les mêmes. **Rejouer comme nouveau jeu** crée au contraire de nouveaux
   identifiants.
8. Comparer les données avant/après et conserver le rapport anonymisé.

Les données cliniques sont résolues dans cet ordre : ligne du profil de la
destination, médecin responsable de l'UF choisie, ancienne configuration EJ,
puis une paire UF–médecin responsable active de la structure liée à la
destination. Cette dernière règle permet d'exécuter un scénario lorsque le
profil n'est pas encore complété. Le détail du jeu indique la provenance de la
projection pour chaque livraison et affiche le payload immuable réellement
envoyé. Dans IHE PAM, la projection renseigne notamment `PV1-3` et les rôles
médecins usuels ; elle est également appliquée aux professionnels HPRIM et à
`Encounter.location` / `Encounter.participant` en FHIR.

### Catalogue et qualification par logiciel cible

`/scenarios/qualification` est le point d'entrée quotidien du catalogue PAM et
HPRIM. Il permet de filtrer par système cible, thème ou texte, d'afficher le
statut courant (`never_run`, `success`, `partial`, `error`) et la date depuis
laquelle ce statut est observé. Un scénario peut être activé ou désactivé pour
chaque logiciel cible sans être supprimé du catalogue.

Le bouton **Importer le catalogue historique** charge de manière idempotente
les corpus PAM et HPRIM fournis par le projet. Les doublons de payload sont
regroupés, mais leurs clés et chemins historiques restent conservés dans le
scénario pour l'audit. Les anciens formats `hprim`/`hprimxml`, le préfixe
`MSH|` avant un XML et les variables CPage courantes sont normalisés pendant
l'import et à l'émission.

Pour un payload HPRIM, les dates métier déjà présentes dans le XML ne sont pas
modifiées. Une date d'acte doit être un `xs:date`, donc `YYYY-MM-DD` (par
exemple `2026-09-12`) ; une date HL7 compacte telle que `20260912`, une date
vide ou un jeton non résolu est rejeté. Les marqueurs historiques `$DATE$` et
`$HEURE$` sont rendus automatiquement en `YYYY-MM-DD` et `HH:MM:SS` dans une
étape XML HPRIM. Les formes HL7 compactes restent employées seulement dans une
étape HL7.

Dans le détail d'un scénario, renseigner le champ **À quoi sert ce scénario ?**
et choisir son thème. Cette information est destinée aux équipes de recette :
elle n'est pas injectée dans le message. Les contrôles préalables visibles sur
la même page signalent un XML invalide, un scénario désactivé ou une variable
historique inconnue.

Un scénario de contrôle négatif peut déclarer son résultat attendu dans
`expected_outcome_json`, par exemple
`{"mode":"negative","ack_codes":["AE","AR"],"step_order":2}`. Il est alors
qualifié comme réussi lorsqu'il est rejeté à l'étape et avec l'ACK attendus ;
un ACK négatif n'est donc plus confondu avec une panne de recette. Conserver
ces scénarios désactivés hors campagne positive tant que leur objectif métier
et leur endpoint de validation n'ont pas été explicitement qualifiés.

`/scenarios/campaigns` permet de mémoriser une liste ordonnée de scénarios
pour un endpoint cible. Les exécutions et leurs preuves restent accessibles
depuis l'espace de qualification `/ui/interface-testing`.

### Livraison durable, versions et assertions

Avant une recette de référence, publier une version depuis le détail du
scénario. Chaque jeu garde cette version et son empreinte ; modifier ensuite le
scénario n'altère jamais les payloads ni les preuves déjà obtenues.

Les livraisons réelles sont placées dans l'outbox persistante. En cas de panne,
le worker périodique reprend automatiquement les lignes `pending` et `retry` ;
`/outbox/process` permet aussi de le déclencher immédiatement. Le bouton
**Réessayer** conserve le même payload et les mêmes identifiants ; **Rejouer
comme nouveau jeu** produit un autre IPP/NDA/venue.

Depuis le détail d'un jeu partiel ou en erreur, **Reprendre les échecs** ne
réémet que les livraisons qui n'ont pas abouti ; les messages déjà acceptés ne
sont pas renvoyés. Télécharger le diagnostic JSON conserve une preuve portable
de la version, des payloads source et compilés, des réponses et des tentatives.

Les critères déclaratifs peuvent vérifier le statut, un ACK, le contenu d'un
payload et des données locales. Les assertions BDD autorisées sont
`database_count` et `database_field_equals`, sur Patient, Dossier, Venue,
Mouvement et les actes HPRIM. Exemple :

```json
[{"type":"database_count","model":"Patient","where":{"identifier":"{{patient.ipp}}"},"equals":1}]
```

Les tokens suivants peuvent être placés dans les payloads FHIR, JSON ou HPRIM
XML : `{{patient.ipp}}`, `{{dossier.nda}}`, `{{venue.id}}`, `{{play.key}}`,
`{{movement.id}}`, `{{message.control_id}}`, `{{patient.family}}` et
`{{patient.given}}`. Ils sont remplacés durant la préparation du jeu. Le
praticien commun au jeu est également disponible avec
`{{practitioner.rpps}}`, `{{practitioner.adeli}}`, `{{practitioner.family}}`,
`{{practitioner.given}}`, `{{practitioner.name}}` et `{{practitioner.xcn}}`
(aliases français `{{medecin.*}}`). Pour HL7, les champs PAM usuels (`PID`,
`PV1`, `MSH-10`, `ZBE-1`) sont également projetés automatiquement.

Le praticien est résolu une seule fois au début du jeu et conservé dans son
contexte et son diagnostic. L'application prend le premier praticien actif du
référentiel local ; sans référentiel, elle emploie un praticien de recette avec
un RPPS/ADELI syntaxiquement valides. Il est donc identique dans toutes les
étapes d'un même jeu, y compris lors d'une reprise technique.

Les valeurs de praticien codées en dur dans les templates sont également
remplacées à l'exécution : `PV1-7`, `PV1-8`, `PV1-17` et `ROL-4` en HL7, les
identifiants et l'identité des professionnels HPRIM, ainsi que les ressources
FHIR `Practitioner`. Cela permet de rejouer les scénarios historiques sans
réutiliser leurs médecins de démonstration.

Dans une étape HPRIM XML, préférer `{{hprim.date}}`,
`{{hprim.date_time}}`, `{{hprim.time}}` et
`{{hprim.patient_birth_date}}` pour respecter respectivement `xs:date`,
`xs:dateTime`, `xs:time` et `xs:date`. Les aliases génériques
`{{date}}`, `{{time}}` et `{{patient.birth_date}}` sont aussi convertis dans
ce contexte XML ; dans une étape HL7, ils gardent au contraire le format HL7
v2 compact.

Un roundtrip valable utilise deux environnements et deux BDD :

```text
GHT-1 / BDD-1 → message généré → endpoint → GHT-2 / BDD-2
                                  ↓
                            ACK et journaux
```

La réussite exige les ACK attendus et l'égalité des données métier ou de leurs
empreintes. Un `AA` seul n'est pas une preuve de roundtrip.

Le roundtrip automatisé de référence pour les scénarios mixtes utilise deux
GHT et deux BDD SQLite isolées, puis compare patient, dossier, venue et acte
HPRIM. Il est décrit dans
[ROUNDTRIP_SCENARIO_DEUX_GHT_20260912.md](reports/ROUNDTRIP_SCENARIO_DEUX_GHT_20260912.md).

Pour qualifier tout le catalogue historique, lancer
`scripts/roundtrip_scenario_catalog_two_ght.py`. La campagne consolide les
doublons, exécute chaque scénario PAM/HPRIM actif et produit un résultat par
étape dans `artifacts/`. Son dernier bilan est conservé dans
[ROUNDTRIP_CATALOGUE_SCENARIOS_DEUX_GHT_20260912.md](reports/ROUNDTRIP_CATALOGUE_SCENARIOS_DEUX_GHT_20260912.md).

## Diagnostic et glossaire

### Ordre de diagnostic

1. Vérifier le contexte GHT/EJ actif.
2. Ouvrir le journal et relever le type, l'ACK et le diagnostic.
3. Valider le payload dans `/validation`.
4. Vérifier structure, identifiants et transition métier.
5. Vérifier l'endpoint ; pour une émission sortante, contrôler l'outbox.
6. Corriger, rejouer une fois, puis contrôler journal et BDD.

| Symptôme | Vérification prioritaire |
|---|---|
| Endpoint absent | Contexte actif, puis `/endpoints/admin` |
| ACK `AE` ou `AR` | Diagnostic, payload et transition métier |
| Import MFN incomplet | GHT actif et liens parent-enfant |
| Import FHIR partiel | Bundle, profils, identifiants et `partOf` |
| Acte HPRIM non rapproché | Patient, NDA/dossier et type d'acte |
| Émission non reprise | Outbox, endpoint activé et disponibilité |

### Routes principales

| Domaine | Routes |
|---|---|
| Contextes | `/admin/ght`, `/context/select`, `/context/clear` |
| Structure | `/structure`, `/structure/interactive`, `/structure/search` |
| Patients et séjours | `/patients`, `/dossiers`, `/venues`, `/mouvements` |
| Validation et conformité | `/validation`, `/conformity`, `/ihe` |
| Messages | `/messages`, `/messages/send`, `/messages/rejections` |
| Endpoints et outbox | `/endpoints`, `/endpoints/admin`, `/outbox` |
| HPRIM | `/hprim/import`, `/hprim/messages`, `/roundtrip-hprim` |
| Scénarios | `/scenarios`, `/scenarios/runs`, `/interface-testing` |
| FHIR | `/api/fhir/export/structure/{ej_id}`, `/api/fhir/import/bundle` |

### Glossaire

| Terme | Définition |
|---|---|
| ACK | Acquittement HL7 indiquant l'acceptation ou le rejet |
| EJ / EG | Entité juridique / entité géographique |
| FHIR | Standard d'échange de données de santé, ici en R4 |
| GHT | Groupement hospitalier de territoire, contexte principal |
| HPRIM | Format XML français utilisé ici pour les actes |
| IHE PAM | Profil identité et mouvements : ITI-30 et ITI-31 |
| IPP / NDA | Identifiant patient / numéro de dossier administratif |
| MFN^M05 | Message HL7 v2 de structure |
| MLLP | Encapsulation réseau des messages HL7 v2 |
| Outbox | File persistante de reprise des émissions sortantes |
| UF / UH | Unité fonctionnelle / unité d'hébergement |

## Documents complémentaires

- [Index de la documentation](README.md) ;
- [Guide IHE PAM France](IHE_PAM.md) ;
- [État des tests](TESTS_STATUS.md) ;
- [Audit IHE PAM France / CPage](reports/AUDIT_CONFORMITE_IHE_PAM_FRANCE_20260911.md) ;
- [Roundtrip CPage](reports/ROUNDTRIP_CPAGE_PAM_20260911.md) ;
- [Vérification FHIR France / FR Core](reports/VERIFICATION_FHIR_FRANCE_FR_CORE_2_2_0_20260912.md).
