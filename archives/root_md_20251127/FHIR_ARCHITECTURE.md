# 🎯 Architecture FHIR Complète - Implémentation

## ✅ Mapping Entités → Ressources FHIR

| Entité Modèle | Message HL7 | Ressource FHIR | Notes |
|---------------|-------------|----------------|-------|
| **Patient** | ADT^A31 | Patient | Identité du patient |
| **Dossier** | ❌ Aucun | **EpisodeOfCare** | Épisode administratif global |
| **Venue** | ADT^A05 | **Encounter** (principal) | Séjour/admission spécifique |
| **Mouvement A01** | ADT^A01 | **Encounter** (nested) | Admission réelle |
| **Mouvement A02** | ADT^A02 | **Encounter** (nested) | Transfert |
| **Mouvement A03** | ADT^A03 | **Encounter** (nested) | Sortie |

## 🏗️ Hiérarchie FHIR

```
Patient (Patient resource)
  └─ Dossier (EpisodeOfCare)
      └─ Venue (Encounter principal)
          ├─ Mouvement A01 (Encounter nested via partOf)
          ├─ Mouvement A02 (Encounter nested via partOf)
          └─ Mouvement A03 (Encounter nested via partOf)
```

## 📁 Structure des Bundles

### Bundle Patient
```json
{
  "resourceType": "Bundle",
  "type": "collection",
  "entry": [
    {"resource": {"resourceType": "Patient"}}
  ]
}
```

### Bundle Dossier
```json
{
  "resourceType": "Bundle",
  "entry": [
    {"resource": {"resourceType": "EpisodeOfCare"}},
    {"resource": {"resourceType": "Patient"}}
  ]
}
```

### Bundle Venue
```json
{
  "resourceType": "Bundle",
  "entry": [
    {
      "resource": {
        "resourceType": "Encounter",
        "episodeOfCare": [{"reference": "EpisodeOfCare/eoc-X"}]
      }
    },
    {"resource": {"resourceType": "EpisodeOfCare"}},
    {"resource": {"resourceType": "Patient"}}
  ]
}
```

### Bundle Mouvement
```json
{
  "resourceType": "Bundle",
  "entry": [
    {
      "resource": {
        "resourceType": "Encounter",
        "partOf": {"reference": "Encounter/enc-venue-X"},
        "episodeOfCare": [{"reference": "EpisodeOfCare/eoc-X"}]
      }
    },
    {
      "resource": {
        "resourceType": "Encounter",
        "episodeOfCare": [{"reference": "EpisodeOfCare/eoc-X"}]
      }
    },
    {"resource": {"resourceType": "EpisodeOfCare"}},
    {"resource": {"resourceType": "Patient"}}
  ]
}
```

## 🔗 Références FHIR

### Encounter (Mouvement)
```json
{
  "resourceType": "Encounter",
  "id": "enc-mvt-123",
  "status": "arrived",
  "class": {"code": "IMP"},
  "subject": {"reference": "Patient/pat-1"},
  "episodeOfCare": [{"reference": "EpisodeOfCare/eoc-10"}],
  "partOf": {"reference": "Encounter/enc-venue-20"}
}
```

### Encounter (Venue)
```json
{
  "resourceType": "Encounter",
  "id": "enc-venue-20",
  "status": "in-progress",
  "class": {"code": "IMP"},
  "subject": {"reference": "Patient/pat-1"},
  "episodeOfCare": [{"reference": "EpisodeOfCare/eoc-10"}]
}
```

### EpisodeOfCare (Dossier)
```json
{
  "resourceType": "EpisodeOfCare",
  "id": "eoc-10",
  "status": "active",
  "patient": {"reference": "Patient/pat-1"},
  "type": [{"coding": [{"code": "IMP"}]}]
}
```

## 🔄 Mapping Bidirectionnel Complet

### Émission (Outbound)

| Événement | Entité | HL7 Généré | FHIR Généré |
|-----------|--------|------------|-------------|
| Création patient | Patient | ADT^A31 | Patient |
| Création dossier | Dossier | ❌ Aucun | EpisodeOfCare |
| Création venue | Venue | ADT^A05 | Encounter |
| Création mouvement | Mouvement | ADT^A01/A02/A03 | Encounter (nested) |

### Réception (Inbound)

