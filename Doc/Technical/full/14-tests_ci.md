# Tests et intégration continue

Tests
- Unitaires : `pytest` (noms `test_*.py`).
- Intégration : dossiers `tests/messages/`, tests E2E Playwright pour UI.

Commandes utiles
```bash
# lancer les tests unitaires rapides
.venv/bin/python -m pytest tests/messages/test_emission_crud.py -q -k emit

# lancer un test ciblé
TESTING=1 .venv/bin/python -m pytest tests/messages/test_emission_crud.py::test_emit_identity_and_movements -q -vv -s
```

CI
- Le dépôt inclut workflows CI (vérifier `.github/workflows/` si présent) pour exécuter les tests et la validation statique.

Conseils
- Pour les modifications des validateurs, ajouter des tests de corpus qui montrent l'effet des allow-lists.
