# Matrice des capacités interopérables

Cette matrice est le contrat de produit courant. Elle ne constitue pas une
certification par un organisme tiers : chaque ligne « qualifiée » renvoie à des
tests automatisés et doit être complétée par une recette avec le partenaire
avant une mise en service.

Vérifiée le 26 septembre 2026. Propriétaire : équipe Interopérabilité.

| Domaine | Capacité | Statut | Preuve / comportement |
|---|---|---|---|
| IHE PAM France | ADT de mouvement et identité, dont A01, A02, A03, A04, A05, A06, A07, A11, A12, A13, A21, A22, A23, A28, A31, A40, A47, A52, A53 | Qualifié sur le corpus | Tests IHE PAM France/CPage et roundtrip CI. |
| IHE PAM France | ADT A08 | Conditionnel | Disponible hors mode PAM FR strict ; refusé explicitement lorsque `STRICT_PAM_FR` ou l'EJ l'impose. |
| HPRIM XML 2.4 | Actes CCAM, NGAP, UCD et LPP | Qualifié sur le périmètre testé | Validation XSD, émission, import et acquittements testés en CI. |
| HPRIM XML 2.4 | État patient, frais divers, PMSI | Non pris en charge | Non exposé comme capacité livrée. L'ancienne sortie vide d'état patient est refusée explicitement. |
| CCAM | Format, activité, phase, quantité et modificateurs HPRIM | Qualifié techniquement | Contrôles structurels HPRIM. |
| CCAM | Existence dans le référentiel officiel et règles tarifaires opposables | Non pris en charge | Aucun référentiel officiel versionné n'est embarqué ; ne pas utiliser l'outil comme moteur de facturation. |
| HL7 v2.5 | MFN^M05 de structure | Qualifié sur le périmètre testé | Import/export et roundtrip de structure dans la CI. |
| FHIR R4 / FR Core 2.2.0 | Structure et relations de structure | Qualifié sur le périmètre testé | Tests FR Core, import/export et idempotence dans la CI. |
| Transport | Outbox persistante, reprises et rejets | Qualifié sur le périmètre testé | Tests `outbox` et reprise FHIR dans la CI. |

## Règle de mise en service partenaire

Avant d'activer une capacité pour un logiciel connecté, exécuter la campagne
de conformité correspondante décrite dans [TESTS_STATUS.md](TESTS_STATUS.md),
archiver les traces anonymisées dans les artefacts CI, puis ajouter le résultat
et les éventuels écarts dans le rapport de qualification du partenaire.

Une capacité « conditionnelle » ou « non prise en charge » doit rester visible
dans les échanges avec le partenaire ; elle ne doit pas être contournée par un
paramétrage local.
