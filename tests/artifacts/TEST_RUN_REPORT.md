- tests/integration/test_hprim_xml_roundtrip.py : **ECHEC** (1 test, 0/1 passé, 12 warnings)
	- AssertionError: 404 == 200 lors de l'appel POST /roundtrip-hprim/generate

- tests/integration/test_phase3b_seed_subset.py : **OK** (1 test, 1/1 passé, 5 warnings)
#
- tests/integration/test_hprim_xml_roundtrip.py : **ECHEC** (1 test, 0/1 passé, 12 warnings)
	- AssertionError: 404 == 200 lors de l'appel POST /roundtrip-hprim/generate
- tests/conftest.py : **Aucun test détecté** (0/0)

- tests/__init__.py : **OK** (1 test, 1/1 passé, 12 warnings)
- `test_dossier_cotations_flags_update` (tests/test_hprim_cotations.py) : **OK** (12 warnings)
	- PydanticDeprecatedSince20: validators et config à migrer vers Pydantic V2.
	- SAWarning: Object of type <VocabularyMapping> not in session, add operation along 'VocabularyValue.mappings' will not proceed.

---

Tests non exécutés (non détectés comme tests par pytest) :
- `test_patient` (tests/conftest.py) : **IGNORÉ** (fonction non détectée comme test exécutable)
- `test_dossier` (tests/conftest.py) : **IGNORÉ** (fonction non détectée comme test exécutable)
- `test_endpoints_fixture` (tests/conftest.py) : **IGNORÉ** (fonction non détectée comme test exécutable)
- `test_acquittement_processing` (tests/test_hprim_cotations.py) : **OK** (12 warnings)
	- PydanticDeprecatedSince20: validators et config à migrer vers Pydantic V2.
	- SAWarning: Object of type <VocabularyMapping> not in session, add operation along 'VocabularyValue.mappings' will not proceed.

- `test_dossier_cotations_flags_update` (tests/test_hprim_cotations.py) : **OK** (12 warnings)
	- PydanticDeprecatedSince20: validators et config à migrer vers Pydantic V2.
	- SAWarning: Object of type <VocabularyMapping> not in session, add operation along 'VocabularyValue.mappings' will not proceed.
- `test_cotations_count_with_cotations` (tests/test_hprim_cotations.py) : **OK** (12 warnings)
	- PydanticDeprecatedSince20: validators et config à migrer vers Pydantic V2.
	- SAWarning: Object of type <VocabularyMapping> not in session, add operation along 'VocabularyValue.mappings' will not proceed.

	- `test_acquittement_processing` (tests/test_hprim_cotations.py) : **OK** (12 warnings)
		- PydanticDeprecatedSince20: validators et config à migrer vers Pydantic V2.
		- SAWarning: Object of type <VocabularyMapping> not in session, add operation along 'VocabularyValue.mappings' will not proceed.
# Résumé de l'exécution pytest

## Audit d'exécutabilité des fichiers de tests (2026-01-10)

- tests/test_admin_ej_route.py : **OK** (1 test, 1/1 passé, 12 warnings)
- tests/test_extended_seed_isolated.py : **OK** (1 test, 1/1 passé, 4 warnings)
- tests/test_hprim_cotations.py : **OK** (4 tests, 4/4 passés, 15 warnings)
- tests/test_hprim_xsd_validation.py : **OK** (1 test, 1/1 passé, 4 warnings)
- tests/conftest.py : **Aucun test détecté** (0/0)

Tous les fichiers standards de tests/ sont exécutables et passent, seuls des warnings Pydantic ou SQLModel sont présents.

Date: 2026-01-10

Fichier log: tests/artifacts/full_pytest_run_after_changes.log

## Exécution individuelle des tests (2026-01-10)

- `test_hprim_xsd_validation_evenements` (tests/test_hprim_xsd_validation.py) : **OK** (4 warnings)
	- PydanticDeprecatedSince20: Support for class-based `config` est déprécié, utiliser ConfigDict.
	- SAWarning: Object of type <VocabularyMapping> not in session, add operation along 'VocabularyValue.mappings' will not proceed.
- `test_multi_ej_extended_seed_isolated` (tests/test_extended_seed_isolated.py) : **OK** (4 warnings)
	- PydanticDeprecatedSince20: Support for class-based `config` est déprécié, utiliser ConfigDict.
	- SAWarning: Object of type <VocabularyMapping> not in session, add operation along 'VocabularyValue.mappings' will not proceed.
