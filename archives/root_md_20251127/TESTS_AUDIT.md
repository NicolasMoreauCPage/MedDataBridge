# Audit de la suite de tests — MedDataBridge

Date : 2025-11-27
Branch : `refactor/dossier-service-edit`
Contexte : exécution complète des tests via `python -m pytest -q` sur l'environnement local (Windows, Python embed 3.13.9).

---

## Résumé d'exécution
- Durée d'exécution : ~21 minutes (1307.13s)
- Résultat global : 118 failed, 416 passed, 45 skipped, 68 xfailed, 30 xpassed, 10 errors
- Warnings massifs : ~8291 warnings (principalement DeprecationWarning `datetime.utcnow()` et SAWarning identity-map)

---

## Regroupement des causes principales (diagnostic)
J'ai analysé les traces et regroupé les échecs par catégories susceptibles d'expliquer la majorité des échecs.

1) Emissions asynchrones / event hooks (`app/services/entity_events.py`) — InterfaceError SQLite
- Symptômes : `sqlite3.InterfaceError: bad parameter or other API misuse` lors d'appels à `emit_session.get(entity_class, entity_id)` exécutés dans des threads d'arrière-plan après `after_commit`. Messages répétés "Entity not found in new session: patient id=...".
- Impact : provoque des échecs/interruption dans de nombreux tests qui dépendent d'émissions ou d'effets attendus.
- Cause probable : utilisation de SQLite in-memory + threads/pls de sessions non adaptée à l'usage actuel des listeners asynchrones.

2) Modèles / champs manquants (mismatch modèle/tests)
- Symptômes : `AttributeError: 'X' object has no attribute 'y'` pour `Patient.patient_seq`, `Pole.physical_type`, `Venue.operational_status`, `Mouvement.uf_medicale_*`, etc.
- Impact : tests d'API, d'export FHIR, et scénarios échouent massivement.
- Cause probable : refactorisations récentes ont renommé/retiré des champs ou modifié les noms attendus par tests et code.

3) Validators HL7 / PAM
- Symptômes : tests attendent `success` mais reçoivent `error` ; validateurs signalent champs manquants (p.ex. PID-3, PID-18).
- Impact : échecs dans la réception ADT/PAM et tests d'intégration IHE.
- Cause probable : modifications précédentes sur le parsing CX/identifier ou sur la normalisation des dates/format HL7 ont altéré la forme des messages validés.

4) Bcrypt / hashing mot de passe
- Symptômes : `ValueError: password cannot be longer than 72 bytes, truncate manually...` dans tests d'auth.
- Impact : tests d'authentification et de hashing échouent.
- Cause probable : tests (ou valeur par défaut dans fixtures) fournissent des chaînes plus longues ; hachage bcrypt impose 72 bytes max.

5) DB / flush / refresh errors (InvalidRequestError, NULL identity)
- Symptômes : `Instance <Dossier ...> has a NULL identity key`, `Could not refresh instance '<X>'`, erreurs OperationalError.
- Impact : erreurs critiques de persistance entraînant échecs nombreux.
- Cause probable : flush/commit qui surviennent pendant des callbacks (event listeners) ou objets mal initialisés avant flush ; interactions avec listeners asynchrones aggravent la concurrence sur la connection SQLite.

6) Playwright / tests UI
- Symptômes : `BrowserType.launch: Executable does not exist` pour tests UI (Playwright). Erreurs non liées au code métier mais à l'environnement (navigateur non installé).
- Impact : UI tests échouent / errors.

7) Failures isolés (assertions métier)
- Exemples : emissions manquantes, perte de champs multi-valued, mapping d'identifiants incorrect.
- Impact : restent après suppression des causes techniques.

---

## Exemples représentatifs (test, description, cause observée)
(ci-dessous quelques cas choisis parmi les 118 échecs pour donner une vue claire)

- tests/test_a06_a07_reception.py::TestA06Reception::test_a06_reception_without_previous_history
  - Ce que teste : réception ADT A06 en l'absence d'antécédent; vérifie création d'entités et états.
  - Cause d'échec observée : assertion sur None — absence d'entité attendue due à échec d'émission ou créations interrompues par InterfaceError dans listeners.

- tests/test_new_business_rules.py::test_a06_insert_rejected_if_not_admitted
  - Ce que teste : règles métier qui rejettent mouvements A06 si patient non admis.
  - Cause d'échec : AttributeError sur `Patient.patient_seq` — modèles attendent un champ absent dans la définition actuelle.

