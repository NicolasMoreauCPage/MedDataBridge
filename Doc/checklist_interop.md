# Checklist de qualification d'interopérabilité

Ce document fournit une checklist rapide pour valider une intégration d'échange HL7 / FHIR avec un système tiers.

## Avant les tests

- Vérifier connectivité réseau (ports MLLP, HTTPS)
- Synchroniser les namespaces et identifiants (OID, systèmes d'identifiants)
- Partager les valeurs de configuration (FINESS, codes GHT/EJ, endpoints)

## Tests fonctionnels recommandés

- Envoi d'un ADT^A01 (admission) et vérification de la création patient
- Envoi d'un MFN pour synchroniser une nomenclature et vérifier l'intégration
- Export FHIR : GET /fhir/Patient/{id} et comparaison des attributs

## Critères d'acceptation

- Tous les messages atteignent l'endpoint et reçoivent un ACK (ou NAK documenté)
- Les identifiants patients sont mappés correctement
- Les erreurs et rejets sont documentés et reproductibles

## Diagnostics

- Activer les logs MLLP (MLLP_TRACE=1) pour capturer les échanges
- Utiliser les endpoints internes de diagnostic (/debug, /metrics)
