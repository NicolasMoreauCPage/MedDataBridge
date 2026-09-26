# Index des rapports de qualification

Les fichiers de ce répertoire sont des preuves et des instantanés datés. Ils
ne sont pas des spécifications : les référentiels externes, le code et les
tests automatisés prévalent.

Mis à jour le 25 septembre 2026. Propriétaire : équipe Qualité.

## Rapports de référence courants

| Domaine | Rapport | État | Propriétaire | Vérifié le |
|---|---|---|---|---|
| IHE PAM France / CPage | [AUDIT_CONFORMITE_IHE_PAM_FRANCE_20260911.md](AUDIT_CONFORMITE_IHE_PAM_FRANCE_20260911.md) | Audit technique corrigé, non équivalent à une certification IHE | Interopérabilité PAM | 24 septembre 2026 |
| Roundtrip PAM CPage | [ROUNDTRIP_CPAGE_PAM_20260911.md](ROUNDTRIP_CPAGE_PAM_20260911.md) | Validé sur le corpus et les deux BDD de qualification | Interopérabilité PAM | 24 septembre 2026 |
| Roundtrip scénario PAM + HPRIM | [ROUNDTRIP_SCENARIO_DEUX_GHT_20260912.md](ROUNDTRIP_SCENARIO_DEUX_GHT_20260912.md) | Deux GHT/BDD isolés, projections métier comparées | Qualification | 24 septembre 2026 |
| Roundtrip catalogue complet | [ROUNDTRIP_CATALOGUE_SCENARIOS_DEUX_GHT_20260912.md](ROUNDTRIP_CATALOGUE_SCENARIOS_DEUX_GHT_20260912.md) | 219 scénarios, résultats et écarts par scénario | Qualification | 24 septembre 2026 |
| HPRIM, MFN, FHIR, outbox | [PLAN_AMELIORATIONS_INTEROPERABILITE_20260911.md](PLAN_AMELIORATIONS_INTEROPERABILITE_20260911.md) | État consolidé et limites restantes | Interopérabilité | 24 septembre 2026 |
| Scénarios durables | [IMPLEMENTATION_QUALIFICATION_DURABLE_20260912.md](IMPLEMENTATION_QUALIFICATION_DURABLE_20260912.md) | Outbox, versions, assertions et campagnes | Qualification | 24 septembre 2026 |
| Reprise historique PAM/HPRIM | [COUVERTURE_REPRISE_SCENARIOS_PAM_HPRIM_20260912.md](COUVERTURE_REPRISE_SCENARIOS_PAM_HPRIM_20260912.md) | Couverture du catalogue et limites de recette | Qualification | 24 septembre 2026 |
| Scénarios multi-protocoles | [PLAN_SCENARIOS_MULTI_PROTOCOLES_20260912.md](PLAN_SCENARIOS_MULTI_PROTOCOLES_20260912.md) | Plan livré, historique | Interopérabilité | 24 septembre 2026 |
| Qualification scénarios PAM/HPRIM | [PLAN_QUALIFICATION_SCENARIOS_PAM_HPRIM_20260912.md](PLAN_QUALIFICATION_SCENARIOS_PAM_HPRIM_20260912.md) | Socle livré ; enrichissement partenaire continu | Qualification partenaires | 24 septembre 2026 |
| FHIR France / FR Core | [VERIFICATION_FHIR_FRANCE_FR_CORE_2_2_0_20260912.md](VERIFICATION_FHIR_FRANCE_FR_CORE_2_2_0_20260912.md) | Compatible sur le périmètre Structure testé | Interopérabilité FHIR | 24 septembre 2026 |
| Audit produit et mise en œuvre | [AUDIT_CODE_INDEPENDANT_20260926.md](AUDIT_CODE_INDEPENDANT_20260926.md) | Audit indépendant et suivi des corrections | Équipe produit | 26 septembre 2026 |

## Lecture des rapports historiques

- Les autres fichiers `AUDIT`, `ANALYSIS`, `PLAN`, `PROGRESS`, `SESSION`,
  `SUMMARY`, `TODO` et `REPORT` expliquent un état à leur date de rédaction.
- Un écart marqué comme corrigé dans un rapport récent ne doit pas être rouvert
  uniquement parce qu'il apparaît dans une ancienne analyse.
- Une limite encore ouverte est explicitement consignée dans le rapport de
  référence correspondant ; elle ne doit pas être masquée par une conclusion
  ancienne ou générale.

Les règles de classement complètes sont dans
[../DOCUMENTATION_STATUS.md](../DOCUMENTATION_STATUS.md).
