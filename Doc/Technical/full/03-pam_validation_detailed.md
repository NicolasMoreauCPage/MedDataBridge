# Détail : `app/services/pam_validation.py`

But
- Vérifier la conformité des messages ADT HL7 v2.5 aux règles IHE PAM France,
  complétées par des contrôles HL7 v2.5 essentiels.

Entrée / Sortie
- Entrée : texte HL7 (chaîne) représentant un message ADT (doit commencer par `MSH|`).
- Sortie : instance `ValidationResult` avec :
  - `is_valid` (bool), `level` (`ok`|`warn`|`fail`), `event` (trigger), `message_type` et `issues` (liste de `ValidationIssue`).
- `ValidationIssue` : `{code, message, severity}` où `severity` ∈ {`error`, `warn`, `info`}.

Configuration via variables d'environnement
- `PID13_STRICT` (0|1) : active la validation stricte des XTN en `PID-13` (par défaut dans le code : `1`).
- `PID13_ALLOW_USES` : CSV d'exceptions pour PID-13.3 (Use Code).
- `PID13_ALLOW_EQUIP` : CSV d'exceptions pour PID-13.4 (Equipment Type).
- `ENABLE_PAM_EXT` : active extensions locales.
- `STRICT_PAM_FR` : ajustements pour règles locales FR.

Contrôles principaux
1. MSH (entête)
   - MSH-1 doit être `|` (sinon `MSH1_INVALID`, severity `error`).
   - MSH-2 (encoding) recommandé `^~\&` (warning si non standard).
   - MSH-9 format `type^trigger[^structure]` (erreur si absent).
   - MSH-10 (Message Control ID) requis.
2. EVN
   - Présence d'EVN (sinon `EVN_MISSING`).
   - Cohérence EVN-1 vs MSH-9 (warn si discordant).
   - Validation TS pour EVN-2 / EVN-6.
3. PID
   - PID-3 (Patient Identifier) doit exister ; chaque répétition CX est validée (`PID3_EMPTY`, `PID3[...]_CX_ID_EMPTY`).
   - PID-5 (Patient Name) recommandé (warn si absent) ; XPN minimal check.
   - PID-7 (DOB) validation TS.
   - PID-11 (adresse) : XAD minimal.
   - PID-13 / PID-14 (XTN) : validation via `_validate_xtn_telecom` (voir infra).
4. PV1 / Séjours
   - PV1 requis pour événements séjour (liste REQUIRE_PV1) sinon `PV1_MISSING`.
   - PV1-2 (Patient Class) validée (warn si valeur non reconnue).
   - PV1-19 (Visit Number) validé comme CX.
5. Segments selon trigger (SEGMENT_RULES)
   - Vérifie présence des segments requis et signale segments optionnels présents (info `OPTIONAL_SEGMENTS`) ou manquants (error `SEG_MISSING`).
   - Vérifie l'ordre attendu des segments (warn `SEGMENT_ORDER_X`).
6. ZBE (extension IHE PAM FR)
   - ZBE-1 identifiant mouvement : namespace requis (`ZBE1_NAMESPACE_MISSING`).
   - ZBE-2 timestamp (format) (`ZBE2_FORMAT`).
   - ZBE-4 action : doit être `INSERT|UPDATE|CANCEL` (`ZBE4_MISSING`/`ZBE4_INVALID`).
   - ZBE-5 historic flag : `Y`/`N` (`ZBE5_MISSING`/`ZBE5_INVALID`).
   - ZBE-6 original trigger requis pour UPDATE/CANCEL (`ZBE6_REQUIRED`).
   - ZBE-7 (UF médicale) : composant 10 code requis (`ZBE7_CODE_MISSING`).
   - ZBE-8 (UF soins) : warn si absent, code composant 10 check (`ZBE8_CODE_MISSING`).
   - ZBE-9 nature : accepte standard `S,H,M,L,D,SM`; les tokens composites produits en
     production (ex: `MH`, `HM`, `MH-EXT`) sont normalisés puis marqués `ZBE9_INVALID` (severity `error` dans la configuration actuelle) — ce comportement peut être assoupli via processus d'exception documentée.

Validation XTN (PID-13)
- Format XTN supporté : `[CountryCode]^TelephoneNumber^TelecomUse^TelecomEquipType^...`.
- Politique par défaut : strict pour PID-13 si `PID13_STRICT=1`.
  - Use Code validés contre un ensemble permissif (`ASN, BPN, EMR, NET, ORN, PRN, PRS, VHN, WPN, PH, CP`).
  - Equipment Type validés contre `BP, CP, FX, Internet, MD, PH, SAT, TDD, TTY, X.400`.
  - Les valeurs non reconnues déclenchent `PID13[...]_XTN_USE_INVALID` ou `PID13[...]_XTN_EQUIP_INVALID` (severity `error` en mode strict).
- Exceptions : ajouter des tokens dans `PID13_ALLOW_USES` / `PID13_ALLOW_EQUIP`.

Détermination du niveau global
- `level` calculé : `fail` si au moins une issue `error`, sinon `warn` si au moins un `warn`, sinon `ok`.
- `is_valid` = `not has_error`.

Outils d'exploitation
- Exécuter la validation sur un message : utiliser la fonction `validate_pam(msg, direction='in', profile='IHE_PAM_FR')` (importable depuis `app.services.pam_validation`).
- Batch corpus : `tools/validate_pam_examples.py` produit un rapport JSON; filtrer/archiver ensuite.
- Extraction tokens PID-13 : `tools/extract_pid13_tokens.py` produit `tools/pid13_tokens.json` pour décider des allow-lists.

Procédure recommandée pour anomalies massives
1. Exécuter `tools/validate_pam_examples.py` sur le corpus de production/échantillon.
2. Regrouper par code d'issue (ZBE9_INVALID souvent dominant) et par valeur observée.
3. Pour PID-13 : examiner `tools/pid13_tokens.json`, décider d'une allow-list restreinte et testée.
4. Documenter chaque exception (motif, date, responsable) et l'ajouter au `.env`/configuration.
5. Revalider le corpus et tracer la diminution des erreurs.

Codes d'issue notables (exemples)
- MSH1_INVALID, MSH9_FORMAT, MSH10_EMPTY, MSH11_INVALID
- EVN_MISSING, EVN_MISMATCH
- PID3_EMPTY, PID5_MISSING, PID7_TS_*
- PV1_MISSING, PV1_2_MISSING, PV1_2_INVALID
- ZBE1_NAMESPACE_MISSING, ZBE2_FORMAT, ZBE4_MISSING, ZBE4_INVALID, ZBE5_MISSING, ZBE5_INVALID, ZBE6_REQUIRED, ZBE7_CODE_MISSING, ZBE8_CODE_MISSING, ZBE8_ABSENT, ZBE9_MISSING, ZBE9_INVALID
- PID13[0]_XTN_USE_INVALID, PID13[0]_XTN_EQUIP_INVALID

Annexe : exemples rapides
- Lancer un check interactif (python REPL)
```python
from app.services.pam_validation import validate_pam
msg = open('tests/exemples/Fichier_test_pam/sample1.hl7').read()
res = validate_pam(msg)
print(res.level)
for i in res.issues:
    print(i.code, i.severity, i.message)
```

Fin du document détaillé.`
