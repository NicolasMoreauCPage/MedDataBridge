# Roundtrip de scénario PAM + HPRIM entre deux GHT

Date : 12 septembre 2026

## Verdict

**Succès.** Un jeu de scénario mixte a été émis depuis le GHT A, puis intégré
dans deux bases SQLite isolées représentant le GHT A et le GHT B. Les
projections métier persistées sont strictement identiques.

## Environnements

```text
GHT A / BDD A ── scénario ADT^A01 + HPRIM CCAM ──> dépôts FILE isolés
       │                                                    │
       ├── réintégration PAM + HPRIM dans BDD A             │
       └──────────────────── mêmes payloads ────────────────┤
                                                            ▼
                                                  GHT B / BDD B
```

Chaque BDD possède son propre GHT et les mêmes espaces d’identifiants IPP,
NDA et VN. Le test ne partage ni moteur SQLAlchemy ni fichier SQLite entre les
deux environnements.

## Scénario exécuté

| Étape | Protocole | Résultat |
|---|---|---|
| Admission patient | IHE PAM `ADT^A01` | émission et intégration réussies |
| Acte | HPRIM XML CCAM `ZZQK900` | émission, validation et persistance réussies |

Le jeu est routé vers deux endpoints FILE/HPRIM de la cible logique `GHT-B`.
Les identifiants générés sont figés dans le jeu, cohérents entre PAM et HPRIM,
et restent distincts du jeu suivant.

## Comparaison BDD

La comparaison vérifie des valeurs métier plutôt que les identifiants internes
SQLite :

- identité patient et IPP ;
- NDA de dossier ;
- code et UF de venue ;
- acte HPRIM : patient, type, code, action et projection JSON.

Les deux empreintes métier sont égales après réintégration.

## Écarts détectés et corrigés

1. Le parseur ADT n’acceptait que `CR`; la lecture FILE normalisait les fins de
   ligne en `LF`. Il accepte désormais les deux séparateurs.
2. L’import ADT créait un identifiant NDA sans le type obligatoire `NDA`.
3. L’identifiant HPRIM réutilisait le contrôle HL7 libre (`PLAY-…`), non
   conforme au format HPRIM. Un identifiant HPRIM alphanumérique dédié est
   désormais généré par étape.

## Reproductibilité

```bash
TESTING=1 PYTHONPATH=. .venv/bin/pytest -q \
  tests/integration/test_two_ght_scenario_roundtrip.py
```

Le test est également inclus dans la CI `interop-conformance.yml`.
