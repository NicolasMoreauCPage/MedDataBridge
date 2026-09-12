# Documentation MedData Bridge

Cette page est le point d'entrée de la documentation maintenue. Les documents
datés, plans, audits et comptes rendus restent disponibles pour la traçabilité,
mais ne décrivent pas nécessairement l'état courant.

## Références à utiliser

| Sujet | Référence | Statut |
|---|---|---|
| Démarrage, architecture et exploitation | [PROGRAM_DOCUMENTATION.md](PROGRAM_DOCUMENTATION.md) | Référence générale |
| IHE PAM France / CPage | [rapport d'audit PAM](reports/AUDIT_CONFORMITE_IHE_PAM_FRANCE_20260911.md) et [roundtrip CPage](reports/ROUNDTRIP_CPAGE_PAM_20260911.md) | Périmètre validé techniquement |
| HPRIM XML | [plan et état d'avancement](reports/PLAN_AMELIORATIONS_INTEROPERABILITE_20260911.md) | CCAM, NGAP, UCD et LPP couverts par tests ciblés |
| MFN Structure | [plan d'interopérabilité](reports/PLAN_AMELIORATIONS_INTEROPERABILITE_20260911.md) et [mémo MFN](MFN_INTEGRATION_COMPLETE_FR.md) | Périmètre courant puis détail historique |
| FHIR France / FR Core | [vérification FR Core 2.2.0](reports/VERIFICATION_FHIR_FRANCE_FR_CORE_2_2_0_20260912.md) | Référence d'échange de structure |
| API FHIR `Location` | [API_FHIR_STRUCTURE.md](API_FHIR_STRUCTURE.md) | API IHM historique, pas le contrat partenaire FR Core |
| Outbox persistante | [OUTBOX.md](OUTBOX.md) | Référence d'exploitation |
| Tests et CI | [TESTS_STATUS.md](TESTS_STATUS.md) | Commandes et périmètre de preuve |
| Guide utilisateur | [user_guide.md](user_guide.md) | Parcours IHM et procédures d'exploitation |
| Scénarios multi-protocoles | [plan back/front](reports/PLAN_SCENARIOS_MULTI_PROTOCOLES_20260912.md) | Évolutions nécessaires pour un jeu cohérent et multi-endpoints |
| Qualification scénarios PAM/HPRIM | [plan de reprise de l'ancien outil](reports/PLAN_QUALIFICATION_SCENARIOS_PAM_HPRIM_20260912.md) | Catalogue, statuts par cible, rejeu, assertions et campagnes |
| Rapports | [reports/README_FOR_REPORTS.md](reports/README_FOR_REPORTS.md) | Index et statut des rapports |

## Règles de lecture et de maintenance

- Le code et les tests automatisés font foi lorsqu'ils contredisent un document
  non daté ou antérieur à septembre 2026.
- Un fichier portant une date, `AUDIT`, `PLAN`, `TODO`, `SPRINT`, `PHASE` ou
  `REPORT` est un instantané : il ne doit pas être utilisé seul comme contrat
  d'intégration.
- Les documents de `archive/`, `Technical/full/` et les anciens comptes rendus
  sont conservés pour expliquer les décisions passées. Les nouvelles décisions
  doivent référencer la présente page et le rapport courant du protocole.
- Toute modification d'un protocole doit mettre à jour son test de roundtrip,
  son rapport de référence et, si nécessaire, cette table.

## Standards couverts

- IHE PAM France (ITI-30 et ITI-31), fondé sur HL7 v2.5 ;
- HL7 MFN^M05 pour la structure ;
- HPRIM XML pour les actes CCAM, NGAP, UCD et LPP ;
- FHIR R4 / FR Core pour les échanges de structure.

Le détail du classement des documents et des fichiers historiques est dans
[DOCUMENTATION_STATUS.md](DOCUMENTATION_STATUS.md).
