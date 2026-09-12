# Plan de finalisation des scénarios multi-protocoles

Date : 12 septembre 2026

Périmètre : création, enregistrement, génération et émission de scénarios
cohérents contenant des messages IHE PAM, HPRIM XML, FHIR et, si nécessaire,
HL7 MFN, vers un ou plusieurs endpoints.

## Réalisation du 12 septembre 2026

Le socle fonctionnel ci-dessous a été implémenté après ce plan :

- tables persistantes `ScenarioPlay`, `ScenarioPlayTarget`,
  `ScenarioPlayStep` et `ScenarioDelivery`, avec migration Alembic ;
- clé logique `target_system_key` sur les endpoints ;
- préparation atomique d'un jeu : identité, IPP, NDA, venue et praticien sont
  résolus une seule fois, puis les payloads compilés sont figés avant émission ;
- routage par format de chaque étape : HL7 → MLLP/FILE, FHIR/JSON → FHIR,
  HPRIM XML → HPRIM/FILE ;
- compatibilité FHIR avec les configurations FHIR dédiées de l'endpoint ;
- projection automatique des références patient/venue dans PAM, FHIR et HPRIM
  XML canonique, en complément des tokens explicites ;
- projection du praticien commun, y compris lorsqu'un médecin est codé en dur
  dans les positions HL7, les professionnels HPRIM ou une ressource FHIR ;
- profils cliniques par `target_system_key`, avec UF, chambre/lit et médecin
  par rôle métier (hospitalisation, externe, urgences, mutation, hôpital de
  jour/séance et laboratoire) ;
- repli déterministe sur le médecin responsable de l'UF, la configuration EJ
  historique puis une paire UF–médecin active de la structure de destination ;
- compilation et conservation du payload par livraison : deux destinations
  peuvent désormais recevoir les mêmes identifiants de jeu, mais leurs propres
  UF et professionnels, sans compromettre le retry ;
- sélection multi-endpoints, prévisualisation sans envoi, détail de la matrice
  de livraisons, retry technique identique et action « nouveau jeu » ;
- édition et réordonnancement des étapes dans l'IHM ;
- capture des messages HPRIM liés au patient en complément des mouvements PAM ;
- tests unitaires de cohérence intra-jeu et de non-réutilisation entre deux
  jeux.

Le lot de finalisation a depuis complété cette trajectoire : version immuable,
politique d'arrêt, lien `ScenarioDelivery` → outbox, retry déterministe,
assertions déclaratives/BDD, campagnes fondées sur les jeux et diagnostic
portable sont implémentés. Le test automatisé couvre un jeu mixte PAM + HPRIM
vers deux cibles FILE isolées. La recette E2E avec deux logiciels réels et deux
BDD partenaires reste une activité de qualification locale : elle dépend de
leurs endpoints, de leurs schémas et de leurs règles métier, pas d'un manque du
moteur de scénarios.

## Objectif produit

Un scénario est un modèle réutilisable d'échange portant généralement sur un
patient ou un dossier. Il contient une suite ordonnée d'étapes, potentiellement
multi-protocoles, par exemple :

```text
ADT^A28     création du patient             → endpoint PAM / MLLP
ADT^A01     admission du dossier             → endpoint PAM / MLLP
HPRIM CCAM  création d'un acte               → endpoint HPRIM / FILE ou HTTP
ADT^A02     transfert                        → endpoint PAM / MLLP
ADT^A03     sortie                           → endpoint PAM / MLLP
```

Chaque lancement constitue un **jeu de scénario** distinct. Tous les messages
d'un même jeu doivent partager les identifiants métier nécessaires à leur
rapprochement. Un lancement ultérieur doit recevoir de nouveaux identifiants
afin que le système cible crée un autre patient/dossier au lieu d'écraser le
jeu précédent.

## Invariants fonctionnels

1. Un scénario enregistré est un modèle ; son payload source n'est jamais
   modifié pendant une exécution.
2. Un jeu génère une seule identité cohérente : patient, dossier, venue,
   mouvements, actes et identifiants techniques.
3. Toutes les étapes d'un jeu réutilisent cette identité, quel que soit leur
   protocole.
4. Tous les endpoints appartenant au même système cible reçoivent des valeurs
   cohérentes dans leurs namespaces.
