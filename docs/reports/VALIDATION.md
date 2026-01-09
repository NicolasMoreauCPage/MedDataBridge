# Validation rules and how to run them

Ce dépôt contient un validateur HL7/IHE PAM (`app/services/pam_validation.py`) configurable via variables d'environnement.

Variables importantes

- `PID13_STRICT`=0|1 : si 1, la validation de `PID-13` (XTN) est stricte et produit des erreurs pour des Use/Equipment non conformes.

- `PID13_ALLOW_USES` : liste CSV d'exceptions pour le composant Use (PID-13.3).

- `PID13_ALLOW_EQUIP` : liste CSV d'exceptions pour le composant Equipment (PID-13.4).

Fichiers utilitaires

- `tools/extract_pid13_tokens.py` : parcourt `tests/exemples/Fichier_test_pam/` et liste les tokens observés (écrit `tools/pid13_tokens.json`).

- `tools/validate_pam_examples.py` : exécute la validation sur le corpus d'exemples et écrit un rapport JSON.

Exemples d'utilisation

Activer le mode strict et fournir les allow-lists :

```bash
export PID13_STRICT=1
export PID13_ALLOW_USES='PH,Internet,CP'
export PID13_ALLOW_EQUIP='mineheure@free.fr,p.moreau@free.fr,mailperso@perso.fr,Victoria@gmail.com'
```

Lancer la validation batch et produire le rapport :

```bash
.venv/bin/python3 tools/validate_pam_examples.py
```

Interprétation des résultats

- Les issues ayant `severity="error"` correspondent à des non-conformités par rapport aux règles IHE PAM (les messages doivent être corrigés en production ou listés comme exceptions dans les allow-lists).

Notes
 
- Par défaut (fichier `.env.example`) une allow-list basée sur le corpus d'exemples est fournie ; adaptez-la avant d'activer strictement en production.
