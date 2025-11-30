# Génération et émission HL7

Fichiers principaux

- `app/services/hl7_generator.py` : fonctions de génération HL7 (ADT) à partir des entités (Patient, Dossier, Mouvement).

- `app/services/emit_on_create.py` : hook/service qui émet un HL7 lors de la création d'un Mouvement si la configuration le demande.

- `app/services/structure_emit.py` : utilitaires pour mapping structure → champs HL7.

Flux d'émission

1. Une entité métier (Mouvement) est persistée.

2. `emit_on_create` construit un bundle de données (patient, dossier, pv1, zbe) et appelle `hl7_generator`.

3. Le message généré est validé via `pam_validation.validate_pam` (niveau pré-envoi).

4. Si validé (ou si politique autorise), `mllp` ou les transporteurs configurés envoient le message; `MessageLog` est mis à jour.

Points d'attention

- Toujours valider avant émission. Les erreurs de validation doivent être consignées et nécessitent revue avant mise en production.

- Les émissions automatiques (emit_on_create) peuvent être désactivées en configuration pour évitements de cycles.

Exemple d'usage

- Générer un ADT^A01 pour un `Mouvement`:

  - appeler `hl7_generator.build_message_for_mouvement(mouvement)` puis `mllp.send(raw_message, endpoint)`.