- `test_ej_detail_route_basic` (tests/test_admin_ej_route.py) : **ERREUR**
	- ModuleNotFoundError: No module named 'openpyxl'
	- 4 warnings (PydanticDeprecatedSince20, SAWarning)
- `test_cotations_count_no_cotations` (tests/test_hprim_cotations.py) : **OK** (12 warnings)
	- PydanticDeprecatedSince20: validators et config à migrer vers Pydantic V2.
	- SAWarning: Object of type <VocabularyMapping> not in session, add operation along 'VocabularyValue.mappings' will not proceed.
- `test_cotations_count_with_cotations` (tests/test_hprim_cotations.py) : **OK** (12 warnings)
	- PydanticDeprecatedSince20: validators et config à migrer vers Pydantic V2.
	- SAWarning: Object of type <VocabularyMapping> not in session, add operation along 'VocabularyValue.mappings' will not proceed.

- `test_hprim_generation` (tests/integration/test_hprim_generation.py) : **OK** (4 warnings)

Prochaine étape : exécuter les autres tests un par un et compléter ce rapport.
# Résumé de l'exécution pytest

Date: 2026-01-09

Fichier log: tests/artifacts/full_pytest_run_after_changes.log

Résumé:
- Durée approximative: ~21 minutes
- Résultat: 136 failed, 595 passed, 38 skipped, 4 xfailed, 62 errors, ~1054 warnings

Principales catégories d'erreurs détectées:
- Erreurs d'intégrité DB (IntegrityError) lors de l'insertion d'actes `lppact` (NOT NULL constraint failed: montant_unitaire_facture_ttc).
- Tests API UCD/LPP renvoyant 400/500 sur create/get/update/delete d'actes.
- Tests générés (CRUD) retournant 500s pour certaines routes (venues, mouvements).
- Tests d'intégration workflow (dossier/patient) échouent pour des raisons liées à l'état de la DB ou seeds manquantes.
- Tests Metrics/Tasks/Configuration échouent probablement à cause du démarrage des services de fond durant les tests.
- Nombreux warnings et erreurs async (coroutine not awaited, no current event loop) — indicatif de services async démarrés en dehors du contexte pytest.

