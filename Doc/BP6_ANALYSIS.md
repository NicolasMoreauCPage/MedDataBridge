
# Analyse détaillée BP6 (IHE PAM France) — conformité du validateur `app/services/pam_validation.py`

Objectifs
- Lire et formaliser les exigences de la checklist France (BP6) fournie dans `Doc/BP6/IHE-PAM-FR-FHIR.xlsx.ods`.
- Cartographier ces exigences vers les contrôles actuellement implémentés dans `app/services/pam_validation.py`.
- Dresser une liste précise des contrôles manquants ou partiellement couverts, en précisant lesquels sont :
  - stateless (par-message) et peuvent être exécutés purement à partir du message HL7 ;
  - stateful (dépendent d'un contexte/chaîne de messages, historique/DB).
- Proposer un plan d'actions priorisé (correctifs + tests) et l'architecture recommandée pour les contrôles stateful.

Contexte technique
- Le projet expose `validate_pam(msg, direction="in", profile="IHE_PAM_FR")` dans `app/services/pam_validation.py` et l'utilise pour la validation au moment d'émettre des messages (cf. `app/services/emit_on_create.py`).
- Le validateur actuel implémente déjà : règles HL7 v2.5 de base, structures HAPI / SEGMENT_RULES et quelques extensions PAM FR (ZBE). Il est principalement per-message (stateless).

Méthode d'analyse
- Extraction des items pertinents du fichier BP6 (ODS) : scénarios, contrôles par segment (PID, PV1, ZBE...) et indications de validations qui doivent être effectuées seulement dans le cadre d'un scénario/chaine (ex: vérifier l'existence d'un mouvement pour ZBE-6 lors d'un CANCEL).
- Lecture du fichier `app/services/pam_validation.py` pour retrouver les validations existantes et les codes d'issue produits.

1) Exigences BP6 — synthèse par segment / zone

1.1 MSH / EVN
- MSH-1 Field Separator = "|" (contrôle déjà présent).
- MSH-2 Encoding Characters = "^~\\&" (warn si différent).
- MSH-9 format: type^trigger[^structure] (vérifie trigger correspondant à EVN)
- MSH-10 non vide (Message Control ID). Ces contrôles existent dans `pam_validation`.

1.2 PID (Patient identity)
- PID-3 (Patient Identifier List) :
  - Exigence BP6 FR : doit inclure au moins une occurrence INS-C (identifiant national) — OBLIGATOIRE pour la France.
  - Attendu : CX with assigning authority including ASIP-SANTE OID `1.2.250.1.213.1.4.2` or explicit `INS-C` token in component; vérifier répétitions (~) — controle ajouté récemment.
- PID-5 (Name) : XPN validation (family/given minimal) - déjà contrôlé.
- PID-7 date de naissance TS format – déjà contrôlé.
- PID-11 addresses, PID-13 phone XTN: contrôles présents (déjà stricts pour PID-13 selon env vars).
- PID-32 identityStatus (PROV/VALI/CACH) : BP6 décrit comportements dépendants de ce statut (p.ex. refuser modification si VALI?). Actuellement non-transformé en règle stricte dans le validateur — à ajouter selon scénario.

1.3 PV1 / Visit (Venue)
- PV1 presence: requis pour événements de séjour (A01, A03, A04, A05, A06, A08, A11, A12, A13, A21, A22, A23 etc.). `pam_validation` vérifie REQUIRE_PV1 et alerte si PV1 manquant.
- PV1-19 (Visit Number) : recommandé/obligatoire pour événements de séjour (BP6) — check ajouté récemment (PV1_19_MISSING).
- PV1-3 Assigned Patient Location (PL): structure `PointOfCare^Room^Bed^Facility^LocationStatus^...`.
  - PV1-3.1 (UF / PointOfCare) : doit être renseignée pour les événements de séjour.
  - PV1-3.2 (Room / chambre) et PV1-3.3 (Bed / lit) : pour A02 (mutation/transfert), BP6 exige la destination complète (UF+chambre+lit).
  - PV1-3.5 LocationStatus : PV1-3.5 indications pour scénarios permission/réservation (valeurs: O=Occupied, U=Unoccupied, etc.). Le validateur produit info/warn selon values.
- PV1-2 Patient Class : doit être un code valide (I, E, O, etc.) — contrôlé.
- PV1-36 (Discharge disposition / sortie mode) : utilisé dans scénarios (p.ex. P pour permission) — pas strictement contrôlé aujourd'hui.
- PV1-41 (Discharge code) : marque la fermeture d'une venue (PV1-41=D) — utile pour valider séquences et clôtures de venue (stateful requirement).
- PV1-44/45 (Admit/Discharge timestamps) : contrôles TS déjà présents.

