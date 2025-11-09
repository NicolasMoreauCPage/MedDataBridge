# Scénarios Templates Contextualisables

## 📋 Vue d'ensemble

Cette feature permet de stocker des **scénarios abstraits** (templates) indépendants de tout contexte organisationnel (GHT, EJ, identifiants) et de les **matérialiser** à la volée en messages HL7v2 ou FHIR adaptés au contexte choisi.

### Problème résolu

Avant : Scénarios = messages HL7/FHIR préconstruits avec identifiants/structures figées → impossible à rejouer ailleurs.

Après : Scénarios = séquence sémantique d'événements → génération dynamique adaptée à n'importe quel établissement.

## 🏗️ Architecture

### Modèles

```python
ScenarioTemplate
├── key: "ihe.hospitSimple"
├── name: "IHE PAM - Hospitalisation simple"
├── protocols_supported: "HL7v2,FHIR"
└── steps: List[ScenarioTemplateStep]
    ├── semantic_event_code: "ADMISSION_CONFIRMED"
    ├── hl7_event_code: "ADT^A01"
    ├── narrative: "Admission hospitalisation"
    └── message_role: "admission"
```

### Flux de matérialisation

```
ScenarioTemplate (abstrait)
    ↓
materialize_template(template, ej_context, options)
    ↓
InteropScenario (concret avec payload HL7/FHIR)
    ↓
send_scenario(scenario, endpoint)
    ↓
Émission vers système cible
```

## 🚀 Utilisation

### Via API

```bash
# Lister templates disponibles
curl http://127.0.0.1:8000/scenarios/templates

# Matérialiser en HL7v2
curl -X POST http://127.0.0.1:8000/scenarios/templates/ihe.hospitSimple/materialize \
  -H 'Content-Type: application/json' \
  -d '{
    "protocol": "HL7v2",
    "ej_id": 1,
    "ipp_prefix": "9",
    "nda_prefix": "5"
  }'

# Matérialiser + rejouer (dry-run)
curl -X POST http://127.0.0.1:8000/scenarios/templates/ihe.hospitSimple/play \
  -F protocol=HL7v2 \
  -F endpoint_id=2 \
  -F ipp_prefix=9 \
  -F dry_run=true
```

### Via UI

1. Aller sur http://127.0.0.1:8000/scenarios/templates
2. Cliquer sur un template
3. Remplir le formulaire (protocole, endpoint, préfixes)
4. Cliquer "Rejouer maintenant"

### Via SQLAdmin

http://127.0.0.1:8000/sqladmin/scenariotemplate/list

## 📦 Templates disponibles

### Manuels

- **ihe.hospitSimple** (7 étapes) : Parcours admission → transferts → sortie

### Auto-importés (IHE PAM)

~50 scénarios extraits depuis `/Doc/interfaces.integration_src/` :
- TestHL7HospitSimple
- TestHL7Urgence
- TestHL7ChangementLit*
- TestHL7Identite*
- etc.

## 🔧 Génération des messages

### HL7v2 (ADT)

Segments générés selon semantic_event_code :
- MSH + EVN + PID + PV1 (toujours)
- PV2 (si ADMISSION)
- DG1 (si DISCHARGE)
- AL1 (si ADMISSION_CONFIRMED)

### FHIR (Bundle)

Ressources générées :
- Patient (avec IPP)
- Organization (EJ context)
- Location (service/UF)
- Practitioner (médecin responsable)
- Encounter (avec NDA, statut adapté)

## 🔍 Événements sémantiques supportés

| Code sémantique | HL7 Event | Rôle | Description |
|-----------------|-----------|------|-------------|
| PATIENT_CREATE | ADT^A28 | lifecycle | Création identité |
| ADMISSION_PLANNED | ADT^A05 | admission | Pré-admission |
| ADMISSION_CONFIRMED | ADT^A01 | admission | Admission confirmée |
| TRANSFER | ADT^A02 | transfer | Transfert/Mutation |
| DISCHARGE | ADT^A03 | discharge | Sortie définitive |
| PATIENT_UPDATE | ADT^A31 | update | MAJ identité |
| ... | ... | ... | 18 événements mappés |

## 📁 Fichiers ajoutés

```
app/
├── models_scenarios.py              [+ScenarioTemplate, ScenarioTemplateStep]
├── services/
│   ├── scenario_template_init.py    [init templates]
│   ├── scenario_template_materializer.py [génération HL7/FHIR]
│   └── scenario_ihe_importer.py     [scan/import auto]
├── routers/
│   └── scenario_templates.py        [API REST]
├── templates/
│   └── scenario_template_detail.html [UI rejeu]
├── admin/
│   ├── __init__.py                   [+register views]
│   └── scenarios.py                  [+Template admins]
└── db.py                             [+init_scenario_templates]

tests/
└── test_scenario_template_materialize.py
```

## 🎯 Prochaines améliorations

- [ ] Génération PV2/DG1/AL1 plus riche (données cliniques)
- [ ] Support ADT^A40-A60 (fusions, annulations)
- [ ] Templates FHIR PDQm / PIXm
- [ ] Import depuis XML pivot (pas seulement HL7)
- [ ] Versioning des templates
- [ ] UI: filtres catégorie/tags
- [ ] Export template → JSON partageable

## �� Statistiques

- **Modèles** : 2 nouveaux (ScenarioTemplate, ScenarioTemplateStep)
- **Services** : 3 nouveaux (init, materializer, importer)
- **Routes** : 5 endpoints (liste, détail, materialize, play)
- **Templates** : ~51 (1 manuel + ~50 auto-importés)
- **Événements** : 18 mappings HL7↔sémantique
- **Tests** : 2 tests (HL7 + FHIR generation)

---

**Branch**: `feature/scenario-templates-contextualizable`  
**Commit**: 8489028  
**Date**: 2025-11-09
