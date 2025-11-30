# Exploitation et procédures opérationnelles

Démarrage
- Utiliser la task VS Code fournie ou :
```bash
.venv/bin/python3 -m uvicorn app.app:app --reload
```

Logs & monitoring
- Logs structurés : `app/utils/structured_logging.py` ; surveiller `MessageLog` pour erreurs critiques.
- Metrics : endpoints métriques exposés (router `metrics.py`).

Gestion des exceptions
- Procédure pour accepter une exception produit :
  1. Collecter preuves avec `tools/validate_pam_examples.py`.
  2. Documenter justification et period d'application.
  3. Ajouter token dans `PID13_ALLOW_*` ou équivalent.
  4. Mettre à jour `.env`/config et re-déployer.

Backup & migration
- Alembic utilisé pour migrations ; sauvegarder DB avant migrations en prod.
