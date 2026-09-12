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
   ou `FILE` pour un échange par répertoire lorsqu'il est configuré.
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

L'outbox persistante couvre les émissions MLLP et FHIR :

| Action | Endpoint |
|---|---|
| Lister les lignes | `GET /outbox?status=retry` |
| Récupérer les journaux sortants en échec | `POST /outbox/recover` |
| Traiter les tentatives échues | `POST /outbox/process?limit=100` |
| Rejouer une ligne corrigée | `POST /outbox/{id}/retry` |

Les statuts sont `pending`, `retry`, `sent` et `failed`. Un ACK MLLP `AE` ou
`AR`, ou une réponse FHIR non 2xx, est traité comme un échec. Consulter
[OUTBOX.md](OUTBOX.md) pour le détail d'exploitation.

### Scénarios et roundtrips

Les scénarios sont gérés dans `/scenarios`, avec les exécutions dans
`/scenarios/runs` et les outils de qualification dans `/interface-testing`.

1. Préparer GHT, EJ, namespaces, structure et endpoint cible.
2. Créer ou importer le scénario dans `/scenarios`.
3. Lancer l'exécution et contrôler chaque ACK dans `/messages`.
4. Comparer les données avant/après et conserver le rapport anonymisé.

Un roundtrip valable utilise deux environnements et deux BDD :

```text
GHT-1 / BDD-1 → message généré → endpoint → GHT-2 / BDD-2
                                  ↓
                            ACK et journaux
```

La réussite exige les ACK attendus et l'égalité des données métier ou de leurs
empreintes. Un `AA` seul n'est pas une preuve de roundtrip.

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
