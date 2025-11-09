# Guide API - MedData Bridge

## Endpoints Principaux

### Santé & Version

#### GET /health

Check de santé

**Réponse**:

```json

{"status": "ok"}

```

#### GET /api/version

Version de l'application

**Réponse**:

```json

{
  "version": "0.2.0",
  "app": "MedData_Bridge"
}

```

### Patients

#### GET /patients

Liste patients (avec contexte GHT/EJ)

**Query params**:

- `search`: Filtre nom/prénom

- `limit`: Limite résultats (défaut: 50)

#### POST /patients

Créer un patient

**Body** (JSON):

```json

{
  "family": "Dupont",
  "given": "Jean",
  "birth_date": "1980-01-15",
  "gender": "male"
}

```

#### GET /patients/{id}

Détails d'un patient

#### PUT /patients/{id}

Mise à jour patient

#### DELETE /patients/{id}

Suppression patient (logique)

### Dossiers

#### GET /dossiers

Liste dossiers

**Filtres contextuels**:

- Patient si contexte actif

- EJ si contexte actif

#### POST /dossiers

Créer un dossier

**Body**:

```json

{
  "patient_id": 123,
  "dossier_seq": 45678,
  "uf_responsabilite": "UF-MED",
  "admit_time": "2025-11-08T10:00:00Z",
  "dossier_type": "HOSPITALISE"
}

```

#### GET /dossiers/{id}

Détails dossier + venues + mouvements

#### PUT /dossiers/{id}

Mise à jour dossier

### Mouvements

#### GET /mouvements

Liste mouvements (filtré par venue/dossier/patient selon contexte)

#### POST /mouvements

Créer mouvement

**Body**:

```json

{
  "venue_id": 456,
  "mouvement_seq": 78901,
  "when": "2025-11-08T14:30:00Z",
  "location": "SERVICE-A/CHAMBRE-12/LIT-1",
  "trigger_event": "A01",
  "action": "INSERT",
  "uf_medicale_code": "UF-MED-01",
  "nature": "S"
}

```

#### GET /mouvements/{id}

Détails mouvement

#### PUT /mouvements/{id}

Mise à jour mouvement

### Structure

#### GET /structure/organizations

Hiérarchie complète GHT → EJ → Pôle → Service → UF

#### GET /structure/locations

Hiérarchie locations UF → UH → Chambre → Lit

#### POST /structure/locations/{type}

Créer location (type: pole, service, uf, uh, chambre, lit)

### Messages

#### GET /messages

Consultation logs messages HL7

**Query params**:

- `status`: error | success | pending

- `trigger_event`: A01, A02, etc.

- `direction`: inbound | outbound

- `limit`: 100 (défaut)

#### GET /messages/{id}

Détails message + contenu HL7 brut

#### POST /messages/generate

Génération manuelle message HL7

**Body**:

```json

{
  "patient_id": 123,
  "dossier_id": 456,
  "venue_id": 789,
  "trigger_event": "A01"
}

```

### Endpoints Système

#### GET /endpoints

Liste endpoints configurés (MLLP, File, HTTP)

#### POST /endpoints

Créer endpoint

**Body MLLP**:

```json

{
  "name": "HIS-Principal",
  "type": "mllp",
  "host": "192.168.1.100",
  "port": 2575,
  "direction": "outbound",
  "ej_emetteur_id": 1
}

```

#### PUT /endpoints/{id}

Mise à jour endpoint

#### POST /endpoints/{id}/test

Test connexion endpoint

### Contextes

#### POST /context/set/ght/{id}

Activer contexte GHT

#### POST /context/set/ej/{id}

Activer contexte EJ

#### POST /context/set/patient/{id}

Activer contexte Patient

#### POST /context/set/dossier/{id}

Activer contexte Dossier

#### GET /context/clear

Effacer contexte

**Query param**: `kind` (ght | ej | patient | dossier | all)

## Codes HTTP Communs

- `200`: Succès

- `201`: Créé

- `400`: Requête invalide (validation failed)

- `404`: Ressource introuvable

- `409`: Conflit (ex: dossier_seq existe déjà)

- `500`: Erreur serveur

## Authentification