5. Deux jeux distincts ne partagent aucun identifiant destiné à être unique.
6. Une reprise technique réutilise le payload exact du jeu en échec ; l'action
   « rejouer comme nouveau jeu » génère au contraire de nouveaux identifiants.
7. Une exécution n'est déclarée réussie que lorsque toutes les livraisons
   obligatoires et toutes les assertions attendues ont réussi.

## État actuel constaté

### Fonctionnalités déjà présentes

- création manuelle d'un `InteropScenario` et ajout/suppression d'étapes ;
- import/export JSON ;
- formats d'étape `hl7`, `fhir`, `json` et `xml` dans le modèle et l'IHM ;
- protocole de scénario `HL7`, `FHIR` ou `MIXED` ;
- capture d'un dossier sous forme de scénario ou de template ;
- recalage cohérent des dates HL7 et préservation des intervalles ;
- génération d'une identité démographique commune aux étapes HL7 ;
- remplacement partiel des IPP, NDA et identifiants de venue ;
- envoi d'un scénario vers un endpoint MLLP ou FHIR ;
- journalisation par run et par étape ;
- tableau des exécutions, mode simulation et exécution en masse ;
- tests existants ciblés : 10 tests passés lors de l'état des lieux.

### Écarts qui empêchent le fonctionnement complet

| Écart | Conséquence |
|---|---|
| L'écran de détail impose un seul `endpoint_id` | Impossible d'adresser plusieurs destinations lors d'un même jeu |
| L'exécution en masse fait plusieurs scénarios vers un endpoint | Elle ne couvre pas un scénario vers plusieurs endpoints |
| Le runner choisit le transport d'après l'endpoint, pas d'après l'étape | Un scénario `MIXED` ne peut pas router correctement PAM + HPRIM + FHIR |
| Le runner ne supporte directement que MLLP et FHIR | Les étapes XML/HPRIM et FILE/FTP/SFTP ne sont pas réellement exécutables |
| Les identifiants HL7 sont générés dans plusieurs services | Risque de double remplacement et d'IPP/NDA différents entre deux étapes |
| La génération actuelle peut être relancée pour chaque étape HL7 | La cohérence patient/dossier d'un même jeu n'est pas garantie |
| Les OID de repli sont codés en dur dans une branche | Les namespaces de l'EJ ou du partenaire peuvent être contournés |
| La configuration EJ est parfois recherchée avec un identifiant de GHT | UF et médecin peuvent ne pas être adaptés au bon établissement |
| FHIR ne reçoit pas le contexte d'identifiants du jeu | Les références Patient/Encounter ne sont pas reliées aux messages PAM |
| La capture de dossier ne capture que les mouvements | Les actes CCAM/NGAP/UCD/LPP liés au dossier ne rejoignent pas le scénario |
| Le `dry_run` ne produit pas encore l'aperçu transformé | L'utilisateur ne peut pas vérifier les identifiants et routes avant envoi |
| « Envoyer seul » utilise implicitement le premier endpoint | L'action peut viser une destination incorrecte |
| Les étapes peuvent être ajoutées ou supprimées, mais pas éditées/réordonnées | La conception d'un scénario réaliste reste laborieuse |
| Les modèles `ScenarioTemplate` et `InteropScenario` se recouvrent | Deux chemins de création et de matérialisation peuvent diverger |
| Les runs sont isolés par endpoint sans groupe d'exécution | Pas de verdict global pour un jeu multi-endpoints |

## Architecture cible

```text
Scenario + version immuable
        │
        ▼
Création d'un ScenarioPlay (un « jeu »)
        │
        ├── génération atomique du contexte métier
        │     IPP, NDA, venue, mouvements, actes, messages, ressources FHIR
        │
        ├── compilation de chaque étape
        │     PAM adapter | HPRIM adapter | FHIR adapter | MFN adapter
        │
        ├── plan de routage
        │     étape × endpoints compatibles × politique d'erreur
        │
        └── livraisons persistantes / outbox
              MLLP | HTTP FHIR | HPRIM FILE/HTTP | FILE/FTP/SFTP
                         │
                         ▼
                 ACK + assertions + verdict global
```