- tests/test_auth_extended.py::TestPasswordHashing::test_get_password_hash
  - Ce que teste : génération et vérification de hash mot de passe.
  - Cause d'échec : `ValueError` de bcrypt car mot de passe fourni >72 bytes. Fixture/test doit être mis à jour ou la fonction de hash doit tronquer.

- tests/test_fhir_export_service.py::test_structure_export
  - Ce que teste : export FHIR d'une structure (Pole/Service...)
  - Cause d'échec : `Pole` n'a pas l'attribut `physical_type` attendu; modèle et exporteurs ne sont pas alignés.

- tests/test_pid_pv1_identifier_mapping.py::test_pid18_and_pv119_simple_values
  - Ce que teste : mapping d'identifiants depuis PID-18 et PV1-19.
  - Cause d'échec : l'endpoint d'admission a retourné `'error'` au lieu de `'success'`. Souvent lié à validateurs HL7 ou classification d'identifiants échouée.

- UI tests Playwright (ex. tests/ui/test_forms.py::test_navigation_menus)
  - Ce que teste : rendu et interactions UI.
  - Cause d'erreur : Playwright browser non installé sur l'environnement CI local.

---

## Recommandations prioritaires (plan d'actions)
Je propose le plan suivant, priorisé par impact minimal + isolation des causes :

1) Isolation rapide : **désactiver les listeners d'émission pendant les tests**
   - Raison : beaucoup d'erreurs critiques et d'InterfaceError proviennent du système d'émissions asynchrones qui lance des sessions en threads et interagit mal avec SQLite/tests. Les désactiver permet d'identifier facilement les échecs purement métiers.
   - Mise en oeuvre : ajouter une condition `if not settings.TESTING: register_entity_events()` ou centraliser un flag `DISABLE_EMISSIONS_IN_TESTS` dans `conftest.py`.
   - Effet attendu : réduit massivement les erreurs `InterfaceError`, `NULL identity key`, et flush/refresh problems.

2) Corriger les divergences de modèle (alias/propriétés)
   - Prioriser l'ajout d'aliases ou propriétés pour : `Patient.patient_seq`, `Venue.operational_status`, `Pole.physical_type`, champs `uf_medicale_*` sur `Mouvement`.
   - Effet : élimine beaucoup d'AttributeError et tests fonctionnels liés.

3) Ajuster hashing bcrypt
   - Options : (a) adapter tests pour fournir mots de passe <=72 bytes, (b) modifier la fonction de hash pour tronquer à 72 bytes (documenter ce choix).

4) Stabiliser la DB / flush logic
   - Éviter `session.commit()` ou `session.flush()` dans des handlers qui peuvent lancer des chargements (ou exécuter ces opérations en dehors des hooks). Réserver les IO/émissions asynchrones hors transaction.
   - Alternativement, exécuter la suite de tests avec une DB file-based (non in-memory) configurée pour accès multi-thread (si besoin).

5) Playwright et UI tests
   - Installer les browsers Playwright sur l’environnement CI ou marquer ces tests pour être exécutés uniquement sur CI adapté.

6) Nettoyage des DeprecationWarnings
   - Remplacer `datetime.utcnow()` par `datetime.now(timezone.utc)` et définir `cache_ok=True` sur TypeDecorator `_FlexibleDate` si compatible.

---

## Actions immédiates que je peux faire maintenant
Choisissez une ou plusieurs options :

- A : Appliquer un patch pour **désactiver les listeners d'émissions en test**, relancer la suite complète, et produire un nouveau rapport (liste des échecs restants) — recommandé comme première étape.
- B : Générer un rapport CSV/JSON exhaustif des 118 échecs (test, message d'erreur, résumé de stack) pour archivage.
- C : Commencer à corriger automatiquement les alias de modèle prioritaires (`patient_seq`, `operational_status`, `physical_type`) et relancer tests ciblés.
- D : Modifier la fonction de hash pour tronquer les mots de passe >72 bytes.

---

## Notes complémentaires
- J'ai déjà appliqué un correctif local pour `app/vocabulary_init.py` (exécution de `init_vocabulary_mappings` dans une nouvelle session) afin de réduire un SAWarning initial ; malgré cela d'autres SAWarning subsistent provenant d'autres modules (emit_on_create, scenario_template_init, etc.).
- Si vous souhaitez la liste complète test-par-test, je peux l’exporter en CSV/JSON et la placer à la racine (`tests_failures_report.csv`).

---

Fin du rapport initial. Indiquez quelle action prioritaire vous souhaitez que j’exécute (A/B/C/D ou autre) et je m’en occupe.
