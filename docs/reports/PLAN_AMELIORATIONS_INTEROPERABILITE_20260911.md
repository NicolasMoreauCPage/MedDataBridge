# Plan d'amélioration de la plateforme d'interopérabilité

Date initiale : 11 septembre 2026
État consolidé : 12 septembre 2026
Périmètre : IHE PAM France, HPRIM XML pour les actes, HL7 MFN et FHIR pour la structure
Hors périmètre volontaire : sécurité et contrôle d'accès, le projet étant destiné à fonctionner sur un LAN local

> Statut documentaire : ce plan conserve les travaux proposés à l'origine.
> Les sections « état actuel » ont été actualisées ; les sections « travaux à
> réaliser » décrivent soit les suites restantes, soit le périmètre de la
> preuve déjà obtenue. Pour l'état de référence, voir aussi
> [README_FOR_REPORTS.md](README_FOR_REPORTS.md).

## Synthèse

Le cœur IHE PAM France/CPage est désormais solide sur le corpus disponible. Le roundtrip réel entre deux environnements GHT a transmis 125 messages générés avec 125 ACK `AA`, puis obtenu des données métier identiques dans les deux BDD.

Le prochain gain de qualité consiste à appliquer ce même niveau de preuve aux trois autres chaînes d'interopérabilité :

- HPRIM XML pour CCAM, NGAP, UCD et LPP ;
- HL7 MFN M05 pour la structure hospitalière ;
- FHIR FRCore pour la structure administrative et physique.

## Priorités

| Priorité | Chantier | Objectif |
|---|---|---|
| P0 | Roundtrip HPRIM complet | Deux BDD isolées et comparaison champ par champ pour CCAM, NGAP, UCD et LPP |
| P0 | FHIR Structure FRCore | Unifier l'émission temps réel avec le convertisseur FRCore conforme |
| P0 | CI automatique | Exécuter à chaque push les tests PAM, HPRIM, MFN, FHIR et les roundtrips |
| P1 | Roundtrip Structure | Vérifier `BDD-1 → MFN/FHIR → BDD-2`, y compris renommage, déplacement et fermeture |
| P1 | Consolidation du code | Supprimer les parseurs/générateurs concurrents et découper les services trop volumineux |
| P1 | IHM de qualification unifiée | Comparer message reçu, message généré, ACK, diagnostic et données BDD |
| P2 | Fiabilité des émissions | Ajouter une file persistante, la reprise après redémarrage et le suivi des refus définitifs |
| P2 | Performance | Qualifier plusieurs endpoints simultanés et de grosses structures hospitalières |

## Avancement de l'implémentation — 12 septembre 2026

Les premiers développements du plan sont intégrés dans cette branche :

- le point d'entrée `/roundtrip-hprim` possède un contrat commun explicite
  `CCAM`, `NGAP`, `UCD` ou `LPP` ;
- les XML générés pour ces quatre catégories sont validés contre le XSD HPRIM
  2.4 avant stockage ;
- les actes sont archivés dans une projection SQL canonique commune, ce qui
  permet la comparaison de BDD au-delà des seules tables historiques CCAM et
  NGAP ;
- les acquittements HPRIM LPP et UCD sont générés et validés contre leur XSD ;
- les anciens tests HPRIM génériques marqués `xfail` ont été remplacés par un
  roundtrip effectif génération → téléchargement → réintégration pour les
  quatre catégories ;
- l'émission FHIR Structure temps réel passe désormais par le même exporteur
  `StructureToFHIRConverter`/FRCore que l'export manuel ;
- l'import FHIR reconstruit désormais les `Organization` puis les `Location`
  dans l'ordre hiérarchique, résout les références `partOf` par identifiant
  métier et reste idempotent ;
- un vrai roundtrip MFN M05 entre deux BDD vérifie EJ, EG, pôle, service, UF,
  UH, chambre et lit ; l'émetteur distingue maintenant correctement une EJ
  (`M`) d'une EG (`ETBL_GRPQ`) ;
- un vrai roundtrip FHIR FR Core entre deux BDD vérifie la même hiérarchie,
  ses relations parent-enfant et l'absence de doublon au rejeu ;