Le contexte métier est généré avant le premier envoi et figé avec le jeu. La
compilation produit également les payloads finaux avant émission. Cela rend le
mode simulation exact, le retry déterministe et le diagnostic reproductible.

## Modèle de données cible

### Scénario et version

Conserver `InteropScenario` comme agrégat fonctionnel, puis ajouter une version
immuable ou une révision :

- `ScenarioVersion` : numéro, statut brouillon/publié/archivé, auteur logique,
  date et empreinte du contenu ;
- `ScenarioStep` : ordre, protocole, format, type de message, événement
  sémantique, template de payload, délai, assertions et politique d'erreur ;
- `ScenarioStepRoute` : mode `all_compatible`, endpoints explicites ou groupe
  logique de destinataires.

À terme, fusionner le rôle de `ScenarioTemplate` et `InteropScenario` : un
template publié est une version abstraite, une matérialisation est une version
concrète éditable. Pendant la migration, conserver une couche de compatibilité
pour les scénarios JSON existants.

### Jeu de scénario

Ajouter un agrégat parent de l'exécution :

- `ScenarioPlay` : scénario/version, GHT, EJ, clé unique de jeu, dates, statut,
  options, graine éventuelle et verdict global ;
- `ScenarioPlayTarget` : endpoints choisis et caractère obligatoire/optionnel ;
- `ScenarioPlayIdentifier` : rôle sémantique, namespace, valeur canonique et
  valeur projetée par système cible ;
- `ScenarioPlayStep` : snapshot du template, payload source et payload compilé ;
- `ScenarioDelivery` : une étape vers un endpoint, tentatives, ACK/réponse,
  statut, erreur et lien vers l'outbox.

`ScenarioExecutionRun` peut être migré vers `ScenarioPlay` ou devenir le run
par endpoint rattaché au jeu. Dans les deux cas, l'IHM doit disposer d'un
identifiant parent unique pour afficher le verdict complet.

### Système cible logique

Ajouter un regroupement logique ou une clé `target_system_key` aux endpoints.
Un même partenaire peut disposer d'un endpoint PAM MLLP, d'un endpoint HPRIM
fichier et d'un endpoint FHIR HTTP. Cette clé permet de partager la même
projection IPP/NDA entre ses différents transports.

## P0 back-end — rendre le jeu cohérent

### 1. Centraliser la génération des identifiants

Créer un `ScenarioPlayContextService` unique qui alloue en transaction :

- IPP et autorités d'affectation ;
- NDA/compte, identifiant de venue et éventuel identifiant d'épisode ;
- un identifiant de mouvement par événement sémantique ;
- un identifiant d'acte par étape HPRIM ;
- `MSH-10`, identifiant de message HPRIM et identifiants/logical IDs FHIR ;
- une identité patient de démonstration cohérente.

Supprimer la double génération actuellement répartie entre
`scenario_runner`, `scenario_identifier_replacer`, les générateurs de séquence
et la matérialisation des templates. Les adaptateurs reçoivent un contexte
déjà créé et ne génèrent plus eux-mêmes d'identifiant métier.

Prévoir des contraintes d'unicité et une allocation transactionnelle afin que
deux lancements simultanés ne produisent jamais la même valeur.

### 2. Définir le graphe de références

Chaque valeur à remplacer doit être identifiée par un rôle sémantique, pas par
une expression régulière isolée :

| Rôle | PAM HL7 | HPRIM XML | FHIR |
|---|---|---|---|
| Patient | `PID-3` | identifiant patient | `Patient.identifier` et références |
| Dossier | `PID-18` / compte | identifiant dossier | `EpisodeOfCare` ou identifiant métier retenu |
| Venue | `PV1-19`/`PV1-50` selon contrat | séjour/venue | `Encounter.identifier` |
| Mouvement | `ZBE-1` et références d'annulation/correction | si référencé | événement/Encounter associé |
| Acte | sans objet direct | identifiant de l'acte | ressource correspondante si utilisée |
| Message | `MSH-10` | identifiant message | `Bundle.id`, `fullUrl` et requêtes |

Ajouter des tests par événement PAM, notamment fusion/changement d'identifiant,
annulation et correction, afin de préserver aussi `MRG`, les références ZBE et
les liens inter-messages.

