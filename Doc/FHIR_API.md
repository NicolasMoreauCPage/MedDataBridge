# API REST FHIR - Documentation

## Vue d'ensemble

MedDataBridge expose une API REST pour l'export et l'import de données au format FHIR R4.

### URL de base

```
http://localhost:8000/api/fhir
```

### Format

Toutes les requêtes et réponses utilisent le format JSON avec le Content-Type `application/json`.

---

## Endpoints d'Export

### GET /api/fhir/export/structure/{ej_id}

Exporte la structure organisationnelle complète d'une entité juridique au format FHIR.

**Paramètres:**
- `ej_id` (path, required): ID de l'entité juridique

**Réponse:** Bundle FHIR de type 'transaction' contenant des ressources Location

**Exemple de requête:**
```bash
curl -X GET "http://localhost:8000/api/fhir/export/structure/1"
```

**Exemple de réponse:**
```json
{
  "resourceType": "Bundle",
  "type": "transaction",
  "entry": [
    {
      "resource": {
        "resourceType": "Location",
        "id": "EG1",
        "identifier": [
          {
            "system": "urn:oid:1.2.3",
            "value": "EG1"
          }
        ],
        "name": "Site Principal",
        "type": [
          {
            "coding": [
              {
                "system": "https://mos.esante.gouv.fr/NOS/TRE_R02-SecteurActivite/FHIR/TRE-R02-SecteurActivite",
                "code": "ETBL",
                "display": "Établissement"
              }
            ]
          }
        ],
        "physicalType": {
          "coding": [
            {
              "system": "http://terminology.hl7.org/CodeSystem/location-physical-type",
              "code": "si",
              "display": "Site"
            }
          ]
        }
      },
      "request": {
        "method": "PUT",
        "url": "Location/EG1"
      }
    }
  ]
}
```

---

### GET /api/fhir/export/patients/{ej_id}

Exporte les patients d'une entité juridique au format FHIR.

**Paramètres:**
- `ej_id` (path, required): ID de l'entité juridique
- `limit` (query, optional): Nombre maximum de patients à exporter (pagination)
- `offset` (query, optional): Nombre de patients à sauter (pagination)

**Réponse:** Bundle FHIR contenant des ressources Patient

**Exemple de requête:**
```bash
curl -X GET "http://localhost:8000/api/fhir/export/patients/1?limit=50&offset=0"
```

**Exemple de réponse:**
```json
{
  "resourceType": "Bundle",
  "type": "transaction",
  "entry": [
    {
      "resource": {
        "resourceType": "Patient",
        "id": "PAT001",
        "identifier": [
          {
            "type": {
              "coding": [
                {
                  "system": "http://terminology.hl7.org/CodeSystem/v2-0203",
                  "code": "PI"
                }
              ]
            },
            "system": "urn:oid:1.2.3.4.5",
            "value": "IPP123456"
          }
        ],
        "name": [
          {
            "family": "DOE",
            "given": ["JOHN"]
          }
        ],
        "gender": "male",
        "birthDate": "1980-01-01",
        "managingOrganization": {
          "reference": "Organization/EJ1"
        }
      },
      "request": {
        "method": "PUT",
        "url": "Patient/PAT001"
      }
    }
  ]
}
```

---

### GET /api/fhir/export/venues/{ej_id}

Exporte les venues (séjours/rencontres) d'une entité juridique au format FHIR.

**Paramètres:**
- `ej_id` (path, required): ID de l'entité juridique
- `limit` (query, optional): Nombre maximum de venues à exporter
- `offset` (query, optional): Nombre de venues à sauter

**Réponse:** Bundle FHIR contenant des ressources Encounter

**Exemple de requête:**
```bash
curl -X GET "http://localhost:8000/api/fhir/export/venues/1?limit=100"
```

**Exemple de réponse:**
```json
{
  "resourceType": "Bundle",
  "type": "transaction",
  "entry": [
    {
      "resource": {
        "resourceType": "Encounter",
        "id": "VEN001",
        "identifier": [
          {
            "system": "urn:oid:1.2.3.4.5",
            "value": "NDA987654"
          }
        ],
        "status": "in-progress",
        "class": {
          "system": "http://terminology.hl7.org/CodeSystem/v3-ActCode",
          "code": "IMP",
          "display": "inpatient encounter"
        },
        "subject": {
          "reference": "Patient/PAT001"
        },
        "period": {
          "start": "2023-01-01T12:00:00Z"
        },
        "location": [
          {
            "location": {
              "reference": "Location/UF1"
            }
          }
        ]
      },
      "request": {
        "method": "PUT",
        "url": "Encounter/VEN001"
      }
    }
  ]
}
```

---

### GET /api/fhir/export/all/{ej_id}

Exporte toutes les données (structure, patients, venues) en une seule requête.

**Paramètres:**
- `ej_id` (path, required): ID de l'entité juridique

**Réponse:** Objet JSON avec trois bundles séparés

**Exemple de requête:**
```bash
curl -X GET "http://localhost:8000/api/fhir/export/all/1"
```

**Exemple de réponse:**
```json
{
  "structure": {
    "resourceType": "Bundle",
    "type": "transaction",
    "entry": [...]
  },
  "patients": {
    "resourceType": "Bundle",
    "type": "transaction",
    "entry": [...]
  },
  "venues": {
    "resourceType": "Bundle",
    "type": "transaction",
    "entry": [...]
  }
}
```

