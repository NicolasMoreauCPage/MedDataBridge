# Audit Technique & Fonctionnel (Milestone Scénarios)

_Date: 2025-11-09_
_Branche courante: `refonte-uiux-2025`_

## 1. Synthèse
Le socle est stable: 218 tests passés, 1 skipped, 5 xfailed contrôlés. Aucune erreur bloquante restante après correction de la navigation (menu interop dupliqué). 351 warnings (deux grandes familles: Deprecation TemplateResponse + SAWarnings SQLAlchemy sur autflush/mappings). L'objectif prochain est l'enrichissement des **scénarios d'interop** pour tests de non-régression automatisés (dates réalistes, génération d'identifiants dédiée, capture d'un dossier réel, suivi des ACK).

## 2. Architecture applicative
- Backend: FastAPI + SQLModel (SQLAlchemy) avec couches services modulaire: `services/scenario_*`, `services/mllp`, `services/fhir_transport`.
- Modèles principaux: patients, dossiers, mouvements, endpoints, scénarios (`InteropScenario`, `InteropScenarioStep`, `ScenarioBinding`).
- Contexte multi-GHT & EJ via middleware (`ght_context`, `ej_context`, `dossier_context`).
- Interop: HL7 MLLP (envoi + parsing MSH), FHIR (bundle POST) ; identification adaptative (namespaces IPP/NDA/VENUE).
- Templates Jinja2 (navigation unifiée + gating contextuel) + tests UI (Playwright/HTTP client) avec attributs `data-test-*`.

## 3. Domaine & Couverture
| Domaine | Couvert | Détails |
|---------|---------|---------|
| Patients / Dossiers | Oui | Création, édition, fusion, validation, mouvements, venues |
| Structure / Entités | Oui | EG, Pôles, Services, UF, UH, Lits, Chambres (navigation conditionnelle) |
| Interop Messages | Oui | Envoi HL7/FHIR, validation HL7, scénarios steps, mapping PID/PV1 |
| Conformité IHE | Partiel | Accès conditionné GHT; tableau conformité (améliorations possibles) |
| Scénarios avancés | Partiel | Modèles présents, exécution existante (dates + identifiants), mais pas UI complète de capture/scénario replay ACK global |
| Monitoring ACK | Lacunaire | Logs présents (MessageLog) mais pas de tableau synthèse par dernier envoi/scénario |

## 4. État des Tests
- Total: 218 passés, 1 skipped, 5 xfailed (scénarios anciens ou fonctionnalités futures). 
- Catégories: identité, structure, interop HL7 (PIX/PDQ), UI navigation, scénarios (date updater).
- Besoin: nouveaux tests pour: capture dossier → scénario, preview identifiants, ACK dashboard agrégé.

## 5. Warnings & Dette Technique
### 5.1 DeprecationWarning TemplateResponse
Cause: utilisation ancienne signature `TemplateResponse(name, {"request": request})`.
Action: refactor progressif vers `TemplateResponse(request, name, context)`.
### 5.2 SAWarnings (autoflush VocabularyMapping)
Cause: objets non attachés au Session lors de relations `VocabularyValue.mappings`.
Action: audit du cycle de création mapping -> ajouter `session.add()` systématique ou disable autoflush local.
### 5.3 Volume warnings UI tests multiples
Cause: répétition des context initializers; possibilité de regrouper initialisation fixtures.

## 6. Opportunités d'Amélioration Prioritaires
1. Réduction warnings critiques (TemplateResponse + SAWarning) → fiabiliser future migration deps.
2. Scénarios: UI de création depuis dossier + prévisualisation identifiants → accélérer non-régression.
3. ACK Dashboard: agrégation par scénario & endpoint (statuts sent/error/skipped + délai moyen).
4. Indexation DB: ajouter index sur `MessageLog(status, endpoint_id, created_at)` pour dashboard.
5. Accessibilité & UX: ARIA landmarks sur pages admin & conformité; focus management menus.
6. Consolidation du paramétrage namespace identifiants (mapping clair IPP/NDA/VENUE + ranges).

## 7. Plan Milestone "Scénarios"
Étapes séquentielles (objectif 2 semaines):
1. Design date shifting (préserver intervalles) – fonction enrichie sur base `update_hl7_message_dates` (ajout cohérence relative admissions/transferts).
2. Namespace config (ranges + validation) – modèle config + interface admin.
3. Capture dossier → export scénario (messages historisés + génération JSON steps).
4. Preview identifiants avant envoi (service existant `preview_identifier_replacement` intégré UI).
5. Replay avec binding (déjà partiel) + paramètre step subset.
6. ACK dashboard – agrégation logs + statut résumé.
7. Tests: unité (transformations identifiants, date shifting avancé) + intégration (capture + replay + dashboard).
8. Documentation rapide (README section scénarios + guide opérateur).

## 8. Risques & Mitigations
| Risque | Impact | Mitigation |
|--------|--------|-----------|
| Complexité date shifting relative | Erreurs de cohérence temporelle | Ajout tests sur séquence A01→A02→A03 avec gaps vérifiés |
| Collisions identifiants test | Rejets récepteurs | Namespaces isolés + prefix override + tracking dernière exécution |
| Charge sur endpoints FHIR/MLLP | Lenteur tests non-régression | Mode "dry-run" (pas d'envoi) + throttling delay_seconds |
| Dashboard coût requête | Performance | Index composite + pagination + filtre période |

## 9. Refactors Immediats Proposés
- Signature TemplateResponse: migrer progressivement (script de refactor automatisé possible).
- Centraliser génération identifiants dans un service stateless; supprimer duplication dans runner.
- Extraire macros Jinja pour menus répétitifs (accessibilité + DRY).

## 10. Prochaines Actions (Conformes à todo list)
1. Dépréciations: inventaire complet usages TemplateResponse + plan de refactor.
2. Priorisation (doc dédiée) – corrélation valeur métier vs effort.
3. Implémentation scaffolding scénario (nouveaux fichiers services + endpoints stub).
4. Merge vers main puis branche milestone.

## 11. KPI Post-Milestone (Cibles)
| KPI | Actuel | Cible |
|-----|--------|-------|
| Warnings totaux | 351 | <120 |
| Tests scénarios spécifiques | ~5 | >15 |
| Temps exécution suite | 7m21s | <6m (optimisation fixtures) |
| Taux ACK "sent" sur replay standard | n/a | >95% |

---
_Fin du rapport initial._