### 3. Compiler tous les protocoles

Créer un registre d'adaptateurs avec une interface commune :

```text
validate_template(step)
compile(step, play_context, target_system)
validate_output(payload)
supported_endpoint(endpoint)
send_or_enqueue(delivery)
decode_ack(response)
```

Implémenter en priorité :

1. IHE PAM HL7 v2.5 sur MLLP ;
2. HPRIM XML CCAM/NGAP/UCD/LPP sur FILE puis HTTP selon les endpoints ;
3. FHIR R4/FR Core sur HTTP ;
4. MFN^M05 sur MLLP si la structure fait partie du scénario.

Chaque payload compilé doit passer par le validateur de son protocole avant la
création des livraisons.

## P0 back-end — multi-endpoints et exécution durable

### 4. Construire le plan de routage

L'API de lancement reçoit `endpoint_ids[]`. Pour chaque étape, le planificateur
conserve uniquement les endpoints compatibles avec le protocole et les options
d'émission de l'endpoint.

Règles proposées :

- `all_compatible` par défaut : envoyer l'étape à tous les endpoints choisis
  qui la supportent ;
- `explicit` : une étape cible une sous-liste précise ;
- `target_system` : router vers le canal compatible d'un système logique ;
- refuser le lancement si une étape obligatoire n'a aucune destination ;
- afficher un avertissement pour un endpoint sélectionné qui ne recevra aucune
  étape.

Prévoir une politique d'erreur au niveau du scénario ou de l'étape :
`stop_all`, `continue_other_targets` ou `continue_all`. La valeur recommandée
pour une qualification multi-systèmes est `continue_other_targets`, avec
verdict global en échec si une livraison obligatoire échoue.

### 5. S'appuyer sur l'outbox

Créer toutes les livraisons avant le premier envoi et les relier à l'outbox
persistante. Ne plus confier une campagne longue à un simple
`asyncio.create_task`, qui est perdu au redémarrage.

Deux actions doivent être distinctes :

- **Réessayer la livraison** : même `ScenarioPlay`, même payload et mêmes
  identifiants ;
- **Rejouer comme nouveau jeu** : nouveau `ScenarioPlay`, nouveaux identifiants
  et nouveaux payloads compilés.

Le traitement doit être idempotent : une livraison déjà confirmée n'est pas
réémise sans action explicite.

### 6. Évaluer le résultat

Implémenter réellement `preconditions_json`, `assertions_json` et les
assertions par étape :

- ACK attendu (`AA`, HTTP 2xx ou acquittement HPRIM positif) ;
- nombre et type de messages envoyés ;
- absence de diagnostic bloquant avant émission ;
- présence d'identifiants identiques entre étapes liées ;
- contrôle optionnel de la BDD cible lorsque MedData Bridge pilote les deux
  environnements ;
- comparaison d'empreintes métier pour les roundtrips.

## P1 back-end — création et capture complètes

### 7. Capturer un dossier multi-protocoles

Faire évoluer la capture pour inclure :

- identité du patient ;
- chronologie PAM des dossiers, venues et mouvements ;
- actes CCAM, NGAP, UCD et LPP liés au dossier ;
- payloads FHIR ou MFN associés lorsque demandé ;
- dépendances explicites entre les étapes.

La capture crée des templates symboliques utilisant des jetons tels que
`{{patient.ipp}}`, `{{dossier.nda}}`, `{{movement.admission.id}}` et
`{{act.ccam_1.id}}`. Elle ne conserve pas comme valeurs fixes les identifiants
du dossier source.

### 8. Versionner et valider l'édition

- brouillon modifiable ;
- publication d'une version immuable ;
- duplication d'une version pour évolution ;
- archivage sans suppression des preuves d'exécution ;
- validation des ordres dupliqués, payloads vides, protocoles inconnus,
  références de jetons absentes et scénarios sans endpoint compatible ;
- import JSON versionné avec migration des anciens formats.

## P0 front-end — concepteur de scénario

Refondre la page de détail en concepteur organisé en quatre zones.

### 1. Identité du scénario

- nom, clé, version, statut, catégorie et description ;
- sujet `patient`, `dossier`, `structure` ou `mixte` ;
- GHT/EJ et politique temporelle ;
- bouton **Dupliquer**, **Publier**, **Archiver** et **Exporter**.