**Note RC:** Authentification simplifiée actuellement. La version 1.0 finale incluera:

- OAuth2 / OIDC

- API Keys pour endpoints système

- Certificats TLS mutuel (MLLP sécurisé)

## Rate Limiting

**Note RC:** Rate limiting à implémenter pour v1.0 finale:

- 100 req/min par IP (API générale)

- 1000 req/min pour MLLP inbound

## Pagination

Format standard:

```json

{
  "items": [...],
  "total": 250,
  "page": 1,
  "page_size": 50,
  "total_pages": 5
}

```

Paramètres query:

- `page`: Numéro page (1-based)

- `page_size`: Taille page (max 100)

## Filtres Communs

- `search`: Recherche textuelle

- `created_after`: ISO8601 datetime

- `created_before`: ISO8601 datetime

- `status`: Statut entité

## Scénarios d'Interopération

### GET /scenarios

Liste tous les scénarios

**Réponse**:

```json
[
  {
    "id": 1,
    "key": "admission-simple",
    "name": "Admission Simple A01",
    "protocol": "HL7v2",
    "steps_count": 3,
    "category": "Urgences",
    "tags": "admission,urgences"
  }
]
```

### GET /scenarios/{id}

Détails d'un scénario avec steps

**Réponse**:

```json
{
  "id": 1,
  "key": "admission-simple",
  "name": "Admission Simple A01",
  "description": "Patient admis aux urgences",
  "protocol": "HL7v2",
  "category": "Urgences",
  "tags": "admission,urgences",
  "ght_context_id": 1,
  "time_anchor_mode": "sliding",
  "time_anchor_days_offset": -1,
  "preserve_intervals": true,
  "jitter_min_minutes": 1,
  "jitter_max_minutes": 5,
  "steps": [
    {
      "id": 10,
      "order_index": 0,
      "message_type": "ADT^A01",
      "message_format": "HL7v2",
      "delay_seconds": 0,
      "payload": "MSH|^~\\&|SENDING|..."
    }
  ]
}
```

### GET /scenarios/{id}/export

Exporter scénario en JSON (format import/export)

**Réponse**:

```json
{
  "id": 1,
  "key": "admission-simple",
  "name": "Admission Simple A01",
  "description": "Patient admis aux urgences",
  "protocol": "HL7v2",
  "tags": "admission,urgences",
  "time_config": {
    "anchor_mode": "sliding",
    "anchor_days_offset": -1,
    "fixed_start_iso": null,
    "preserve_intervals": true,
    "jitter_min": 1,
    "jitter_max": 5,
    "jitter_events": true
  },
  "steps": [
    {
      "order_index": 0,
      "message_type": "ADT^A01",
      "format": "HL7v2",
      "delay_seconds": 0,
      "payload": "MSH|^~\\&|SENDING|FACILITY|..."
    }
  ]
}
```

### POST /scenarios/import

Importer scénario depuis JSON

**Content-Type**: `multipart/form-data`

**Form Fields**:

- `ght_context_id` (int, required): Contexte GHT cible
- `json_file` (file, optional): Fichier JSON à uploader
- `json_data` (text, optional): JSON en texte brut (si pas de fichier)
- `override_key` (string, optional): Nouvelle clé pour éviter collision
- `override_name` (string, optional): Nouveau nom

**Exemple cURL**:

```bash
# Upload fichier
curl -X POST http://localhost:8000/scenarios/import \
  -F "ght_context_id=1" \
  -F "json_file=@scenario.json"

# Ou JSON direct
curl -X POST http://localhost:8000/scenarios/import \
  -F "ght_context_id=1" \
  -F 'json_data={"key":"test","name":"Test","protocol":"HL7v2","steps":[]}'

# Avec override
curl -X POST http://localhost:8000/scenarios/import \
  -F "ght_context_id=1" \
  -F "json_file=@scenario.json" \
  -F "override_key=scenario-imported-2025"
```

**Réponse Succès** (303 Redirect vers `/scenarios/{new_id}`)

**Réponse Erreur**:

```json
{
  "detail": "Erreur d'import: Un scénario avec la clé 'test-key' existe déjà"
}
```

### POST /scenarios/{id}/send

Rejouer un scénario vers un endpoint

