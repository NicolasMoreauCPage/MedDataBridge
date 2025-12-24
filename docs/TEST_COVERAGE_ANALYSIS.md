# Documentation de Couverture des Tests - MedBridge Data

## État Actuel de la Couverture

**Couverture globale : 43%** (2,534 lignes couvertes sur 14,557 lignes totales)

### Résultats des Tests
- ✅ **129 tests réussis**
- ❌ **7 tests échoués**
- ⚠️ **1 test ignoré**
- ❌ **4 tests attendus en échec**
- 🚨 **183 erreurs** (principalement liées aux modèles de base de données)

## Modules Critiques avec Couverture Insuffisante

### Routers Non Testés (0% de couverture)

#### 1. `app/routers/patients.py` (0% - 7 lignes)
**Fonctionnalités non testées :**
- API REST de création de patients (`/api/patients`)
- Interface web de listing des patients
- Gestion du contexte GHT/EJ
- Création/modification via formulaires

**Tests manquants recommandés :**
```python
# tests/unit/test_patients_router.py
def test_api_create_patient_success(client, session):
    response = client.post("/api/patients", json={
        "family": "Doe", "given": "John", "birth_date": "1990-01-01"
    })
    assert response.status_code == 200

def test_list_patients_with_context(client, session):
    # Test avec contexte GHT/EJ
    pass

def test_patient_form_creation(client, session):
    # Test création via formulaire web
    pass
```

#### 2. `app/routers/context.py` (0% - 84 lignes)
**Fonctionnalités non testées :**
- Changement de contexte patient (`/patient/{id}`)
- Changement de contexte dossier (`/dossier/{id}`)
- Effacement de contexte (`/clear`)

**Tests manquants :**
```python
def test_set_patient_context(client, session):
    # Créer un patient et tester le changement de contexte
    pass

def test_clear_context(client, session):
    # Tester l'effacement de contexte
    pass
```

### Services Critiques Peu Testés

#### 3. `app/services/ucd_service.py` (22%)
**Fonctionnalités partiellement testées :**
- Création d'actes UCD
- Récupération par dossier
- Validation d'actes

**Tests manquants :**
- Gestion d'erreurs de validation
- Cas limites (valeurs nulles, formats invalides)
- Intégration avec la base de données

#### 4. `app/services/pam.py` (26% - 806 lignes)
**Module critique avec beaucoup de logique métier non testée :**
- Traitement des messages PAM I18N
- Validation de séquences
- Gestion des identifiants

## Problèmes Techniques Identifiés

### 1. Erreurs de Modèles de Base de Données
**Cause :** Incompatibilité entre les modèles SQLAlchemy et le schéma de base de données
```
KeyError: ('SELECT lppact.id, lppact.dossier_id, lppact...')
```

**Solution :** Synchroniser les modèles avec le schéma de base de données actuel.

### 2. Tests d'Interface Utilisateur
**Problème :** Les tests UI échouent car le serveur FastAPI ne démarre pas correctement
```
Server failed to start (timeout): [Errno 111]
```

**Solution :** Corriger la configuration de test pour les routes UI.

## Plan d'Amélioration de la Couverture

### Phase 1 : Tests Critiques (Priorité Haute)
1. **Corriger les erreurs de modèles DB** (183 erreurs)
2. **Tester les routers patients et context** (0% coverage)
3. **Ajouter tests pour services UCD/LPP** (16-22% coverage)

### Phase 2 : Tests de Services (Priorité Moyenne)
1. **Compléter la couverture de `pam.py`** (26% → 70%)
2. **Tester `scenario_status_service.py`** (8% → 60%)
3. **Ajouter tests pour `fhir_export.py`** (16% → 60%)

### Phase 3 : Tests Avancés (Priorité Basse)
1. **Tests d'intégration end-to-end**
2. **Tests de performance et charge**
3. **Tests de sécurité avancés**
4. **Tests de migration de données**

## Métriques Cibles

| Niveau | Couverture | Statut |
|--------|------------|--------|
| Minimum acceptable | 60% | ❌ Actuel: 43% |
| Bon niveau | 75% | 🎯 Objectif Phase 1 |
| Excellent | 85% | 🎯 Objectif Phase 2 |

## Recommandations Immédiates

### 1. Corriger les Erreurs de Base de Données
```bash
# Vérifier la cohérence des modèles
python -c "from app.models import *; print('Models loaded successfully')"

# Régénérer les migrations si nécessaire
alembic revision --autogenerate -m "Fix model inconsistencies"
```

### 2. Créer des Tests pour les Routers Non Testés
```python
# tests/unit/test_patients_router.py
import pytest
from fastapi.testclient import TestClient
from app.app import app

@pytest.fixture
def client():
    return TestClient(app)

def test_api_create_patient_success(client):
    response = client.post("/api/patients", json={
        "family": "Test", "given": "Patient", "birth_date": "1990-01-01"
    })
    assert response.status_code == 200
    assert "id" in response.json()
```

### 3. Améliorer la Configuration de Test
- Ajouter des fixtures pour la base de données de test
- Configurer correctement les mocks pour les services externes
- Séparer les tests unitaires des tests d'intégration

## Outils et Frameworks Recommandés

### Pour les Tests Unitaires
- `pytest` (déjà en place)
- `pytest-cov` pour la couverture (déjà configuré)
- `pytest-mock` pour les mocks

### Pour les Tests d'Intégration
- `pytest-asyncio` pour les tests async
- `httpx` pour les tests d'API externes
- `testcontainers` pour les tests avec bases de données

### Pour les Tests UI
- `selenium` ou `playwright` pour les tests end-to-end
- `pytest-playwright` pour l'intégration

## Conclusion

La couverture actuelle de 43% est insuffisante pour un projet de cette complexité. Les modules critiques comme les patients, le contexte, et les services UCD/LPP nécessitent une attention immédiate. L'objectif devrait être d'atteindre 75% de couverture dans les 3 prochains mois, en se concentrant d'abord sur la correction des erreurs existantes puis sur l'ajout de tests pour les fonctionnalités non couvertes.