1.4 ZBE (Extension IHE PAM France)
- ZBE-1 (id mouvement) : requis, doit contenir namespace (composants 2 ou 3) — `pam_validation` génère `ZBE1_NAMESPACE_MISSING` si absent.
- ZBE-2 (date/heure mouvement) : requis, format TS — contrôlé.
- ZBE-4 (action) : INSERT/UPDATE/CANCEL — contrôlé et erreur si absent/incorrect.
- ZBE-5 (historic flag) : Y/N — contrôlé.
- ZBE-6 (trigger original) : requis pour UPDATE/CANCEL — contrôlé, mais la vérification d'existence du mouvement référencé est stateful (non seulement la présence du champ) — à ajouter.
- ZBE-7 (UF médicale XON) : contrôle presence/composant 10 — déjà présent.
- ZBE-8 (UF soins) : warn si absent (compatibilité legacy) — actuellement info.
- ZBE-9 nature : normalisation et rejet/alerte sur tokens non standard — contrôlé.

1.5 Autres segments
- PD1, NK1, PV2, MRG — PV2 et MRG sont optionnels selon trigger; HAPI structures dans `SEGMENT_RULES` sont renseignées.

2) Analyse de la mise en œuvre actuelle (`app/services/pam_validation.py`)

2.1 Contrôles présents (récapitulatif)
- Vérifications HL7 de base : MSH/EVN/PID parsing, MSH field checks, EVN consistency, TS validation, etc.
- PID validation : CX/XPN/XAD/XTN validations, et maintenant INS-C existence check (nouveau).
- PV1 validation : PV1-2 class check, PV1-3 PL parsing (warn if parts manquantes), PV1-19 CX validation, PV1 timestamps validation.
- ZBE validation : présence/format de ZBE-1..ZBE-9, checks sur namespace, action, historic flag, ZBE6 presence when required.
- Segment order validation : `_validate_segment_order` using `SEGMENT_ORDER` mapping (warns when order wrong).

2.2 Contrôles récemment ajoutés (delta)
- `PID3_INS_C_MISSING` (error) when PID-3 lacks INS-C.
- `PV1_19_MISSING` (error) when PV1-19 missing for stay events.
- PV1-3 component checks: added errors for missing PV1-3.1 for stay events; strict errors for A02 when room/bed missing (`PV1_3_2_MISSING_A02`, `PV1_3_3_MISSING_A02`).

3) Contrôles BP6 manquants ou à renforcer (détaillés)

3.1 Stateless (par-message) — à ajouter/renforcer
- PID-32 identityStatus handling : BP6 précise des comportements différents selon PROV/VALI/CACH — il faut définir la règle exacte et ajouter checks (ex: if PID-32==VALI then reject modifications to core attributes (PID-5, PID-7)).
- PV1-36 (mode de sortie) : ajouter vérifications contextuelles (ex: permission flows expect PV1-36=P) — aujourd'hui non contrôlé.
- PV1-3.4 Facility (entité géographique) : vérifier conformité si présente.
- Standardiser et configurer gravité (error/warn/info) selon profil (STRICT_PAM_FR env var) pour les warnings BP6 -> certaines valeurs peuvent devenir errors en mode strict.

3.2 Stateful / séquence (nécessitent historique DB) — prioritaires
- ZBE-6 target existence and consistency: for UPDATE/CANCEL actions, find referenced movement (by ZBE-6 or id) in DB and validate patient/venue/type concordance; else error (not only field presence).
- Transition semantics: validate that incoming trigger is allowed given last persisted event for the venue (use `ALLOWED_TRANSITIONS` in `app/state_transitions.py`). Already partially used elsewhere in the code but should be part of sequence validator for inbound messages.
- Reservation / occupation checks: for A21 (permission) where PV1-3.5=O and ZBE flags indicate reservation, mark bed reserved; subsequent events (A22 return, A02 transfer) should consult reservations/occupancy before accepting (could be warn or error depending policy).
- Venue lifecycle checks: if PV1-41=D indicates last venue, verify that further movements that would reference the closed venue are either rejected or treated as new venue depending on PV1-51 / ZBE semantics.

4) Plan d'implémentation détaillé (priorisé)

Phase 0 — stabilisation rapide (low-risk)
- Ajouter/mettre à jour tests unitaires pour les contrôles récemment ajoutés (PID-3 INS-C, PV1 A02 rules). Tests to add in `tools/` as existing test harness uses HL7 sample messages.
- Ajouter configuration `STRICT_PAM_FR` handling pour piloter gravité des violations BP6.

Phase 1 — contrôles per-message (stateless) à finaliser
- PID-32 identityStatus enforcement rules (documenter comportement métier et coder). Exemple : when PID-32=="VALI" then modifications to PID-5/PID-7 rejected (error).
- PV1-36 validation rules for permissions and exit modes (map BP6 scenarios to PV1-36 expected values).
- Add more granular PV1-3.4/3.5 checks and explicit codes mapping.

