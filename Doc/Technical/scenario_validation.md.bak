# Validation de scénarios (app/services/scenario_validation.py)

Ce document décrit le validateur de scénario qui opère sur un texte contenant
une ou plusieurs messages HL7 v2.5 (séparés par des lignes ou commençant par `MSH|`).

Comportement principal
- Le texte est découpé en messages en repérant chaque ligne commençant par `MSH|`.
- Pour chaque message :
  - `validate_pam(message, direction, profile)` est exécuté (validation message).
  - On extrait : event code (MSH-9.2 ou EVN-1), patient id (PID-3.1), visit id (PV1-19.1), timestamp (EVN-2 ou MSH-7).
  - Un `MessageValidationResult` est construit et ajouté au résultat.
- Contrôles workflow :
  - le premier message doit être un événement de démarrage (`INITIAL_EVENTS`).
  - chaque transition est testée via `app.state_transitions.is_valid_transition(previous_event, event_code)`; en cas d'échec on ajoute un issue `WORKFLOW_INVALID_TRANSITION` (severity `error`).
- Vérifications de cohérence globales :
  - unicité des identifiants patient (erreur si >1, warn si aucun),
  - unicité/consistance du visit id (warn si multiples),
  - ordre chronologique des timestamps (warn si désordonné).

Types clés
- `MessageValidationResult` : numéro, texte, `ValidationResult` (pam), message_type, event_code, patient_id, visit_id, timestamp.
- `ScenarioValidationResult` : `is_valid`, `level` (`ok`|`warn`|`error`), listes d'issues workflow/cohérence.

Stratégie de reporting
- Issues workflow : `WORKFLOW_INVALID_INITIAL`, `WORKFLOW_INVALID_TRANSITION` (severity `error`).
- Issues de cohérence : `SCENARIO_MULTIPLE_PATIENTS`, `SCENARIO_NO_PATIENT`, `SCENARIO_MULTIPLE_VISITS`, `SCENARIO_TIMESTAMP_ORDER`.
- Les issues messages proviennent de `validate_pam` et sont agrégées.

Limitations
- Parsing HL7 simple (split par lignes et `|`/`^`). Les échappements/encodages HL7 avancés
  ne sont pas traités par ce validateur.
- Le validateur n'effectue pas de résolution d'identités avancée (matching multi-sources).

Voir aussi : `app/state_transitions.py` pour le graphe des transitions autorisées.
