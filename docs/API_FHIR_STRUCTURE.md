# 🔷 API FHIR Structure - Documentation Technique

**Status** : ✅ Déjà implémentée et fonctionnelle  
**Version FHIR** : R4  
**Ressource** : Location (structure hospitalière hiérarchique)

---

## 📋 Vue d'ensemble

L'API FHIR Structure expose une **interface REST standard FHIR R4** pour gérer la structure organisationnelle d'un établissement de santé via la ressource **Location**.

### Conversion Modèles

Les entités SQLModel sont converties en ressources FHIR Location :

| Entité DB | Type FHIR Location | Code physicalType |
|-----------|-------------------|-------------------|
| EntiteGeographique | Location (site) | si (Site) |
| Pole | Location (dept) | bu (Building) |
| Service | Location (dept) | wa (Ward) |
| UniteFonctionnelle | Location (dept) | wa (Ward) |
| UniteHebergement | Location (dept) | wa (Ward) |
| Chambre | Location (room) | ro (Room) |
| Lit | Location (bed) | bd (Bed) |

---

## 🔌 Endpoints

### 1. Recherche de Locations

```http
GET /fhir/Location?[parameters]
```

**Paramètres de recherche supportés** :

| Paramètre | Type | Description | Exemple |
|-----------|------|-------------|---------|
| `_id` | token | ID logique de la ressource | `_id=123` |
| `identifier` | token | Identifiant métier ou FINESS | `identifier=750001234` |
| `name` | string | Nom de la location (partiel) | `name=Cardiologie` |
| `status` | token | Statut (`active`, `inactive`, `suspended`) | `status=active` |
| `type` | token | Type de service | `type=HOSP` |
| `operational-status` | token | Statut opérationnel | `operational-status=O` |
| `partof` | reference | Location parente (navigation hiérarchique) | `partof=Location/5` |
| `_count` | number | Nombre de résultats (1-1000, défaut=50) | `_count=100` |
| `_sort` | string | Tri des résultats | `_sort=name` |
| `_format` | code | Format réponse (json, xml) | `_format=json` |

**Exemple de requête** :

```bash
# Recherche par identifiant FINESS
curl -X GET "http://localhost:8000/fhir/Location?identifier=750001234"

# Recherche des enfants d'un Pôle
curl -X GET "http://localhost:8000/fhir/Location?partof=Location/5"

# Recherche par nom avec pagination
curl -X GET "http://localhost:8000/fhir/Location?name=Cardio&_count=20"
```

**Réponse** : Bundle FHIR de type `searchset`

```json
{
  "resourceType": "Bundle",
  "type": "searchset",
  "total": 15,
  "entry": [
    {
      "fullUrl": "http://localhost:8000/fhir/Location/123",
      "resource": {
        "resourceType": "Location",
        "id": "123",
        "identifier": [
          {
            "system": "http://finess.sante.gouv.fr",
            "value": "750001234"
          }
        ],
        "status": "active",
        "name": "Service de Cardiologie",
        "physicalType": {
          "coding": [
            {
              "system": "http://terminology.hl7.org/CodeSystem/location-physical-type",
              "code": "wa",
              "display": "Ward"
            }
          ]
        },
        "partOf": {
          "reference": "Location/5",
          "display": "Pôle Médecine"
        }
      }
    }
  ],
  "link": [
    {
      "relation": "self",
      "url": "http://localhost:8000/fhir/Location?name=Cardio&_count=20"
    }
  ]
}
```

---

### 2. Lecture d'une Location par ID

```http
GET /fhir/Location/{id}
```

**Exemple** :

```bash
curl -X GET "http://localhost:8000/fhir/Location/123"
```

**Réponse** : Ressource Location FHIR

```json
{
  "resourceType": "Location",
  "id": "123",
  "meta": {
    "versionId": "1",
    "lastUpdated": "2026-01-08T10:30:00Z"
  },
  "identifier": [
    {
      "system": "http://finess.sante.gouv.fr",
      "value": "750001234"
    }
  ],
  "status": "active",
  "name": "Service de Cardiologie",
  "alias": ["Cardio", "UF Cardio"],
  "description": "Service de cardiologie interventionnelle",
  "mode": "instance",
  "physicalType": {
    "coding": [
      {
        "system": "http://terminology.hl7.org/CodeSystem/location-physical-type",
        "code": "wa",
        "display": "Ward"
      }
    ]
  },
  "partOf": {
    "reference": "Location/5",
    "display": "Pôle Médecine"
  },
  "managingOrganization": {
    "reference": "Organization/1",
    "display": "CHU Exemple"
  }
}
```

**Codes d'erreur** :
- `404` : Location introuvable

