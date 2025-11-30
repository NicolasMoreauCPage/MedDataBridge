# Architecture MedData Bridge — synthèse

Vue d'ensemble
- Application backend : FastAPI + SQLModel
- Objectif : gérer l'interopérabilité HL7 v2.5 (IHE PAM France) et FHIR R4

Modules clés
- `app/services/pam_validation.py` : validateur HL7 / IHE PAM (segments, datatypes, ZBE)
- `app/services/scenario_validation.py` : validation multi-message / workflow
- `app/state_transitions.py` : règles de transitions autorisées (INITIAL_EVENTS, ALLOWED_TRANSITIONS)
- `app/services/emit_on_create.py` / `app/services/hl7_generator.py` : génération et émission HL7
- `app/models_*` : entités Patient / Dossier / Venue / Mouvement / MessageLog

Flux simplifié
- Inbound : MLLP / fichier → parsing MSH/PID/PV1/ZBE → validation PAM → persistance (MessageLog, Mouvement)
- Outbound : génération HL7 → validation → transport (MLLP/File)

Tests et outils
- Tests : pytest (+ Playwright pour UI)
- Outils : `tools/validate_pam_examples.py`, `tools/extract_pid13_tokens.py`

Conformité IHE PAM
- Support des segments ZBE (ZBE-1..ZBE-9), actions INSERT/UPDATE/CANCEL
- Validation de datatypes essentiels (CX, XTN, TS, XPN, XAD)

Notes
- Documentation détaillée et spécifications externes sont dans `/Doc`.
