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

Actuellement: aucune (POC). Production nécessitera:

- OAuth2 / OIDC

- API Keys pour endpoints système

- Certificats TLS mutuel (MLLP sécurisé)

## Rate Limiting

Non implémenté (POC). Prévoir pour production:

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

---
Documentation API générée automatiquement.