---

### GET /api/fhir/export/statistics/{ej_id}

Récupère les statistiques d'export pour une entité juridique.

**Paramètres:**
- `ej_id` (path, required): ID de l'entité juridique

**Réponse:** Objet JSON avec les compteurs

**Exemple de requête:**
```bash
curl -X GET "http://localhost:8000/api/fhir/export/statistics/1"
```

**Exemple de réponse:**
```json
{
  "entite_juridique": {
    "id": 1,
    "name": "Centre Hospitalier Test",
    "finess": "123456789"
  },
  "locations": {
    "entites_geographiques": 3,
    "poles": 15,
    "services": 45,
    "unites_fonctionnelles": 90,
    "unites_hebergement": 90,
    "chambres": 450,
    "lits": 900,
    "total": 1593
  },
  "patients": 2543,
  "venues": 5421
}
```

---

## Endpoints d'Import

### POST /api/fhir/import/bundle

Importe un bundle FHIR complet.

**Corps de la requête:**
```json
{
  "ej_id": 1,
  "bundle": {
    "resourceType": "Bundle",
    "type": "transaction",
    "entry": [...]
  }
}
```

**Réponse:**
```json
{
  "status": "success",
  "message": "Import terminé: 10 créées, 5 mises à jour",
  "resources_created": 10,
  "resources_updated": 5,
  "errors": []
}
```

**Exemple de requête:**
```bash
curl -X POST "http://localhost:8000/api/fhir/import/bundle" \
  -H "Content-Type: application/json" \
  -d @bundle.json
```

---

### POST /api/fhir/import/patient

Importe une ressource Patient FHIR.

**Corps de la requête:**
```json
{
  "ej_id": 1,
  "patient": {
    "resourceType": "Patient",
    "identifier": [...],
    "name": [...],
    ...
  }
}
```

**Réponse:**
```json
{
  "status": "success",
  "message": "Patient importé avec succès",
  "resources_created": 1,
  "resources_updated": 0,
  "errors": []
}
```

---

### POST /api/fhir/import/location

Importe une ressource Location FHIR.

**Corps de la requête:**
```json
{
  "ej_id": 1,
  "location": {
    "resourceType": "Location",
    "identifier": [...],
    "name": "Unité de Cardiologie",
    ...
  }
}
```

---

### POST /api/fhir/import/encounter

Importe une ressource Encounter FHIR.

**Corps de la requête:**
```json
{
  "ej_id": 1,
  "encounter": {
    "resourceType": "Encounter",
    "identifier": [...],
    "status": "in-progress",
    ...
  }
}
```

---

### POST /api/fhir/validate/bundle

Valide un bundle FHIR sans l'importer.

**Corps de la requête:**
```json
{
  "resourceType": "Bundle",
  "type": "transaction",
  "entry": [...]
}
```

**Réponse:**
```json
{
  "valid": true,
  "errors": [],
  "warnings": [
    "Type de bundle 'batch' peut ne pas être supporté"
  ],
  "resource_count": 25
}
```

**Exemple de requête:**
```bash
curl -X POST "http://localhost:8000/api/fhir/validate/bundle" \
  -H "Content-Type: application/json" \
  -d @bundle-to-validate.json
```

---

## Codes d'erreur

- **200 OK**: Requête réussie
- **400 Bad Request**: Requête invalide (bundle mal formé, etc.)
- **404 Not Found**: Ressource non trouvée (EJ inexistante, etc.)
- **422 Unprocessable Entity**: Données invalides (validation échouée)
- **500 Internal Server Error**: Erreur serveur

---

## Pagination

Les endpoints d'export supportent la pagination via les paramètres `limit` et `offset`:

```bash
# Page 1 (50 premiers résultats)
GET /api/fhir/export/patients/1?limit=50&offset=0

# Page 2 (résultats 51-100)
GET /api/fhir/export/patients/1?limit=50&offset=50

# Page 3 (résultats 101-150)
GET /api/fhir/export/patients/1?limit=50&offset=100
```

---

## Exemples d'utilisation

### Export complet d'une structure

```bash
#!/bin/bash

# Export de la structure
curl -X GET "http://localhost:8000/api/fhir/export/structure/1" \
  -o structure.json

# Export des patients
curl -X GET "http://localhost:8000/api/fhir/export/patients/1" \
  -o patients.json

# Export des venues
curl -X GET "http://localhost:8000/api/fhir/export/venues/1" \
  -o venues.json

echo "Export terminé"
```

### Import d'un bundle

```bash
#!/bin/bash

# Valider le bundle avant import
curl -X POST "http://localhost:8000/api/fhir/validate/bundle" \
  -H "Content-Type: application/json" \
  -d @my-bundle.json \
  | jq .

# Si valid=true, importer
curl -X POST "http://localhost:8000/api/fhir/import/bundle" \
  -H "Content-Type: application/json" \
  -d '{
    "ej_id": 1,
    "bundle": '$(cat my-bundle.json)'
  }' \
  | jq .
```

### Statistiques d'export

```bash
#!/bin/bash

# Récupérer les statistiques
curl -X GET "http://localhost:8000/api/fhir/export/statistics/1" \
  | jq '.locations.total, .patients, .venues'
```

---

## Documentation interactive

L'API est également documentée via Swagger UI, accessible à:

```
http://localhost:8000/docs
```

Et ReDoc:

```
http://localhost:8000/redoc
```