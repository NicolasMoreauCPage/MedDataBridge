# État des Tests - MedData Bridge

Date: 9 janvier 2026

## ✅ Tests Fonctionnels (8/8 passés)

### Tests HPRIM
- `test_hprim_cotations.py` (4 tests) ✅
  - test_cotations_count_no_cotations
  - test_cotations_count_with_cotations  
  - test_acquittement_processing
  - test_dossier_cotations_flags_update

- `test_hprim_xsd_validation.py` (1 test) ✅
  - test_hprim_xsd_validation_evenements

### Tests Admin
- `test_admin_ej_route.py` (1 test) ✅
  - test_ej_detail_route_basic

### Tests Models  
- `test_models.py::TestNGAPAct` (2 tests) ✅
  - test_ngap_act_creation_minimal
  - test_ngap_act_creation_complete

## ⚠️ Tests Nécessitant des Corrections

### Tests API - Obsolètes (Architecture changée)
- `tests/api/test_api_ucd_lpp.py` (10 tests) ❌
  - **Problème**: Tests utilisent TestClient avec routers isolés
  - **Solution**: Réécrire avec app complète ou intégration
  - **Priorité**: Basse (fonctionnalité testée ailleurs)

### Tests Models - Champs obsolètes
- `test_models.py::TestUCDAct` (2 tests) ❌
  - **Problème**: Utilise `code_cip` au lieu de `code_ucd`
  - **Problème**: Utilise `designation` au lieu de `denomination_libelle`
  - **Problème**: Champs obsolètes (prix_unitaire, montant_total, facturable, valide, facture)
  - **Solution**: Adapter aux nouveaux champs du modèle UCDAct

- `test_models.py::TestLPPAct` (2 tests) ❌
  - **Problème**: Utilise `libelle` au lieu de `denomination_libelle`  
  - **Problème**: Utilise `prix_unitaire` au lieu de `montant_unitaire_facture_ttc`
  - **Problème**: Champs obsolètes (montant_total, facturable, valide, facture)
  - **Solution**: Adapter aux nouveaux champs du modèle LPPAct

- `test_models.py::TestCCAMAct` (2 tests) ⚠️
  - À vérifier après UCD/LPP

### Tests UI - Multiples problèmes
- Nombreux tests UI avec codes 404/405/500
- **Cause**: Routes changées, mocks obsolètes  
- **Priorité**: Moyenne (UI fonctionnelle en dev)

### Tests E2E - Event loop  
- Tests e2e/phase5/phase6 avec erreurs async
- **Cause**: Playwright fixtures non compatibles
- **Priorité**: Basse (tests manuels OK)

### Tests Performance - Event loop
- Tests avec "RuntimeError: This event loop is already running"
- **Cause**: Conflits async/await dans tests
- **Priorité**: Basse (performance OK en prod)

## 📊 Statistique Globale

- **Tests fonctionnels**: 8
- **Tests à corriger (priorité haute)**: ~4-6 (models UCD/LPP/CCAM)
- **Tests obsolètes à réécrire**: ~10 (API routers)
- **Tests non critiques**: ~50+ (UI, E2E, Performance)

## 🎯 Plan d'Action

### Court terme (Priorité 1)
1. ✅ NGAP models tests - FAIT
2. ⏳ UCD models tests - Adapter champs
3. ⏳ LPP models tests - Adapter champs  
4. ⏳ CCAM models tests - Vérifier

### Moyen terme (Priorité 2)
5. Réécrire tests API UCD/LPP avec app complète
6. Corriger fixtures Playwright pour E2E
7. Résoudre conflicts event loop

### Long terme (Priorité 3)
8. Tests UI complets
9. Tests performance stabilisés
10. Coverage > 80%

## 📝 Notes

### Changements d'Architecture Récents
- Schémas UCD/LPP simplifiés (code unique au lieu de multiples)
- Models alignés sur HPRIM XML v2.4
- Suppression champs métier obsolètes (facturable, valide, facture pour UCD/LPP)
- `facture` devient string "oui"/"non"/"trd"/"ec" pour NGAP au lieu de boolean

### Recommandations
- Prioriser tests fonctionnels core (HPRIM, models, API principales)
- Tests UI peuvent être manuels temporairement
- E2E et Performance à long terme
- Maintenir coverage des fonctionnalités critiques