- une CI bloquante a été ajoutée pour PAM/CPage, HPRIM, MFN et FHIR.
- une outbox SQL persistante reprend les `MessageLog` sortants en échec, avec
  backoff exponentiel, limite de tentatives, rejeu manuel et points d'API de
  supervision (`/outbox`) ;
- les roundtrips FHIR couvrent aussi le renommage, la désactivation, le
  déplacement d'un service et le diagnostic explicite d'un parent inconnu.

La campagne locale associée est verte : les tests ciblés PAM, HPRIM, MFN et
FHIR, puis le roundtrip PAM CPage, sont exécutés dans le même enchaînement que
la CI.

## P0 — Roundtrip HPRIM XML — corrigé sur le périmètre courant

### État actuel

Les quatre catégories `CCAM`, `NGAP`, `UCD` et `LPP` disposent maintenant d'un
contrat commun de génération, d'une validation XSD et d'un test de roundtrip.
Les acquittements LPP/UCD conformes aux XSD fournis sont également couverts.

Reste ouvert : enrichir les acquittements métier CCAM/NGAP lorsque le contrat
fonctionnel de réponse détaillée sera stabilisé avec les systèmes partenaires.

### Travaux à réaliser

1. Définir un contrat commun de génération portant explicitement le type `CCAM`, `NGAP`, `UCD` ou `LPP`.
2. Dispatcher vers le générateur et le récepteur propres à chaque type d'acte.
3. Valider chaque XML entrant et sortant avec le XSD HPRIM correspondant.
4. Générer et intégrer les acquittements HPRIM complets.
5. Créer deux environnements et deux BDD isolés, comme pour le roundtrip PAM.
6. Générer les actes dans le premier environnement, transmettre réellement les XML, puis les intégrer dans le second.
7. Comparer les actes, interventions, patients, venues, exécutants, montants, modificateurs et identifiants métier.
8. Ajouter un corpus négatif : XML mal formé, élément requis absent, code invalide, montant incohérent, doublon et référence inconnue.

### Critère d'acceptation

- 100 % des XML valides sont acceptés et acquittés ;
- 100 % des erreurs injectées attendues sont détectées ;
- les empreintes métier HPRIM des deux BDD sont identiques pour les quatre catégories d'actes.

## P0 — Unifier FHIR Structure sur FRCore — corrigé pour les échanges

### État actuel

L'export principal et l'émission temps réel utilisent le même convertisseur
FRCore. L'import traite les `Organization` avant les `Location`, résout les
références déterministes `partOf` et met à jour les lignes existantes au lieu
de les dupliquer. Le roundtrip inter-BDD est automatisé. La vérification finale
contre FR Core 2.2.0 est consignée dans
`docs/reports/VERIFICATION_FHIR_FRANCE_FR_CORE_2_2_0_20260912.md` : les
canonicals sont versionnés et les établissements emploient les types officiels
`LEGAL-ENTITY` et `GEOGRAPHICAL-ENTITY` du système FR Core v2-3307.

### Travaux à réaliser

1. Faire de `StructureToFHIRConverter` l'unique convertisseur de structure pour les échanges partenaires.
2. Retirer ou adapter l'ancien mapping de `app/services/fhir_structure.py` : il reste réservé à la recherche IHM historique et ne doit pas être utilisé comme interface FR Core partenaire.
3. Utiliser le même convertisseur pour l'export manuel et l'émission temps réel.
4. Stabiliser les identifiants FINESS, OID et URI dans les deux sens.
5. Conserver les relations hiérarchiques avec des références `partOf` déterministes.
6. Valider les ressources avec les profils FRCore ciblés et produire des `OperationOutcome` exploitables.

### Critère d'acceptation

Une structure créée en BDD, exportée en FHIR puis réintégrée dans une BDD vide doit restituer les mêmes entités, relations, identifiants, statuts et libellés.

## P1 — Construire un vrai roundtrip de structure MFN et FHIR

### État courant

Le scénario initial, le rejeu idempotent et la comparaison des liens de la
hiérarchie complète sont automatisés pour MFN et FHIR, chacun entre deux bases
SQLite indépendantes. FHIR couvre également renommage, désactivation,
déplacement et parent inconnu. Restent à compléter pour MFN les mêmes mutations
avancées, les suppressions protocolaires, l'ordre volontairement inversé et la
qualification gros volume.

