# Vue d'ensemble des services métiers

Principe

- Les services sont des modules Python sous `app/services/` ; ils implémentent la logique métier et sont conçus pour être réutilisables par les routeurs et les runners.

Services clés (résumé)

- `pam_validation.py` : validation de message (voir doc détaillée).

- `scenario_validation.py` : validation multi-message (workflow/cohérence).

- `hl7_generator.py` : génération de messages HL7 à partir d'entités (Patient, Mouvement).

- `emit_on_create.py` : wrapper qui émet automatiquement un HL7 lors de la création d'un Mouvement si configuré.

- `message_router.py` : oriente les messages entrants vers le bon handler (creation, update, cancel).

- `transport_inbound.py` : orchestration de la réception d'un message (parsing, validation, persistance, routing métier).

- `dossiers_service.py`, `patients_service.py`, `venues_service.py` : CRUD métier pour entités PAM.

- `identifier_*` : génération et classification d'identifiants (namespaces).

- `mfn_*` : gestion des messages MFN (vocabulaire / structure MFN).

Tests internes

- Chaque service a des tests unitaires (références dans `tests/`), et les services critiques (validation, transport) ont des tests d'intégration.

Conseil d'exploitation

- Ne pas appeler `pam_validation` pour modifier un message ; utiliser son output (issues) pour décision manuelle/automatique encadrée.