Recommandations prioritaires (ordre d'intervention):
1. Empêcher le démarrage des services de fond pendant les tests (MLLP, scheduler, file polling, runners). Cela réduira les side-effects, les problèmes d'event loop et les erreurs d'état inattendues.
2. Reproduire les erreurs d'IntegrityError sur `lppact` en lançant les tests ciblés puis corriger la création d'actes (valeurs par défaut, fixtures de seed, validation côté tests).
3. Corriger les fixtures async / event loop: s'assurer que `pytest-asyncio` est utilisé correctement et que aucun background loop n'est démarré automatiquement.
4. Ré-exécuter les sous-ensembles de tests (UCD/LPP API, generated CRUD) pour itérer sur les corrections.
5. Pour les E2E avec Playwright: exécuter en CI où les navigateurs sont préinstallés, ou corriger l'environnement système local (apt/GPG) pour permettre `playwright install --with-deps`.

Actions réalisées maintenant:
- Ajout de ce rapport (tests/artifacts/TEST_RUN_REPORT.md).
- Ajout d'un guard pour empêcher le démarrage des services de fond pendant les tests (modifications de `app/app.py` et `app/services/scheduler.py`).


## Exécution individuelle des tests (2026-01-10)

- `test_hprim_xsd_validation_evenements` (tests/test_hprim_xsd_validation.py) : **OK** (4 warnings)
	- PydanticDeprecatedSince20: Support for class-based `config` est déprécié, utiliser ConfigDict.
	- SAWarning: Object of type <VocabularyMapping> not in session, add operation along 'VocabularyValue.mappings' will not proceed.

- `test_hprim_generation` (tests/integration/test_hprim_generation.py) : **OK** (4 warnings)

- `test_roundtrip_ultra_simple` (tests/integration/test_roundtrip_ultra_simple.py) : **IGNORÉ** (2 tests, 2/2 skipped, 7 warnings)
- `test_fixtures_example` (tests/integration/test_fixtures_example.py) : **OK** (3 tests, 3/3 passés, 14 warnings)
- `test_hprim_validation` (tests/integration/test_hprim_validation.py) : **Aucun test détecté** (0/0, 3 warnings)
- `test_duplicate_fix` (tests/integration/test_duplicate_fix.py) : **IGNORÉ** (1 test, 1/1 skipped, 5 warnings)
- `test_legacy_import` (tests/integration/test_legacy_import.py) : **OK** (9 tests, 8/9 passés, 1 ignoré, 233 warnings)
- `test_real_roundtrip` (tests/integration/test_real_roundtrip.py) : **Aucun test détecté** (0/0, 3 warnings)
- `test_realistic_timing_demo` (tests/integration/test_realistic_timing_demo.py) : **OK** (2 tests, 2/2 passés, 5 warnings)
- `test_data_migration` (tests/integration/test_data_migration.py) : **OK** (14 tests, 14/14 passés, 122 warnings)
- `test_all_hprim_scenarios` (tests/integration/test_all_hprim_scenarios.py) : **IGNORÉ** (1 test, 1/1 skipped, 3 warnings)
- `test_dossier_workflow` (tests/integration/test_dossier_workflow.py) : **ECHEC** (1 test, 0/1 passé, 7 warnings)
	- ValidationError: Field 'when' manquant dans MouvementCreateSchema lors de la création du mouvement (voir https://errors.pydantic.dev/2.8/v/missing)
- `test_mllp_server` (tests/integration/test_mllp_server.py) : **Aucun test détecté** (0/0)
- `test_phase1_validator` (tests/integration/test_phase1_validator.py) : **Aucun test détecté** (0/0)
- `test_scenarios_roundtrip` (tests/integration/test_scenarios_roundtrip.py) : **Aucun test détecté** (0/0, 3 warnings)
- `test_roundtrip_simple` (tests/integration/test_roundtrip_simple.py) : **ERREUR** (1 test, 1 ignoré, 1 erreur, 6 warnings)
	- fixture 'scenario_name' introuvable pour test_roundtrip_scenario
- `test_realistic_timeplan` (tests/integration/test_realistic_timeplan.py) : **OK** (27 tests, 27/27 passés, 30 warnings)
- `test_phase3_seed_integration` (tests/integration/test_phase3_seed_integration.py) : **ECHEC** (3 tests, 2/3 passés, 1 échec, 8 warnings)
	- AttributeError: 'HL7ImportValidator' object has no attribute 'validate_message' dans test_validator_functionality
- `test_new_features_integration` (tests/integration/test_new_features_integration.py) : **ECHEC** (1 test, 0/1 passé, 12 warnings)
	- AssertionError: 'uptime_seconds' non présent dans la réponse de l'endpoint /metrics
- `test_api_endpoints` (tests/ui/test_api_endpoints.py) : **OK** (6 tests, 6/6 passés, 20 warnings)
- `test_ui_ucd_lpp` (tests/ui/test_ui_ucd_lpp.py) : **ECHEC** (1 test, 0/1 passé, 12 warnings)
	- AssertionError: 404 == 200 lors de l'appel GET /ucd/
- `test_ui_components` (tests/ui/test_ui_components.py) : **OK** (3 tests, 3/3 passés, 6 warnings)
- `test_ui_smoke` (tests/ui/test_ui_smoke.py) : **OK** (1 test, 1/1 passé, 5 warnings)
- `test_ui_pages` (tests/ui/test_ui_pages.py) : **ECHEC** (5 tests, 4/5 passés, 1 échec, 16 warnings)
	- AssertionError: la page /api/docs ne contient pas 'API' ou 'Gestion structure' malgré le code 200
- `test_ui_ajax_endpoints` (tests/ui/test_ui_ajax_endpoints.py) : **OK** (4 tests, 4/4 passés, 15 warnings)
- `test_ui_cotation_modern` (tests/ui/test_ui_cotation_modern.py) : **ECHEC** (3 tests, 2/3 passés, 1 échec, 18 warnings)
	- AssertionError: /cotation-modern/ retourne 200 au lieu d'un code de redirection (302 ou 307)
- `test_forms_temp` (tests/ui/test_forms_temp.py) : **IGNORÉ** (1 test, 1/1 skipped)
- `test_patient_management_ui` (tests/ui/test_patient_management_ui.py) : **OK** (14 tests, 14/14 passés, 67 warnings)
- `test_inheritance_api` (tests/unit/test_inheritance_api.py) : **OK** (5 tests, 5/5 passés, 8 warnings)
- `test_identifier_oid` (tests/unit/test_identifier_oid.py) : **IGNORÉ** (1 test, 1/1 skipped, 5 warnings)

Prochaine étape : exécuter les autres tests un par un et compléter ce rapport.
