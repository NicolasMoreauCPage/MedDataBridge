# 🚀 Plan d'Amélioration de la Couverture des Tests

## 📊 État Initial
- **Couverture actuelle : 47%** (10,786/25,343 lignes)
- **129 tests réussis**, **183 erreurs** (principalement modèles DB)
- **Objectif global : 75%** de couverture d'ici 3 mois

---

## 🔥 PHASE 1 : Correction des Erreurs et Tests Critiques (1-2 semaines) ✅ **COMPLETED**
**Objectif : 60% de couverture globale**

### 1.1 🔧 Correction des Erreurs de Base de Données (Priorité CRITIQUE) ✅ **DONE**
- [x] **Corriger les 183 erreurs KeyError** sur les modèles SQLAlchemy ✅ **DONE**
  - [x] Identifier les tables/modèles problématiques (lppact, ucdact, etc.) ✅ **DONE**
  - [x] Vérifier la cohérence entre modèles et schéma DB ✅ **DONE**
  - [x] Régénérer les migrations Alembic si nécessaire ✅ **DONE**
  - [x] Tester : `python -c "from app.models import *; print('OK')"` ✅ **DONE**
- [x] **Résoudre les erreurs de serveur UI** (timeout sur les tests UI) ✅ **DONE**
  - [x] Vérifier la configuration FastAPI pour les tests ✅ **DONE**
  - [x] Corriger les dépendances de session manquantes ✅ **DONE**

### 1.2 🧪 Tests des Routers Critiques (0% coverage) ✅ **DONE**
- [x] **Créer `tests/unit/test_patients_router.py`** ✅ **DONE**
  - [x] Test API REST `/api/patients` (création patient) ✅ **DONE**
  - [x] Test interface web `/patients` (listing avec contexte) ✅ **DONE**
  - [x] Test création/modification via formulaires ✅ **DONE**
  - [x] Test gestion d'erreurs et validation ✅ **DONE**
- [x] **Créer `tests/unit/test_context_router.py`** ✅ **DONE**
  - [x] Test `/patient/{id}` (changement contexte patient) ✅ **DONE**
  - [x] Test `/dossier/{id}` (changement contexte dossier) ✅ **DONE**
  - [x] Test `/clear` (effacement contexte) ✅ **DONE**
  - [x] Test redirection et gestion d'erreurs ✅ **DONE**

### 1.3 🏗️ Infrastructure de Test ✅ **DONE**
- [x] **Configurer les fixtures de test communes** ✅ **DONE**
  - [x] Créer `tests/conftest.py` avec fixtures DB ✅ **DONE**
  - [x] Ajouter fixture `authenticated_client` pour tests UI ✅ **DONE**
  - [x] Configurer mocks pour services externes ✅ **DONE**
- [x] **Séparer tests unitaires et d'intégration** ✅ **DONE**
  - [x] Créer dossier `tests/integration/` pour tests lourds ✅ **DONE**
  - [x] Marquer les tests lents avec `@pytest.mark.slow` ✅ **DONE**

### 1.4 ✅ Validation Phase 1 ✅ **DONE**
- [x] **Couverture ≥ 60%** globale ✅ **DONE**
- [x] **0 erreurs** sur les modèles DB ✅ **DONE**
- [x] **Tous les routers critiques** testés (patients, context) ✅ **DONE**
- [x] **Tests passent** sans erreurs de configuration ✅ **DONE**

---

## 🚀 PHASE 2 : Services et Fonctionnalités Métier (2-4 semaines)
**Objectif : 75% de couverture globale**

### 2.1 🔄 Services UCD/LPP (16-22% coverage) ✅ **COMPLETED**
- [x] **Compléter `tests/unit/test_ucd_service.py`** ✅ **DONE**
  - [x] Test création actes UCD avec validation ✅ **DONE**
  - [x] Test récupération par dossier/patient ✅ **DONE**
  - [x] Test mise à jour et suppression ✅ **DONE**
  - [x] Test cas d'erreur (valeurs invalides, contraintes) ✅ **DONE**
- [x] **Compléter `tests/unit/test_lpp_service.py`** ✅ **DONE**
  - [x] Test création actes LPP ✅ **DONE**
  - [x] Test logique métier spécifique LPP ✅ **DONE**
  - [x] Test intégration avec dossiers ✅ **DONE**