**Form Data**:

- `endpoint_id` (int, required): ID de l'endpoint cible
- `step_id` (int, optional): Si fourni, n'envoie que ce step

**Réponse Succès** (303 Redirect)

**Erreurs**:

- `400`: Endpoint non configuré en mode sender
- `404`: Scénario ou endpoint introuvable

### GET /scenarios/runs

Dashboard d'exécution des scénarios (UI HTML)

### GET /scenarios/runs.json

Liste des exécutions récentes (JSON)

**Query params**:

- `limit`: Nombre max (défaut: 200)

**Réponse**:

```json
[
  {
    "id": 1001,
    "scenario_id": 1,
    "endpoint_id": 5,
    "status": "success",
    "success_steps": 3,
    "error_steps": 0,
    "skipped_steps": 0,
    "total_steps": 3,
    "dry_run": false,
    "started_at": "2025-11-09T10:30:00",
    "finished_at": "2025-11-09T10:30:15"
  }
]
```

### GET /scenarios/api/stats

Statistiques agrégées

**Query params**:

- `scenario_id` (int, optional): Filtrer par scénario
- `endpoint_id` (int, optional): Filtrer par endpoint
- `days_back` (int, default=30): Période d'analyse

**Réponse**:

```json
{
  "total_runs": 125,
  "success_rate": 0.96,
  "total_errors": 5,
  "avg_duration_seconds": 12.4,
  "period_days": 30
}
```

### GET /scenarios/api/ack-distribution

Distribution des codes ACK

**Query params**: Identiques à `/stats`

**Réponse**:

```json
{
  "AA": 115,
  "AE": 5,
  "AR": 3,
  "CA": 2
}
```

### GET /scenarios/api/timeline

Exécutions par jour

**Query params**: Identiques à `/stats`

**Réponse**:

```json
{
  "2025-11-09": 15,
  "2025-11-08": 22,
  "2025-11-07": 18,
  ...
}
```

### GET /scenarios/api/comparison

Comparaison de performances entre scénarios

**Query params**:

- `endpoint_id` (optional)
- `days_back` (default=30)
- `limit` (default=10): Nombre de scénarios

**Réponse**:

```json
[
  {
    "scenario_id": 1,
    "scenario_name": "Admission Simple",
    "total_runs": 45,
    "success_rate": 0.98,
    "avg_duration": 10.2
  },
  {
    "scenario_id": 2,
    "scenario_name": "Transfert MCO",
    "total_runs": 38,
    "success_rate": 0.95,
    "avg_duration": 15.7
  }
]
```

### GET /scenarios/api/run/{run_id}/errors

Détails des erreurs d'une exécution

**Réponse**:

```json
[
  {
    "step_order": 2,
    "message_type": "ADT^A08",
    "error_message": "Timeout MLLP après 30s",
    "ack_code": null,
    "timestamp": "2025-11-09T10:35:22"
  }
]
```

## Validation JSON Import

Le JSON d'import doit respecter cette structure:

**Champs Requis**:
- `key` (string): Identifiant unique
- `name` (string): Nom du scénario
- `protocol` (string): "HL7v2" ou "FHIR"
- `steps` (array): Liste des étapes

**Champs Optionnels**:
- `description` (string)
- `category` (string)
- `tags` (string): Séparés par virgules
- `time_config` (object):
  - `anchor_mode` (string): "sliding" | "fixed" | "none"
  - `anchor_days_offset` (int)
  - `fixed_start_iso` (string): Date ISO 8601
  - `preserve_intervals` (bool)
  - `jitter_min` (int): Minutes
  - `jitter_max` (int): Minutes
  - `jitter_events` (bool)

**Structure Step**:
- `order_index` (int, required): Position dans séquence (0-based)
- `message_type` (string, required): Type HL7 (ex: "ADT^A01")
- `format` (string, optional): "HL7v2" ou "FHIR"
- `delay_seconds` (int, optional): Délai avant ce step (0 par défaut)
- `payload` (string, required): Contenu du message

**Validation Automatique**:
- Types vérifiés (steps = array, time_config = object)
- Champs requis présents
- Structure steps conforme
- Retourne erreur explicite si invalide

---
Documentation API v0.3.0