### Architecture de test cible

```text
Structure GHT-1
    ├── HL7 MFN^M05 par MLLP ──> GHT-2 / BDD-2
    └── FHIR transaction HTTP ──> GHT-3 / BDD-3
```

### Données à comparer

- GHT et entités juridiques ;
- entités géographiques ;
- pôles et services ;
- unités fonctionnelles et unités d'hébergement ;
- chambres et lits ;
- identifiants locaux, globaux, FINESS et OID ;
- relations parent-enfant ;
- statuts, dates d'ouverture et de fermeture ;
- rattachements aux namespaces et aux endpoints.

### Scénarios nécessaires

1. Création d'une structure complète.
2. Import initial dans une BDD vide.
3. Réimport idempotent du même contenu.
4. Modification d'un libellé ou d'un statut.
5. Déplacement d'une entité dans une autre branche.
6. Fermeture ou désactivation d'une entité.
7. Suppression lorsque le protocole et le modèle l'autorisent.
8. Réception dans le désordre, avec résolution différée des parents.
9. Référence vers un parent inexistant, avec diagnostic explicite.
10. Gros volume comparable au fichier MFN de 1 946 entités déjà testé.

### Critère d'acceptation

Les empreintes métier des structures obtenues par MFN et FHIR doivent être identiques à celle de la structure source. Une structure partiellement importée doit produire un verdict d'échec explicite et non un succès ambigu.

## P1 — Consolider l'architecture

### Constat

Le dépôt contient plusieurs implémentations qui se recouvrent :

- plusieurs parseurs PID/PV1/ZBE ;
- plusieurs générateurs HL7 ;
- plusieurs chemins FHIR Structure ;
- plusieurs définitions ou générations HPRIM ;
- des services et routeurs dépassant fréquemment 1 500 à 2 000 lignes.

Cette duplication augmente le risque qu'un correctif soit appliqué à un chemin mais pas à celui réellement utilisé en émission ou en réception.

### Architecture cible

```text
Modèle métier canonique
    ├── adaptateur IHE PAM France
    ├── adaptateur HL7 MFN
    ├── adaptateur FHIR FRCore
    └── adaptateur HPRIM XML
```

Chaque adaptateur doit posséder :

- un parseur ;
- un générateur ;
- un validateur ;
- un mapping vers le modèle métier ;
- une matrice de tests positifs, négatifs et roundtrip.

Le transport MLLP, HTTP ou fichier doit rester indépendant du contenu fonctionnel.

## P0 — Réactiver une CI réellement bloquante

### État actuel

Le workflow bloquant
[`interop-conformance.yml`](../../.github/workflows/interop-conformance.yml)
est maintenant présent et couvre les contrôles de compilation, PAM/CPage,
HPRIM, MFN, FHIR et l'outbox. Les anciens workflows suffixés `.disabled`
restent de la documentation historique et ne décrivent pas la CI active.

La campagne ciblée est la preuve de conformité prioritaire. La suite complète
reste utile pour les régressions générales ; elle ne doit pas transformer un
échec E2E sans rapport avec les protocoles en verdict de non-conformité PAM,
HPRIM, MFN ou FHIR.

### Pipeline minimal recommandé

1. Compilation Python et contrôle `git diff --check`.
2. Tests unitaires sans `xfail` inattendu.
3. Validation IHE PAM France et corpus CPage.
4. Roundtrip PAM entre deux BDD.
5. Validation XSD et roundtrip HPRIM.
6. Roundtrip de structure MFN.
7. Validation et roundtrip FHIR FRCore.
8. Tests IHM ciblés sur les parcours de qualification.
9. Publication des rapports et empreintes comme artefacts CI.

La CI doit échouer si un message généré n'est plus accepté par le propre récepteur de l'application ou si une empreinte BDD diverge.

## P1 — Unifier l'IHM de qualification

L'application devrait proposer un même parcours de diagnostic pour PAM, HPRIM, MFN et FHIR.

### Écran cible

