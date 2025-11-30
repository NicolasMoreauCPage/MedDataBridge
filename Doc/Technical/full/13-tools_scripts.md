# Outils et scripts

Outils présents
- `tools/validate_pam_examples.py` : exécute la validation sur le corpus d'exemples et produit un rapport JSON.
- `tools/extract_pid13_tokens.py` : extrait tokens observés en PID-13 pour alimenter allow-lists.
- `generate_jwt_token.py` : ouvriers pour tests d'API.
- `init_db.py`, `init_vocabulary_mappings.py` : scripts d'initialisation.

Usage recommandé
- Exécuter `tools/validate_pam_examples.py` en environnement isolé et archiver le rapport hors dépôt (ex: `/tmp/validate_pam_examples_report.json`).
- Utiliser `extract_pid13_tokens.py` pour proposer valeurs `PID13_ALLOW_*`.
