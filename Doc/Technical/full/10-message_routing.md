# Routage des messages entrants

Composants
- `app/services/message_router.py` : décide du traitement selon le trigger / ZBE action (INSERT, UPDATE, CANCEL).
- `app/services/transport_inbound.py` : orchestration complète pour un message entrant (parse, validate, persist, route to services).

Logique
- Après parsing et validation, le routeur choisit : création d'identité, mise à jour patient, création de mouvement, annulation.
- Pour UPDATE/CANCEL, le routeur s'appuie sur `ZBE-6` (trigger original) et sur `MessageLog` pour retrouver la cible.

Gestion d'erreurs et compensation
- Les erreurs de persistance ou logique déclenchent des issues dans `MessageLog` et des callbacks de retry selon `scheduler`.
- Les annulations sont traitées de façon idempotente : vérifier existence et état avant application.

Observabilité
- `MessageLog` contient raw, trigger, zbe action, validation level, timestamp, et sujet (patient_id/dossier_id) pour faciliter debug.