### 2. Timeline des étapes

- cartes ordonnées avec drag-and-drop et numérotation automatique ;
- badges de protocole et de type de message ;
- édition, duplication, suppression et activation/désactivation ;
- délai avant/après, dépendances et politique d'erreur ;
- éditeur spécialisé HL7, XML et JSON avec validation immédiate ;
- prévisualisation segmentée HL7, arbre XML ou ressource FHIR ;
- aperçu des jetons et références utilisés par chaque étape.

L'action « Envoyer seul » doit ouvrir le même sélecteur de destination que le
jeu complet ; elle ne doit plus utiliser silencieusement le premier endpoint.

### 3. Assistant de capture

Depuis un patient ou un dossier :

1. choisir la période et les venues ;
2. sélectionner les mouvements PAM ;
3. sélectionner les actes HPRIM ;
4. choisir les éventuels exports FHIR/MFN ;
5. afficher la chronologie détectée ;
6. enregistrer comme brouillon puis corriger les étapes.

## P0 front-end — lancement multi-endpoints

Créer un assistant de lancement en trois étapes.

### Étape 1 — Destinations

- sélection multiple par cases à cocher ;
- regroupement par système cible, GHT/EJ et protocole ;
- état de disponibilité et dernière erreur ;
- matrice indiquant quelles étapes seront envoyées à chaque endpoint ;
- blocage clair lorsqu'une étape obligatoire n'a aucune destination.

### Étape 2 — Jeu et simulation

- bouton **Générer un nouveau jeu** ;
- affichage de la clé du jeu et des nouveaux IPP/NDA/venue sans exposer de
  données nominatives réelles ;
- aperçu des payloads transformés et diff avec les templates ;
- dates calculées et délais estimés ;
- validation PAM/HPRIM/FHIR/MFN avant envoi ;
- mode `dry-run` utilisant exactement les payloads qui seraient envoyés.

### Étape 3 — Confirmation

- récapitulatif du nombre d'étapes et de livraisons ;
- endpoints obligatoires/optionnels ;
- politique en cas d'échec ;
- estimation de durée ;
- confirmation unique du lancement.

## P1 front-end — suivi d'exécution

Le détail d'un jeu doit afficher une matrice `étapes × endpoints` :

| Étape | PAM MLLP | HPRIM fichier | FHIR HTTP |
|---|---|---|---|
| A28 | `AA` | non concerné | 201 |
| A01 | `AA` | non concerné | 200 |
| CCAM | non concerné | acquitté | non concerné |

Pour chaque livraison, afficher : payload final, réponse/ACK décodé, durée,
tentatives et erreur. Ajouter les actions **Réessayer cette livraison**,
**Reprendre les échecs** et **Rejouer comme nouveau jeu** avec des libellés qui
expliquent clairement la différence d'identifiants.

Le verdict global doit distinguer `running`, `success`, `partial`, `failed`,
`cancelled` et `dry_run`.

## API cible

| Méthode et route | Usage |
|---|---|
| `POST /api/scenarios` | Créer un brouillon |
| `PUT /api/scenarios/{id}` | Modifier les métadonnées du brouillon |
| `POST /api/scenarios/{id}/steps` | Ajouter une étape |
| `PUT /api/scenarios/{id}/steps/{step_id}` | Modifier ou déplacer une étape |
| `POST /api/scenarios/{id}/validate` | Valider scénario, jetons et routage |
| `POST /api/scenarios/{id}/plays/preview` | Générer une simulation complète |
| `POST /api/scenarios/{id}/plays` | Lancer vers `endpoint_ids[]` |
| `GET /api/scenario-plays/{play_id}` | Suivre le verdict global |
| `GET /api/scenario-plays/{play_id}/deliveries` | Lire la matrice des livraisons |
| `POST /api/scenario-deliveries/{id}/retry` | Réessayer avec le même payload |
| `POST /api/scenario-plays/{id}/replay-as-new` | Créer un jeu avec de nouveaux identifiants |

Conserver temporairement les routes UI actuelles en adaptateurs, puis les
faire appeler cette API unique.

## Plan de tests

### Tests unitaires