Phase 2 — validateur stateful (séquence) — implémentation recommandée
- Nouveau module `app/services/pam_sequence_validator.py`.
  - API proposée:
    - `def validate_pam_sequence(msg: str, session, direction: str = "in") -> List[ValidationIssue]`
    - `def find_mouvement_by_zbe_id(session, zbe_id: str) -> Optional[Mouvement]`
  - Fonctionnalités:
    - Pour ZBE with action UPDATE/CANCEL: verify ZBE-6 references an existing movement and that patient/venue match.
    - Verify allowed transitions using `ALLOWED_TRANSITIONS` and last persisted event for the venue; return error if trigger not allowed.
    - Bed reservation/occupation policy: consult DB (Chambre/Lit occupancy) to verify conflicts; either raise error or warning depending on policy.
    - Venue lifecycle checks: ensure that messages referencing closed venues are handled according to BP6 rules (reject or create new venue).

Integration points
- Call `validate_pam` (stateless) first, then `validate_pam_sequence` before persisting movements or accepting inbound messages. Integration points:
  - ingestion endpoints (where HL7 raw messages are received or parsed),
  - `emit_on_create` flows for outbound validation (stateful checks not required for outbound in all cases but useful for logging),
  - message processing pipeline where messages are converted to DB entities.

Phase 3 — tests & reporting
- Add unit tests covering BP6 scenarios in `tools/` (extend `tools/test_ihe_pam_complete.py`, `tools/test_ihe_pam_with_zbe.py`).
- Add end-to-end integration tests that simulate the sequences described in BP6 (A01→A02→A03, permission/reservation flows, preadmission→admission).
- Update UI/logging to expose validation issues for inbound messages (similar to outbound handling where PAM issues are stored on messages).

5) Mapping concret vers le code (`pam_validation.py`) — où se trouvent déjà les checks
- Segment rules & order: `SEGMENT_RULES`, `SEGMENT_ORDER`, `_validate_segment_order`.
- PID checks: `_validate_cx_identifier`, `_validate_xpn_name`, `_validate_xad_address`, `_validate_xtn_telecom`.
- PV1 checks: code in the PV1 handling block (PV1-2 class, PV1-3 PL parsing, PV1-19 call to `_validate_cx_identifier`, PV1-44/45 TS checks).
- ZBE checks: ZBE block starting with `_get_first_segment(msg, "ZBE")` and subsequent checks (ZBE1..ZBE9).

6) Contrôles à implémenter prioritairement (récapitulatif)
1. ZBE-6 existence & consistency check (stateful) — HIGH
2. Allowed transition check against persisted last event for the venue (stateful) — HIGH
3. PID-32 enforcement rules (stateless but business-sensitive) — MEDIUM
4. PV1 reservation/occupation checks (stateful) — MEDIUM
5. PV1-36 / PV1-41 scenario checks (stateless partly, stateful for venue closure) — MEDIUM

7) Prochaines étapes (proposition d'exécution)
- Étape A (immédiate) : créer tests unitaires pour les règles ajoutées (PID-3 INS-C, PV1 A02) — 1-2 heures.
- Étape B : implémenter `app/services/pam_sequence_validator.py` avec ZBE-6/mouvement lookup + transition checks + tests unitaires — 1-2 jours selon complexité des règles et disponibilité des fixtures DB.
- Étape C : intégrer l'appel au validateur stateful dans le pipeline d'ingestion et exécuter les scenarii BP6 end-to-end (tests automatisés).

Annexe A — Exemples BP6 extraits (non-exhaustif)
- A02 scenarios where PV1-3 must include room/bed (several occurrences in BP6 file): transfers/mutations described explicitly require PV1-3.1/3.2/3.3.
- Permission/reservation scenarios: PV1-3.5=O and PV1-36=P are indicators; ZBE fields supply movement ids and actions (INSERT/UPDATE/CANCEL) for reservation lifecycle.

Annexe B — Questions ouvertes / décisions métier à prendre
- En cas de conflit de réservation (lit déjà occupé) : bloquer (error) ou accepter with warning? (proposer erreur en mode strict, warning otherwise).
- Politique pour PID-32=VALI : quelles modifications doivent être refusées ? (nom/dateNaissance/sex?)

Validation requise
- Confirmez si vous validez cette analyse — je lancerai ensuite l'implémentation prioritaire (A: tests unitaires puis B: validateur stateful). Si vous voulez, je peux commencer immédiatement par écrire `app/services/pam_sequence_validator.py` et un jeu de tests unitaires minimal pour ZBE-6/UPDATE/CANCEL.

-- fin