- [x] **Créer tests d'intégration UCD/LPP** ✅ **DONE**
  - [x] Test workflow complet création → validation → stockage ✅ **DONE**
  - [x] **API Tests UCD/LPP** : 10/10 tests passent (5 UCD + 5 LPP) ✅ **DONE**

### 2.2 📤 Export/Import FHIR (16-26% coverage) ✅ **COMPLETED**
- [x] **Compléter `tests/unit/test_fhir_export.py`** ✅ **DONE**
  - [x] Test export structure FHIR ✅ **DONE**
  - [x] Test export patients FHIR ✅ **DONE**
  - [x] Test export complet (all) FHIR ✅ **DONE**
  - [x] Test gestion erreurs (EJ non trouvée) ✅ **DONE**
- [x] **Compléter `tests/unit/test_fhir_import.py`** ✅ **DONE**
  - [x] Test import bundle FHIR ✅ **DONE**
  - [x] Test validation bundle FHIR ✅ **DONE**
  - [x] Test gestion erreurs (format invalide, EJ inexistante) ✅ **DONE**
  - [x] **API Tests FHIR** : 10/10 tests passent (5 export + 5 import) ✅ **DONE**

### 2.3 🏥 Services Médicaux Critiques ✅ **COMPLETED**
- [x] **Créer `tests/unit/test_pam_service.py`** (26% → 70%) ✅ **DONE**
  - [x] Test validation timing mouvements ✅ **DONE**
  - [x] Test parsing segments HL7 (PV1, ZBE) ✅ **DONE**
  - [x] Test traitement messages PAM ADT ✅ **DONE**
  - [x] Test génération messages PAM ✅ **DONE**
- [x] **Créer `tests/unit/test_scenario_status_service.py`** (8% → 60%) ✅ **DONE**
  - [x] Test propriétés classes ScenarioStatus ✅ **DONE**
  - [x] Test récupération statut scénarios ✅ **DONE**
  - [x] Test agrégation par EJ ✅ **DONE**
  - [x] Test validation scénarios multi-étapes ✅ **DONE**

### 2.4 🌐 Routers Métier ✅ **COMPLETED**
- [x] **Créer `tests/unit/test_namespaces_router.py`** (7% → 60%) ✅ **DONE**
  - [x] Test gestion vocabulaires médicaux ✅ **DONE**
  - [x] Test résolution identifiants ✅ **DONE**
  - [x] Test création/modification namespaces ✅ **DONE**
  - [x] Test validation et erreurs ✅ **DONE**
- [x] **Créer `tests/unit/test_ngap_router.py`** (19% → 60%) ✅ **DONE**
  - [x] Test API NGAP ✅ **DONE**
  - [x] Test validation données NGAP ✅ **DONE**
  - [x] Test dashboard et formulaires ✅ **DONE**
  - [x] Test création actes NGAP ✅ **DONE**

### 2.5 ✅ Validation Phase 2 ✅ **COMPLETED**
- [x] **Couverture ≥ 75%** globale (62 tests unitaires créés) ✅ **DONE**
- [x] **Services UCD/LPP** complètement testés ✅ **DONE**
- [x] **Export/Import FHIR** fonctionnel ✅ **DONE**
- [x] **Tous services médicaux critiques** couverts ✅ **DONE**
- [x] **Routers métier** (namespaces, NGAP) testés ✅ **DONE**

---

## 🏆 PHASE 3 : Tests Avancés et Qualité (1-2 mois) 🚀 **IN PROGRESS**
**Objectif : 85% de couverture globale**

### 3.1 🔗 Tests d'Intégration End-to-End ✅ **COMPLETED**
- [x] **Créer `tests/integration/test_patient_workflow.py`** ✅ **DONE**
  - [x] Test workflow complet : création → actes → export ✅ **DONE**
  - [x] Test intégration avec tous services ✅ **DONE**
- [x] **Créer `tests/integration/test_dossier_workflow.py`** ✅ **DONE**
  - [x] Test gestion dossier médical complet ✅ **DONE**
  - [x] Test transitions états et validations ✅ **DONE**
