# Résolution des problèmes & diagnostics

Quelques pistes rapides pour diagnostiquer les problèmes d'échange HL7/ FHIR.

## Connexion et réseau

- Vérifier que le port MLLP est ouvert et accessible depuis l'émetteur.
- Tester la latence et la perte de paquets si des timeouts apparaissent.

## Erreurs de format

- Valider le message HL7 via l'outil de validation intégré (/validation) ou via le module de validation HL7.
- Vérifier les encodages (UTF-8) et les séparateurs MSH.

## Logs et traces

- Activer MLLP_TRACE=1 pour capturer les échanges bas niveau.
- Consulter /metrics/dashboard et /debug pour les erreurs enregistrées.
