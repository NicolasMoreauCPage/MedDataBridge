## 2025-11-29 — ZBE-9 validation strictness restored

The PAM validator's handling of ZBE-9 (nature of stay) has been reverted
to strict mode: non-standard or unknown values are now reported as errors
rather than warnings. This enforces conformance with local policy and
aligns behavior with production requirements.

Tests: message-level tests (`tests/messages`) were executed with
`TESTING=1` and all passed locally after the change.
# 

# Validation — résumé et usage

Ce fichier documente le validateur HL7 / IHE PAM implémenté dans
`app/services/pam_validation.py` et les outils associés.

## But

- Valider les messages ADT (HL7 v2.5) selon :

  - règles IHE PAM France (profil minimal),

  - structures HAPI locales (SEGMENT_RULES),

  - contrôles essentiels HL7 v2.5 (MSH, types de données, TS, XTN, CX, etc.).

## Niveaux et sortie

- Le validateur retourne un objet `ValidationResult` contenant :

  - `is_valid` (bool), `level` (`ok`|`warn`|`fail`), `event`, `message_type` et `issues` (liste de `ValidationIssue`).

  - Chaque `ValidationIssue` a : `code`, `message`, `severity` (`error`|`warn`|`info`).

## Variables d'environnement importantes

- `PID13_STRICT` (0|1) : si `1`, validation stricte des XTN en `PID-13` (par défaut dans le code : `1`).

- `PID13_ALLOW_USES` : CSV d'exceptions pour le composant Use (PID-13.3).

- `PID13_ALLOW_EQUIP` : CSV d'exceptions pour le composant Equipment (PID-13.4).

- `ENABLE_PAM_EXT` : active des extensions/compatibilités locales (optionnel).

- `STRICT_PAM_FR` : ajuste certaines règles locales (exclusion A08, etc.).

## Outils fournis

- `tools/extract_pid13_tokens.py` : extrait les tokens observés dans PID-13 du corpus d'exemples et écrit `tools/pid13_tokens.json`.

- `tools/validate_pam_examples.py` : exécute la validation sur le corpus `tests/exemples/Fichier_test_pam/` et produit un rapport JSON.

## Interprétation et bonnes pratiques

- Les issues `severity: "error"` sont des non-conformités à traiter (correction des émetteurs ou exception documentée).

- Pour les déviations de production massives (ex. `ZBE9_INVALID`) :

  - établir une liste d'exceptions limitée et documentée,

  - ou corriger la source des messages.

- Principe opérationnel : « les messages sont la vérité » — n'éditez
  les messages que si vous avez une preuve; préférer des exceptions auditées.

## Exemple minimal (bash)

```bash
export PID13_STRICT=1
export PID13_ALLOW_USES='PH,Internet,CP'
export PID13_ALLOW_EQUIP='PH,Internet,CP'
.venv/bin/python3 tools/validate_pam_examples.py
```

## Fichiers de sortie utiles (suite à `tools/validate_pam_examples.py`)

- rapport complet JSON (grand) — déplacer hors du dépôt si nécessaire (/tmp...).

- rapport filtré erreurs (ex: `/tmp/validate_pam_examples_report_errors.json`).

Voir aussi : `Doc/Technical/scenario_validation.md` pour la validation multi-message.

## 2025-11-29 — ZBE-9 validation strictness restored

- The PAM validator's handling of ZBE-9 (nature of stay) has been reverted
  to strict mode: non-standard or unknown values are now reported as errors
  rather than warnings. This enforces conformance with local policy and
  aligns behavior with production requirements.

- Tests: message-level tests (`tests/messages`) were executed with
  `TESTING=1` and all passed locally after the change.

Notes:

- If you run tests locally, use:

```bash
TESTING=1 .venv/bin/python -m pytest tests/messages -q -o log_cli=true
```

# Validation — résumé et usage

Ce fichier documente le validateur HL7 / IHE PAM implémenté dans
`app/services/pam_validation.py` et les outils associés.

But

- Valider les messages ADT (HL7 v2.5) selon :

  - règles IHE PAM France (profil minimal),

  - structures HAPI locales (SEGMENT_RULES),

  - contrôles essentiels HL7 v2.5 (MSH, types de données, TS, XTN, CX, etc.).

Niveaux et sortie

- Le validateur retourne un objet `ValidationResult` contenant :

  - `is_valid` (bool), `level` (`ok`|`warn`|`fail`), `event`, `message_type` et `issues` (liste de `ValidationIssue`).

- Chaque `ValidationIssue` a : `code`, `message`, `severity` (`error`|`warn`|`info`).

Variables d'environnement importantes

- `PID13_STRICT` (0|1) : si `1`, validation stricte des XTN en `PID-13` (par défaut dans le code : `1`).

- `PID13_ALLOW_USES` : CSV d'exceptions pour le composant Use (PID-13.3).

- `PID13_ALLOW_EQUIP` : CSV d'exceptions pour le composant Equipment (PID-13.4).

- `ENABLE_PAM_EXT` : active des extensions/compatibilités locales (optionnel).

- `STRICT_PAM_FR` : ajuste certaines règles locales (exclusion A08, etc.).

Outils fournis

- `tools/extract_pid13_tokens.py` : extrait les tokens observés dans PID-13 du corpus d'exemples et écrit `tools/pid13_tokens.json`.

- `tools/validate_pam_examples.py` : exécute la validation sur le corpus `tests/exemples/Fichier_test_pam/` et produit un rapport JSON.

Interprétation et bonnes pratiques

- Les issues `severity: "error"` sont des non-conformités à traiter (correction des émetteurs ou exception documentée).

- Pour les déviations de production massives (ex. `ZBE9_INVALID`) :

  - établir une liste d'exceptions limitée et documentée,

  - ou corriger la source des messages.

- Principe opérationnel : « les messages sont la vérité » — n'éditez
  les messages que si vous avez une preuve; préférer des exceptions auditées.

Exemple minimal (bash)
```bash
export PID13_STRICT=1
export PID13_ALLOW_USES='PH,Internet,CP'
export PID13_ALLOW_EQUIP='PH,Internet,CP'
.venv/bin/python3 tools/validate_pam_examples.py
```

Fichiers de sortie utiles (suite à `tools/validate_pam_examples.py`)

- rapport complet JSON (grand) — déplacer hors du dépôt si nécessaire (/tmp/...).

- rapport filtré erreurs (ex: `/tmp/validate_pam_examples_report_errors.json`).

Voir aussi : `Doc/Technical/scenario_validation.md` pour la validation multi-message.