---

### 3. Création d'une Location

```http
POST /fhir/Location
Content-Type: application/fhir+json
```

**Corps de la requête** : Ressource Location FHIR complète

**Exemple** :

```bash
curl -X POST "http://localhost:8000/fhir/Location" \
  -H "Content-Type: application/fhir+json" \
  -d '{
    "resourceType": "Location",
    "identifier": [
      {
        "system": "http://mon-hopital.fr/identifiers",
        "value": "SVC-NEURO-01"
      }
    ],
    "status": "active",
    "name": "Service de Neurologie",
    "mode": "instance",
    "physicalType": {
      "coding": [
        {
          "system": "http://terminology.hl7.org/CodeSystem/location-physical-type",
          "code": "wa"
        }
      ]
    },
    "partOf": {
      "reference": "Location/5"
    }
  }'
```

**Réponse** : `201 Created` avec Location créée

**Fonctionnement** :
- Si `identifier` existe déjà → **upsert** (mise à jour)
- Sinon → **création** nouvelle entité
- Conversion FHIR → SQLModel via `process_fhir_location()`
- Retour ressource complète avec ID généré

**Codes d'erreur** :
- `400` : Format invalide ou référence parente introuvable
- `422` : Validation échouée

---

### 4. Mise à jour complète d'une Location

```http
PUT /fhir/Location/{id}
Content-Type: application/fhir+json
```

**Exemple** :

```bash
curl -X PUT "http://localhost:8000/fhir/Location/123" \
  -H "Content-Type: application/fhir+json" \
  -d '{
    "resourceType": "Location",
    "id": "123",
    "status": "inactive",
    "name": "Service de Cardiologie (fermé)",
    ...
  }'
```

**Réponse** : `200 OK` avec Location mise à jour

**Codes d'erreur** :
- `404` : Location introuvable
- `400` : Format invalide

---

### 5. Suppression d'une Location

```http
DELETE /fhir/Location/{id}
```

**Exemple** :

```bash
curl -X DELETE "http://localhost:8000/fhir/Location/123"
```

**Réponse** : `200 OK` avec OperationOutcome

```json
{
  "resourceType": "OperationOutcome",
  "issue": [
    {
      "severity": "information",
      "code": "informational",
      "diagnostics": "Location with id 123 deleted successfully"
    }
  ]
}
```

**Codes d'erreur** :
- `404` : Location introuvable
- `409` : Conflit (entités dépendantes)

---

## 🏗️ Architecture

### Fichiers clés

```
app/
├── routers/
│   └── fhir_structure.py          # Router FastAPI (~620 lignes)
│       ├── GET /fhir/Location
│       ├── GET /fhir/Location/{id}
│       ├── POST /fhir/Location
│       ├── PUT /fhir/Location/{id}
│       └── DELETE /fhir/Location/{id}
│
└── services/
    ├── fhir_structure.py           # Services conversion (~400 lignes)
    │   ├── entity_to_fhir_location()     # DB → FHIR
    │   ├── process_fhir_location()       # FHIR → DB (create/update)
    │   └── _build_partof_reference()     # Résolution hiérarchie
    │
    └── fhir_structure_export.py    # Export bundles complets
        └── export_structure_bundle()     # Pour endpoints/export
```

### Service de conversion

#### `entity_to_fhir_location(entity, session) -> Dict`

Convertit une entité SQLModel en ressource FHIR Location.

**Paramètres** :
- `entity` : EntiteGeographique, Pole, Service, UF, UH, Chambre, ou Lit
- `session` : Session SQLModel pour résoudre les références

**Retour** : Dictionnaire FHIR Location complet

**Fonctionnalités** :
- Détection automatique du type d'entité
- Résolution `partOf` (référence parent)
- Mapping `physicalType` selon type
- Conversion statuts (active/inactive/suspended)
- Identifiants multiples (FINESS, identifiers)

#### `process_fhir_location(fhir_location, session) -> Tuple[model, int, str]`

Convertit une ressource FHIR Location en entité SQLModel (create ou update).

**Paramètres** :
- `fhir_location` : Dictionnaire FHIR Location
- `session` : Session SQLModel

**Retour** : `(entity, status_code, operation)`
- `entity` : Entité créée/mise à jour
- `status_code` : 201 (created) ou 200 (updated)
- `operation` : "created" ou "updated"

**Fonctionnalités** :
- Upsert automatique par `identifier`
- Résolution `partOf` → foreign key
- Détection type via `physicalType.code`
- Validation hiérarchie (Service → Pole, UF → Service, etc.)
- Gestion erreurs avec messages détaillés

---

## 🔍 Cas d'usage

