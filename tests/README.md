# Tests Directory

Ce répertoire contient tous les tests du projet MedDataBridge, organisés par type et portée.

## 📁 Structure

```text
tests/
├── unit/              # Tests unitaires (logique métier)
├── integration/       # Tests d'intégration (composants)
├── api/               # Tests API (endpoints FastAPI)
├── messages/          # Tests de messages (HL7, HPRIM)
├── scenarios/         # Tests de scénarios complets
├── fixtures/          # Données de test et fixtures
├── ui/                # Tests d'interface utilisateur
├── security/          # Tests de sécurité
├── performance/       # Tests de performance
└── e2e/               # Tests end-to-end
```

## 🧪 Types de tests

### 🔸 Tests unitaires (`unit/`)

Tests isolés des fonctions et classes individuelles :

- Logique métier pure
- Validation des données
- Utilitaires et helpers
- Parsers et formatters

### 🔸 Tests d'intégration (`integration/`)

Tests de l'interaction entre composants :

- Base de données
- Services externes
- APIs internes
- Workflows complets

### 🔸 Tests API (`api/`)

Tests des endpoints FastAPI :

- Routes et contrôleurs
- Validation des requêtes/réponses
- Authentification
- Gestion d'erreurs

### 🔸 Tests de messages (`messages/`)

Tests des formats HL7 et HPRIM :

- Parsing et génération
- Validation de conformité
- Roundtrip (génération → parsing)
- Gestion d'erreurs

### 🔸 Tests de scénarios (`scenarios/`)

Tests de cas d'usage complets :

- Workflows patient
- Intégration IHE PAM
- Scénarios métier

## 🚀 Exécution des tests

### Tous les tests

```bash
pytest
```

### Tests par catégorie

```bash
pytest tests/unit/          # Tests unitaires
pytest tests/integration/   # Tests d'intégration
pytest tests/api/           # Tests API
pytest tests/messages/      # Tests de messages
```

### Tests avec couverture

```bash
pytest --cov=app --cov-report=html
```

### Tests spécifiques

```bash
pytest tests/unit/test_patient_model.py -v
pytest tests/api/test_fhir_endpoints.py::test_create_patient -v
```

## 📊 Métriques de qualité

- **Couverture minimale** : 85%
- **Tests collectés** : 1000+
- **Durée maximale** : < 5 minutes en CI

## 🔧 Maintenance

### Ajouter un test

1. Choisir la catégorie appropriée
2. Nommer le fichier `test_*.py`
3. Utiliser les fixtures existantes
4. Documenter les cas limites

### Fixtures et données de test

- `fixtures/` : Données de test réutilisables
- `conftest.py` : Configuration pytest globale
- Utiliser `factory_boy` pour les objets complexes

## 📈 Performance

### Optimisations

- Tests parallèles en CI
- Cache des dépendances
- Isolation des tests (DB séparée)

### Métriques

- Temps d'exécution < 30s en local
- Utilisation mémoire < 500MB
- Pas de fuites de connexions

## 🐛 Debugging

### Tests qui échouent

```bash
pytest tests/unit/test_example.py -v -s --tb=long
```

### Profiling

```bash
pytest tests/performance/ --durations=10
```

## 🤝 Contribution

- Tous les tests doivent passer avant merge
- Couverture maintenue ou améliorée
- Tests documentés et lisibles
- Fixtures réutilisables
