# Gestion des identifiants et namespaces

Fichiers
- `app/services/identifier_generator.py` : génération séquentielle des identifiants locaux.
- `app/services/identifier_namespace_classifier.py` : classification et routage selon namespace.
- `app/models_identifiers.py` : modèles Namespace, Identifier.

Principes
- Les identifiants sont qualifiés par namespace (ex: HOSP, EXTERN). Le code veille à l'unicité par namespace.
- Les règles de génération peuvent être paramétrées (préfixes, séquences) — voir `Doc/identifier_prefixes.md`.

Interop
- Lorsque le système reçoit des identifiants externes (PID-3 avec assigning authority), ils sont stockés et utilisés pour rechercher/joindre des patients.
- Les conflits déclenchent des workflows de fusion (`patient_merge.py`) et éventuellement des requêtes PIX/PDQ si configurées.
