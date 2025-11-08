# Documentation Interne MedDataBridge

Ce répertoire `program_docs/` contient la documentation D'IMPLÉMENTATION interne. Les spécifications externes officielles (IHE PAM France, HL7 v2.5) restent dans `Doc/`.

## Structure

- `CORRECTION_PLAN.md` : Plan de conformité IHE PAM FR (segment ZBE, logique inbound/outbound, migrations).
- `README.md` : Ce fichier, vue générale.

## Conformité ZBE (IHE PAM FR)

Le segment ZBE est généré/parsé selon les règles :

- ZBE-1 identifiant principal + (TODO) répétitions futures
- ZBE-2 date/heure du mouvement (TS)
- ZBE-4 action : INSERT | UPDATE | CANCEL
- ZBE-5 historique : Y/N
- ZBE-6 trigger original requis si UPDATE/CANCEL
- ZBE-7 UF médicale XON (comp1 label, comp10 code)
- ZBE-8 UF soins XON (optionnel, warning si absent)
- ZBE-9 nature : {S,H,M,L,D,SM} dérivée via `services/nature_mapping.py`

## Flux Inbound UPDATE/CANCEL

- UPDATE/CANCEL : la présence de ZBE-1 + ZBE-6 est vérifiée; mouvement existant modifié ou annulé.
- Historique (ZBE-5=Y) accepté sans restriction temporelle additionnelle.

## PV1 Provenance (A02)

- PV1-6 reçoit l'UF précédente sur transfert A02 (issue du dernier mouvement de la venue).

## Tests

- `tests/test_zbe_segments.py` couvre génération INSERT, transfert A02 (PV1-6), UPDATE avec trigger original.
- À ajouter : CANCEL, historic Y, erreurs (ZBE-6 manquant sur UPDATE, nature invalide), warning absence ZBE-8.

## Compliance Matrix (En Construction)

Un fichier sera généré automatiquement listant chaque champ ZBE et statut (Pass/Partial/Missing) basé sur le validateur.

## Backward Compatibility

- Absence ZBE-8 génère un warning (et non une erreur) pour supporter anciens messages.

## Actions Prochaines

1. Étendre suite de tests.
2. Générer `COMPLIANCE_MATRIX.md`.
3. Micro-benchmark parsing/validation (N messages synthétiques) pour performance gate.

---
Documentation interne générée automatiquement.