| Message HL7 Reçu | Entité Créée | FHIR Généré |
|------------------|--------------|-------------|
| ADT^A31 | Patient | Patient |
| ADT^A05 | **Venue** (à implémenter) | Encounter |
| ADT^A01 | **Mouvement** (à implémenter) | Encounter (nested) |

## 💾 Fichiers Modifiés

### Nouveaux Fichiers
1. **app/services/fhir_resources.py** (nouveau module)
   - `generate_patient_resource(patient)`
   - `generate_episode_of_care_resource(dossier)`
   - `generate_encounter_resource_for_venue(venue)`
   - `generate_encounter_resource_for_mouvement(mouvement)`
   - `generate_fhir_bundle_for_entity(entity, entity_type)`

2. **test_fhir_mapping.py** (tests complets)
   - Teste toutes les ressources
   - Valide la structure nested
   - Vérifie les références

### Fichiers Modifiés
1. **app/services/emit_on_create.py**
   - `generate_fhir()` simplifié
   - Utilise `generate_fhir_bundle_for_entity()`
   - Ancien code commenté

## ✅ Tests Validés

```bash
.venv/bin/python3 test_fhir_mapping.py
```

**Résultats** :
- ✅ Patient resource correcte
- ✅ EpisodeOfCare resource correcte (status, type, patient ref)
- ✅ Encounter (venue) resource correcte (class, episodeOfCare ref)
- ✅ Encounter (mouvement) resource correcte (partOf ref)
- ✅ Bundle Patient : 1 ressource
- ✅ Bundle Dossier : 2 ressources (EpisodeOfCare + Patient)
- ✅ Bundle Venue : 3 ressources (Encounter + EpisodeOfCare + Patient)
- ✅ Bundle Mouvement : 4 ressources (2 Encounters + EpisodeOfCare + Patient)
- ✅ Structure nested validée (partOf → episodeOfCare)

## 📋 TODO : Réception Messages

Pour compléter l'implémentation, il faut modifier `app/services/pam.py` :

### Actuellement
```python
# ADT^A01 reçu → crée un Dossier
```

### À Implémenter
```python
# ADT^A05 reçu → crée une Venue (qui crée un Dossier si nécessaire)
# ADT^A01 reçu → crée un Mouvement (lié à une Venue)
# ADT^A02 reçu → crée un Mouvement transfer
# ADT^A03 reçu → crée un Mouvement discharge
```

## 🎯 Bénéfices

1. **Conformité FHIR** : Mapping sémantique correct selon la spec FHIR
2. **Hiérarchie claire** : Patient ← EpisodeOfCare ← Encounter ← Encounter (nested)
3. **Bidirectionnalité** : Génération et réception cohérentes
4. **Traçabilité** : Chaque mouvement est un Encounter avec références
5. **Extensibilité** : Facile d'ajouter d'autres types de mouvements

## 🔍 Exemple Complet

### Scénario : Patient hospitalisé avec transfert

1. **Créer Patient** → Patient FHIR
2. **Créer Dossier IMP** → EpisodeOfCare FHIR
3. **Créer Venue (pre-admit)** → ADT^A05 + Encounter FHIR
4. **Créer Mouvement A01 (admit)** → ADT^A01 + Encounter nested FHIR
5. **Créer Mouvement A02 (transfer)** → ADT^A02 + Encounter nested FHIR
6. **Créer Mouvement A03 (discharge)** → ADT^A03 + Encounter nested FHIR

### Messages HL7 Générés
- ADT^A31 (patient)
- ADT^A05 (venue/pre-admit)
- ADT^A01 (admission)
- ADT^A02 (transfer)
- ADT^A03 (discharge)

### Ressources FHIR Générées
- 1 Patient
- 1 EpisodeOfCare
- 4 Encounters (1 venue + 3 mouvements nested)

## 🎉 Conclusion

L'architecture FHIR est maintenant **conforme aux standards** avec :
- ✅ Mapping correct entités → ressources
- ✅ Hiérarchie nested pour mouvements
- ✅ Références FHIR cohérentes
- ✅ Tests complets passants
- ✅ Documentation complète

**Prochaine étape** : Implémenter la réception des messages ADT^A05/A01/A02/A03 pour créer Venues/Mouvements.
