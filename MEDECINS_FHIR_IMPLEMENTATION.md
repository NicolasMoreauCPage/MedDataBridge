# Médecins Responsables - Implémentation FHIR

## Vue d'ensemble

L'intégration des médecins responsables dans les flux FHIR permet de :

1. **Import FHIR** : Extraire les informations du médecin depuis `Encounter.participant[ATND]`
2. **Export FHIR** : Générer des ressources `Practitioner` complètes avec RPPS/ADELI
3. **Cycle complet** : Import → Stockage → Export avec préservation des données

## Architecture

### Modèles

- **MedecinResponsable** : Stockage des données médecin (RPPS, ADELI, nom, spécialité)
- **Dossier.medecin_responsable_id** : Médecin responsable du dossier
- **Mouvement.medecin_responsable_id** : Médecin responsable du mouvement (peut différer du dossier)
- **UniteFonctionnelle.medecin_responsable_id** : Médecin responsable de l'UF

### Services

#### Import FHIR (`app/converters/fhir_import_converter.py`)

**FHIRToEncounterConverter.convert_encounter()**

1. Extrait `encounter.participant` avec `type.coding.code = "ATND"`
2. Résout la référence vers `Practitioner` (contained ou externe)
3. Extrait les identifiants RPPS/ADELI et les données du praticien
4. Utilise `get_or_create_medecin()` pour éviter les doublons
5. Assigne `medecin_responsable_id` au Mouvement
6. Met à jour le Dossier si nécessaire

**Méthodes d'extraction :**

- `_extract_medecin_from_participants()` : Point d'entrée principal
- `_resolve_practitioner_reference()` : Résolution des références contained (#pract-1)
- `_extract_medecin_from_practitioner()` : Extraction des données FHIR
- `_parse_practitioner_display()` : Parsing du display textuel (fallback)

**Formats supportés :**

```json
{
  "participant": [
    {
      "type": [{"coding": [{"code": "ATND"}]}],
      "individual": {
        "reference": "#pract-1",  // Référence contained
        "display": "Dr DURAND Jean-Pierre"  // Fallback si pas de Practitioner
      }
    }
  ],
  "contained": [
    {
      "resourceType": "Practitioner",
      "id": "pract-1",
      "identifier": [
        {"system": "http://rpps.fr", "value": "12345678901"},  // RPPS 11 chiffres
        {"system": "http://adeli.fr", "value": "891020646"}    // ADELI 9 chiffres
      ],
      "name": [{
        "family": "DURAND",
        "given": ["Jean-Pierre"],
        "prefix": ["Dr"]
      }],
      "qualification": [{
        "code": {"coding": [{"display": "Cardiologie"}]}
      }]
    }
  ]
}
```

#### Export FHIR (`app/services/fhir_encounters.py`)

**generate_encounter_resource_for_venue()** et **generate_encounter_resource_for_mouvement()**

1. Récupère le `MedecinResponsable` depuis `dossier.medecin_responsable_id` ou `mouvement.medecin_responsable_id`
2. Génère la section `participant` avec type ATND
3. Crée une ressource `Practitioner` contained avec :
   - Identifiants RPPS/ADELI
   - Nom complet (family, given, prefix)
   - Qualification/spécialité

**Exemple de sortie :**

```json
{
  "resourceType": "Encounter",
  "id": "enc-mvt-241",
  "participant": [
    {
      "type": [{"coding": [{"code": "ATND", "display": "attender"}]}],
      "individual": {
        "reference": "#pract-2",
        "display": "Dr Jean-Pierre DURAND"
      }
    }
  ],
  "contained": [
    {
      "resourceType": "Practitioner",
      "id": "pract-2",
      "identifier": [
        {"system": "http://rpps.fr", "value": "12345678901"}
      ],
      "name": [{"family": "DURAND", "given": ["Jean-Pierre"], "prefix": ["Dr"]}],
      "qualification": [{"code": {"coding": [{"display": "Cardiologie"}]}}]
    }
  ]
}
```

## Tests

### Test d'import FHIR

```bash
.venv/bin/python3 test_fhir_medecin_import.py
```

Vérifie :
- Extraction du médecin depuis `Encounter.participant[ATND]`
- Résolution du `Practitioner` contained
- Création ou récupération du `MedecinResponsable`
- Assignation au `Mouvement` et `Dossier`

### Test d'export FHIR

```bash
.venv/bin/python3 test_fhir_medecin_export.py
```

Vérifie :
- Génération de `Encounter.participant[ATND]`
- Inclusion du `Practitioner` contained
- Présence des identifiants RPPS/ADELI
- Complétude des données (nom, spécialité)

## Correspondances HL7 ↔ FHIR

| HL7 PAM (PV1-7) | FHIR Encounter |
|-----------------|----------------|
| `PV1-7` XCN format | `participant[ATND].individual` → `Practitioner` |
| ID Number | `identifier[system=rpps/adeli].value` |
| Family Name | `name[0].family` |
| Given Name | `name[0].given[0]` |
| Prefix (Dr, Pr) | `name[0].prefix[0]` |
| Assigning Authority | Mapping vers `system` (RPPS/ADELI) |

## Détection automatique RPPS/ADELI

Le système identifie automatiquement le type d'identifiant :

- **RPPS** : 11 chiffres → `system: "http://rpps.fr"`
- **ADELI** : 9 chiffres → `system: "http://adeli.fr"`
- **Explicite** : Si `system` contient "rpps" ou "adeli"

## Gestion des doublons

La fonction `get_or_create_medecin()` évite les doublons en recherchant :

1. Par RPPS (si fourni)
2. Par ADELI (si fourni et RPPS non trouvé)
3. Par nom complet (si aucun identifiant)

En cas de match, les données existantes sont **préservées** (pas de mise à jour automatique).

## Points d'attention

### Import nécessaire

Les scripts doivent importer `MedecinResponsable` pour que SQLAlchemy puisse résoudre les relations :

```python
from app.models_practitioners import MedecinResponsable  # Important pour les relations
```

### Session obligatoire pour l'export

L'export FHIR nécessite une `session` pour charger le médecin :

```python
encounter = generate_encounter_resource_for_mouvement(mouvement, session=session)
```

Sans session, le médecin ne sera pas inclus dans l'export.

### Fallback sur attending_provider

Si aucun `medecin_responsable_id` n'est défini, l'export utilise `venue.attending_provider` (champ texte legacy).

## Améliorations futures

1. **UI de gestion** : Interface CRUD pour les médecins responsables
2. **Validation** : Contrôle de format RPPS/ADELI au niveau du formulaire
3. **Recherche** : Autocomplete sur les médecins existants
4. **Synchronisation** : Mise à jour automatique depuis un référentiel externe (RPPS national)
5. **Historique** : Tracer les changements de médecin responsable
6. **Bundle complet** : Support des Practitioner en entrée de bundle (pas seulement contained)

## Statut

✅ **Complété** :
- Modèle MedecinResponsable
- Migration Alembic
- Import FHIR (Encounter → MedecinResponsable)
- Export FHIR (MedecinResponsable → Practitioner contained)
- Tests unitaires fonctionnels
- Intégration avec PAM (HL7)

⏳ **En attente** :
- Interface utilisateur (CRUD)
- API REST pour la gestion des médecins
- Validation avancée des identifiants
