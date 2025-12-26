# Organisation du projet MedData Bridge

## Structure des dossiers

### 📁 `scripts/`
Scripts utilitaires et outils de développement
- `maintenance/` : Scripts de maintenance base de données et migrations
- `analysis/` : Scripts d'analyse et diagnostic

### 📁 `docs/`
Documentation du projet
- `reports/` : Rapports de validation, analyses et résultats de tests

### 📁 `logs/`
Fichiers de logs et sorties de tests
- `full_test_run*.log` : Logs complets des exécutions de tests
- `test_run_output.txt` : Sorties de tests diverses

### 📁 `temp/`
Fichiers temporaires et de développement
- Bases de données temporaires (`*.db`, `*.db-*`)
- Scripts de test temporaires (`test_*.py`)
- Données de test (`scenarios_seed_data.json`)
- Logs temporaires

### 📁 `tools/`
Outils et utilitaires (réservé pour usage futur)

## Fichiers à la racine

Seuls les fichiers de configuration essentiels restent à la racine :
- Fichiers de configuration (`.env*`, `pyproject.toml`, `requirements*.txt`)
- Fichiers git (`.git*`, `.gitignore`)
- README principal
- Cache et environnements de développement (`.pytest_cache/`, `.venv/`, etc.)

## Bonnes pratiques

- Les nouveaux scripts de maintenance vont dans `scripts/maintenance/`
- Les nouveaux scripts d'analyse vont dans `scripts/analysis/`
- Les rapports et logs vont dans `docs/reports/` et `logs/`
- Les fichiers temporaires vont dans `temp/`
- Garder la racine propre et lisible