- génération atomique et concurrente des identifiants ;
- même IPP/NDA dans toutes les étapes d'un jeu ;
- identifiants différents entre deux jeux ;
- remplacement des références PAM (`PID`, `PV1`, `ZBE`, `MRG`) ;
- remplacement HPRIM patient/dossier/acte/message ;
- références FHIR `identifier`, `fullUrl`, `subject` et `encounter` ;
- matrice de compatibilité étape/endpoint ;
- politiques d'arrêt et de continuation ;
- retry avec payload inchangé et replay avec nouveau payload.

### Tests d'intégration

Scénario minimal de preuve : A28 + A01 + acte CCAM + A02 + A03.

1. sélectionner un endpoint PAM et un endpoint HPRIM ;
2. lancer le jeu 1 et vérifier les ACK ;
3. vérifier que PAM et HPRIM désignent le même patient/dossier ;
4. lancer le jeu 2 ;
5. vérifier que tous les identifiants uniques diffèrent du jeu 1 ;
6. vérifier dans la BDD cible que les deux patients/dossiers coexistent ;
7. provoquer une panne HPRIM, redémarrer, puis reprendre via l'outbox ;
8. vérifier que le retry conserve les identifiants du jeu en échec ;
9. ajouter une destination supplémentaire et contrôler le fan-out ;
10. exécuter le même scénario avec une étape FHIR.

### Tests IHM E2E

- création et édition d'un scénario `MIXED` ;
- ajout, édition et réordonnancement des étapes ;
- sélection de plusieurs endpoints ;
- aperçu exact des identifiants et du routage ;
- blocage d'une combinaison incompatible ;
- progression temps réel et matrice des ACK ;
- retry et « nouveau jeu » clairement différenciés ;
- accessibilité clavier, focus, messages d'erreur et rendu mobile.

## Lots de réalisation

### Lot 1 — Socle du jeu

1. modèles `ScenarioPlay`, identifiants et livraisons ;
2. service unique de génération ;
3. compilation PAM complète ;
4. tests d'unicité et cohérence multi-étapes ;
5. migration des runs actuels.

Critère de sortie : deux exécutions du même scénario produisent chacune un jeu
cohérent et deux ensembles d'identifiants distincts.

### Lot 2 — Multi-protocoles

1. adaptateurs HPRIM et FHIR ;
2. partage des références patient/dossier ;
3. capture des actes ;
4. validation de sortie par protocole ;
5. scénario de preuve PAM + HPRIM.

Critère de sortie : un acte HPRIM est rapprochable du patient/dossier créé par
les étapes PAM du même jeu.

### Lot 3 — Multi-endpoints durable

1. sélection `endpoint_ids[]` ;
2. plan de routage ;
3. outbox par livraison ;
4. politiques d'échec ;
5. verdict global et reprise après redémarrage.

Critère de sortie : chaque endpoint compatible reçoit les étapes prévues, et
une panne n'efface ni le jeu ni ses identifiants.

### Lot 4 — UX complète

1. concepteur de timeline ;
2. assistant de capture ;
3. assistant de lancement ;
4. matrice de suivi ;
5. actions retry/nouveau jeu et export de rapport.

Critère de sortie : un intégrateur peut créer, vérifier, lancer et diagnostiquer
un scénario multi-protocoles sans modifier manuellement la BDD ni le code.

### Lot 5 — Qualification finale

1. tests E2E et roundtrip entre environnements isolés ;
2. charge avec plusieurs scénarios/endpoints simultanés ;
3. migration d'un corpus de scénarios existants ;
4. documentation utilisateur ;
5. activation des tests dans la CI bloquante.

## Définition de terminé

Le chantier est terminé lorsque :

- un scénario peut être créé, capturé, édité, versionné et archivé ;
- il peut combiner au minimum IHE PAM et HPRIM, puis FHIR ;
- un lancement accepte un ou plusieurs endpoints compatibles ;
- les identifiants sont cohérents dans un jeu et différents au jeu suivant ;
- retry et nouveau jeu ont des comportements distincts et testés ;
- le suivi montre toutes les livraisons, ACK, erreurs et assertions ;
- le scénario de preuve est rejoué automatiquement en CI ;
- deux jeux successifs coexistent dans la BDD réceptrice sans écrasement.