- [x] **Créer `tests/integration/test_fhir_interop.py`** ✅ **DONE**
  - [x] Test échange FHIR avec systèmes externes ✅ **DONE**
  - [x] Test conformité profils FHIR ✅ **DONE**

### 3.2 ⚡ Tests de Performance 🚀 **STARTING**
- [x] **Créer `tests/performance/test_ucd_lpp_performance.py`** (améliorer existant) ✅ **DONE**
  - [x] Test charge élevée (1000+ actes) ✅ **DONE**
  - [x] Test mémoire et CPU ✅ **DONE**
  - [x] Test temps de réponse ✅ **DONE**
- [x] **Créer `tests/performance/test_fhir_performance.py`** ✅ **DONE**
  - [x] Test export/import gros volumes ✅ **DONE**
  - [x] Test performance requêtes complexes ✅ **DONE**

### 3.3 🔒 Tests de Sécurité ✅ **COMPLETED**
- [x] **Créer `tests/security/test_input_validation.py`** ✅ **DONE**
  - [x] Test injection SQL prévention ✅ **DONE**
  - [x] Test XSS prévention ✅ **DONE**
  - [x] Test path traversal prévention ✅ **DONE**
- [x] **Créer `tests/security/test_authentication.py`** ✅ **DONE**
  - [x] Test contrôles d'accès ✅ **DONE**
  - [x] Test rate limiting (simulé) ✅ **DONE**
  - [x] Test gestion sessions ✅ **DONE**

### 3.4 🔄 Tests de Migration et Données
- [ ] **Créer `tests/integration/test_data_migration.py`**
  - [ ] Test migration schémas DB
  - [ ] Test transformation données existantes
- [ ] **Créer `tests/integration/test_legacy_import.py`**
  - [ ] Test import données legacy
  - [ ] Test validation et nettoyage

### 3.5 🎨 Tests d'Interface Utilisateur
- [ ] **Créer `tests/ui/test_patient_management_ui.py`**
  - [ ] Test formulaires création/édition patients
  - [ ] Test navigation et contexte
- [ ] **Créer `tests/ui/test_dossier_management_ui.py`**
  - [ ] Test interface gestion dossiers
  - [ ] Test workflow médical UI

### 3.6 🤖 Tests Automatisés et CI/CD
- [ ] **Configurer tests parallèles** pour accélérer CI
- [ ] **Ajouter tests de mutation** (mutmut)
- [ ] **Créer rapports couverture automatiques**
- [ ] **Intégrer tests dans pipeline CI/CD**

### 3.7 ✅ Validation Phase 3
- [ ] **Couverture ≥ 85%** globale
- [ ] **Tests end-to-end** complets et fonctionnels
- [ ] **Performance** validée pour cas d'usage réels
- [ ] **Sécurité** testée et validée
- [ ] **Interface utilisateur** testée
- [ ] **CI/CD** avec tests automatiques

---

## 📈 Métriques de Suivi

### Hebdomadaire
- [ ] Exécuter `python coverage_tracker.py`
- [ ] Vérifier progression couverture
- [ ] Identifier nouveaux gaps critiques

### Quotidien
- [ ] Tests passent en local (`pytest`)
- [ ] Pas de régression sur fonctionnalités existantes
- [ ] Code review des nouveaux tests

## 🛠️ Outils et Dépendances

### À Installer
```bash
pip install pytest-mock pytest-asyncio testcontainers mutmut
```

### Configuration pytest
```ini
# pytest.ini
addopts = --cov=app --cov-report=html --cov-fail-under=60 -v
markers = unit, integration, ui, slow, security, performance
```

## 📋 Checklist Générale

- [ ] **Code Coverage** : métriques automatisées
- [ ] **Test Quality** : pas de tests triviaux, couverture des edge cases
- [ ] **Performance** : tests ne ralentissent pas le développement
- [ ] **Maintainability** : tests faciles à comprendre et modifier
- [ ] **CI/CD Integration** : tests automatiques dans le pipeline

---

## 🎯 Priorisation des Tâches

1. **CRITIQUE** : Erreurs empêchant les tests de tourner
2. **HAUTE** : Fonctionnalités métier critiques non testées
3. **MOYENNE** : Améliorations et edge cases
4. **BASSE** : Optimisations et fonctionnalités avancées

**Rappel** : Commencer par la Phase 1 pour établir une base solide !