- choix du protocole et du profil ;
- message entrant et message régénéré côte à côte ;
- différence syntaxique et différence sémantique ;
- arborescence des segments HL7, éléments XML ou ressources FHIR ;
- données BDD créées, modifiées ou ignorées ;
- ACK HL7/HPRIM ou `OperationOutcome` FHIR décodé ;
- filtrage par sévérité, champ et code d'erreur ;
- copie, téléchargement, correction et rejeu ;
- lancement d'un roundtrip depuis l'IHM ;
- rapport de qualification téléchargeable sans données nominatives.

Pour PAM, les assistants guidés devront progressivement couvrir les événements avancés A44, A52/A53, A54/A55 et Z99, ainsi que les extensions françaises réellement conservées.

## P2 — Fiabiliser les émissions — socle implémenté

Les retries en mémoire sont utiles pour une indisponibilité courte, mais ils ne garantissent pas la reprise après redémarrage du programme.

### Évolution recommandée

Ajouter une table d'outbox persistante contenant :

- protocole et endpoint cible ;
- payload généré ;
- identifiant de corrélation ;
- nombre de tentatives ;
- date de prochaine tentative ;
- dernier ACK ou dernière erreur ;
- statut `pending`, `sent`, `retry` ou `failed`.

Le worker appelable via `POST /outbox/process` reprend les messages après
redémarrage. Les échecs sortants historiques sont récupérables via
`POST /outbox/recover`, et une ligne peut être replanifiée avec
`POST /outbox/{id}/retry`. Les messages définitivement refusés restent donc
consultables et rejouables. La planification périodique du worker dépend du
mode de déploiement (cron, service systemd ou ordonnanceur applicatif).

## P2 — Mesurer les performances réelles

La qualification doit couvrir :

- plusieurs endpoints MLLP et FHIR simultanés ;
- un import MFN de plusieurs milliers d'entités ;
- un flux continu de messages PAM ;
- des lots HPRIM importants ;
- les écritures concurrentes et les risques de verrouillage SQLite ;
- le temps de validation XSD et FHIR ;
- le temps de génération et de comparaison des rapports.

Si les tests montrent que SQLite limite les écritures concurrentes, PostgreSQL devra devenir le moteur recommandé pour les campagnes multi-endpoints, même sur un LAN local.

## P2 — Nettoyer la documentation et la dette de tests

Plusieurs rapports conservent volontairement les constats effectués avant correction. Cette traçabilité est utile, mais elle rend parfois difficile l'identification de l'état réellement courant.

Actions de maintenance restantes :

1. ajouter un statut clair `corrigé`, `encore ouvert` ou `hors périmètre` à chaque écart ;
2. séparer les constats historiques de la matrice courante ;
3. retirer ou réécrire les tests visant d'anciennes API ;
4. supprimer les `xfail` devenus sans objet ;
5. stabiliser les scénarios E2E généraux restant sensibles à l'isolation ou
   aux transitions de page ;
6. conserver un rapport de référence unique par protocole.

## Ordre de réalisation proposé

### Lot 1 — Preuve fonctionnelle

1. Roundtrip HPRIM CCAM/NGAP/UCD/LPP.
2. Acquittements HPRIM et validation XSD complète.
3. Correction du chemin FHIR Structure temps réel.
4. Activation d'une CI minimale.

### Lot 2 — Structure multi-protocole

1. Harness deux/trois GHT pour MFN et FHIR.
2. Comparaison BDD canonique de structure.
3. Scénarios de mise à jour, déplacement, fermeture et erreurs de parenté.
4. Qualification sur gros volume.

### Lot 3 — Industrialisation fonctionnelle

1. Refactorisation des parseurs, générateurs et validateurs.
2. Outbox persistante et supervision des retries.
3. IHM unifiée de qualification et de comparaison.
4. Nettoyage des tests et de la documentation historique.

## Conclusion

La priorité n'est plus d'ajouter isolément de nouveaux champs. Elle est de garantir qu'un même état métier traverse sans perte chacun des protocoles revendiqués, que les erreurs soient détectées au bon niveau et que cette preuve soit rejouée automatiquement à chaque évolution du programme.

L'objectif final est donc une plateforme où PAM, HPRIM, MFN et FHIR utilisent un modèle métier commun, disposent chacun d'un adaptateur unique et sont tous couverts par un vrai roundtrip avec comparaison BDD.
