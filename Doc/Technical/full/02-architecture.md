# Architecture — vue synthétique

Composants principaux
- FastAPI (application) : point d'entrée HTTP, endpoints administratifs et UI.
- Services métiers : modules sous `app/services/` (validation, parsing, emission, routing).
- Parsing HL7 : répertoire `app/infrastructure/hl7/parsing/` (segments PID, PV1, ZBE, ...).
- Transport : MLLP (`app/services/mllp.py`), file poller, HTTP/FHIR transport.
- Persistance : SQLModel/SQLAlchemy (modèles Patient, Dossier, Venue, Mouvement, MessageLog).
- Outils batch : `tools/validate_pam_examples.py`, extracteurs, scripts d'analyse.

Flux principal
- Inbound : transport → parsing (MSH/PID/PV1/ZBE) → validation PAM → persistance / MessageLog → traitement métier (création Mouvement/Dossier)
- Outbound : génération HL7 → validation → transport (MLLP/File) → mise à jour MessageLog

Séparation des responsabilités
- `pam_validation.py` : responsabilité de conformité (renvoie issues, n'applique
  pas de corrections automatiques).
- `scenario_validation.py` : validateur multi-message (workflow, cohérence patient/visit).
- `state_transitions.py` : autorise / interdit les transitions entre événements ADT.

Exploitation
- Logs structurés (structured logging) et MessageLog pour traçabilité complète.
- Rapports de validation batch produits par `tools/validate_pam_examples.py`.