### 1. Navigation hiérarchique

**Récupérer tous les services d'un Pôle** :

```bash
# 1. Récupérer l'ID du Pôle
GET /fhir/Location?name=Pôle%20Médecine&_count=1
# → ID = 5

# 2. Récupérer ses enfants
GET /fhir/Location?partof=Location/5
# → Liste des Services du Pôle
```

### 2. Synchronisation SIH

**Créer/mettre à jour une structure depuis SIH** :

```python
import requests

# Structure reçue du SIH (format propriétaire)
sih_service = {
    "code": "SVC-CARDIO-01",
    "nom": "Service de Cardiologie",
    "pole_id": "POLE-MED",
    "statut": "actif"
}

# Conversion en FHIR Location
fhir_location = {
    "resourceType": "Location",
    "identifier": [{"system": "http://sih.hopital.fr", "value": sih_service["code"]}],
    "name": sih_service["nom"],
    "status": "active" if sih_service["statut"] == "actif" else "inactive",
    "physicalType": {"coding": [{"code": "wa"}]},
    "partOf": {"reference": f"Location/{resolve_pole_id(sih_service['pole_id'])}"}
}

# Envoi à l'API (upsert automatique)
response = requests.post(
    "http://localhost:8000/fhir/Location",
    json=fhir_location,
    headers={"Content-Type": "application/fhir+json"}
)

# 201 si créé, 200 si mis à jour
print(f"Status: {response.status_code}")
```

### 3. Export pour BI

**Récupérer toute la structure** :

```bash
# Export complet (pagination automatique)
GET /fhir/Location?_count=1000
```

### 4. Recherche multi-critères

```bash
# Services actifs de type MCO dont le nom contient "Cardio"
GET /fhir/Location?status=active&type=MCO&name=Cardio
```

---

## 🎯 Intégration avec Phases 4.1 et 5.1

### Import/Export Excel (Phase 4.1)

L'API FHIR peut être utilisée comme alternative à l'import Excel :

```python
# Dans structure_import_export.py
# Après parsing Excel, créer via API FHIR au lieu de direct DB
for row in excel_rows:
    fhir_location = convert_excel_row_to_fhir(row)
    requests.post("/fhir/Location", json=fhir_location)
```

**Avantages** :
- Validation FHIR standard
- Upsert automatique
- Logs centralisés
- Interopérabilité

### UX Interactive (Phase 5.1)

L'API FHIR peut remplacer les endpoints REST custom :

```javascript
// Dans structure-interactive.js
// Au lieu de PATCH /api/structure/{type}/{id}
async function saveEdit(entityId, field, value) {
  // 1. GET FHIR Location
  const location = await fetch(`/fhir/Location/${entityId}`).then(r => r.json());
  
  // 2. Modifier champ
  location.name = value; // ou autre champ
  
  // 3. PUT FHIR Location
  await fetch(`/fhir/Location/${entityId}`, {
    method: 'PUT',
    headers: {'Content-Type': 'application/fhir+json'},
    body: JSON.stringify(location)
  });
}
```

---

## 🔒 Sécurité et Bonnes Pratiques

### Validation

- ✅ Tous les champs requis validés
- ✅ Références `partOf` vérifiées
- ✅ Format identifiers contrôlé
- ✅ Hiérarchie cohérente

### Performance

- ✅ Indexes DB sur identifiers et FKs
- ✅ Pagination native FHIR (`_count`)
- ⚠️ **TODO** : Cache Redis pour GET répétés
- ⚠️ **TODO** : Rate limiting API externe

### Interopérabilité

- ✅ Conformité FHIR R4 standard
- ✅ Content-Type `application/fhir+json`
- ✅ Headers `Last-Modified`
- ✅ OperationOutcome pour erreurs

---

## 📊 Métriques

- **~620 lignes** : Router fhir_structure.py
- **~400 lignes** : Service de conversion
- **5 endpoints** REST complets
- **10+ paramètres** recherche FHIR
- **7 types** entités supportés

---

## 🚀 Prochaines Étapes (Phase 4.3)

1. **Webhooks** : Notifier systèmes tiers lors de CREATE/UPDATE/DELETE
2. **SSE** : Notifications temps réel pour UI (Server-Sent Events)
3. **Cache Redis** : Améliorer performance requêtes hiérarchiques
4. **Rate Limiting** : Protéger API contre abus
5. **Métriques** : Logs d'utilisation et monitoring

---

**Documentation complète** : `app/routers/fhir_structure.py` (docstrings)  
**Tests** : `tests/test_fhir_structure.py` (à créer)  
**Standard FHIR** : https://www.hl7.org/fhir/location.html
