# APIs REST MedDataBridge

Documentation des endpoints REST ajoutés pour l'intégration externe.

## 📋 Vue d'ensemble

MedDataBridge expose 4 APIs REST principales pour permettre l'intégration avec des systèmes externes (DPI, PAS, systèmes de facturation, etc.).

**Base URL**: `http://votre-serveur:8000`  
**Documentation interactive**: `http://votre-serveur:8000/api/docs` (Swagger UI)

## 🏥 API Patients

**Prefix**: `/api/patients`  
**Tag**: `Patients API`

Gestion complète des fiches patients avec recherche, pagination, et fusion de doublons.

### Endpoints

#### `POST /api/patients`
Crée un nouveau patient.

**Body** (exemple):
```json
{
  "family": "DUPONT",
  "given": "Jean",
  "birth_date": "1980-05-15",
  "gender": "M"
}
```

**Response**: `201 Created` + Patient créé avec ID

---

#### `GET /api/patients/{patient_id}`
Récupère un patient par son ID.

**Response**: `200 OK` + Données patient

---

#### `GET /api/patients`
Liste les patients avec filtres et pagination.

**Query params**:
- `skip` (int, défaut: 0) - Offset pagination
- `limit` (int, défaut: 100, max: 1000) - Limite résultats
- `family` (string) - Filtre nom (recherche partielle insensible casse)
- `given` (string) - Filtre prénom (recherche partielle)
- `birth_date` (date) - Filtre date naissance exacte
- `gender` (string) - Filtre sexe (M/F/U)

**Exemples**:
```
GET /api/patients?family=DUPONT&limit=10
GET /api/patients?birth_date=1980-05-15&gender=M
```

---

#### `PUT /api/patients/{patient_id}`
Met à jour un patient (champs partiels).

**Body**: Champs à mettre à jour (tous optionnels sauf si création)

---

#### `DELETE /api/patients/{patient_id}`
Supprime un patient. ⚠️ Opération irréversible.

**Response**: `204 No Content`

---

#### `GET /api/patients/{patient_id}/dossiers`
Récupère tous les dossiers d'un patient.

**Response**: `200 OK` + Liste des dossiers

---

#### `POST /api/patients/{patient_id}/merge/{other_id}`
Fusionne deux patients (dédoublonnage).

Transfère tous les dossiers de `other_id` vers `patient_id`, puis supprime `other_id`.

**Response**:
```json
{
  "message": "Patient 456 fusionné dans 123",
  "moved_dossiers": 3
}
```

---

## 📁 API Dossiers

**Prefix**: `/api/dossiers`  
**Tag**: `Dossiers API`

Gestion des dossiers patients (hospitalisations, consultations, urgences).

### Endpoints

#### `POST /api/dossiers`
Crée un nouveau dossier.

**Query params** (obligatoires):
- `patient_id` (int) - ID du patient
- `ej_id` (int) - ID de l'entité juridique
- `dossier_type` (string) - Type: HOSPITALISE, EXTERNE, URGENCE (défaut: HOSPITALISE)
- `admit_time` (datetime) - Date admission (défaut: datetime.now())

**Exemple**:
```
POST /api/dossiers?patient_id=123&ej_id=1&dossier_type=HOSPITALISE
```

**Response**: `201 Created` + Dossier créé avec numéro séquence auto

---

#### `GET /api/dossiers/{dossier_id}`
Récupère un dossier par son ID.

---

#### `GET /api/dossiers`
Liste les dossiers avec filtres (triés par date décroissante).

**Query params**:
- `skip`, `limit` - Pagination
- `patient_id` (int) - Filtre par patient
- `dossier_type` (string) - Filtre par type
- `ej_id` (int) - Filtre par entité juridique
- `date_start` (datetime) - Dossiers avec date_start >= date
- `date_end` (datetime) - Dossiers avec date_end <= date

**Exemples**:
```
GET /api/dossiers?patient_id=123&limit=10
GET /api/dossiers?ej_id=1&dossier_type=HOSPITALISE&date_start=2025-01-01
```

---

#### `PUT /api/dossiers/{dossier_id}`
Met à jour un dossier.

---

#### `DELETE /api/dossiers/{dossier_id}`
Supprime un dossier. ⚠️ Supprime aussi venues et mouvements (cascade).

**Response**: `204 No Content`

---

#### `GET /api/dossiers/{dossier_id}/venues`
Récupère toutes les venues (séjours en unité) d'un dossier.

---

#### `GET /api/dossiers/{dossier_id}/mouvements`
Récupère tous les mouvements d'un dossier (triés chronologiquement).

---

#### `POST /api/dossiers/{dossier_id}/close`
Clôture un dossier.

**Query param**:
- `date_end` (datetime, optionnel) - Date clôture (défaut: datetime.now())

**Exemples**:
```
POST /api/dossiers/456/close
POST /api/dossiers/456/close?date_end=2026-01-06T15:30:00
```

**Response**: Dossier clôturé avec date_end renseignée

**Erreur**: `400 Bad Request` si déjà clôturé

---

## 💊 API UCD

**Prefix**: `/ucd`  
**Tag**: `UCD API`

Gestion des actes UCD (Unité Commune de Dispensation) - médicaments et dispositifs médicaux identifiés par code CIP-13.

### Validation automatique

Chaque acte UCD est validé selon ces règles:
- ✅ Code CIP-13 : 13 chiffres exactement
- ✅ Quantité > 0
- ✅ Prix unitaire > 0
- ✅ Cohérence: total = unitaire × quantité (±0.01€ tolérance)

### Endpoints

#### `POST /ucd/`
Crée un acte UCD.

**Body**:
```json
{
  "dossier_id": 123,
  "code_cip": "3400936396258",
  "quantity": 2,
  "unit_price": 15.50,
  "total_price": 31.00
}
```

---

#### `GET /ucd/{act_id}`
Récupère un acte UCD.

---

#### `GET /ucd/dossier/{dossier_id}`
Liste tous les actes UCD d'un dossier.

---

#### `PUT /ucd/{act_id}`
Met à jour un acte UCD.

---

#### `DELETE /ucd/{act_id}`
Supprime un acte UCD.

---

#### `POST /ucd/{act_id}/validate`
Force la validation d'un acte UCD.

**Response**: Acte validé ou erreur 400 avec détails

---

## 🦴 API LPP

**Prefix**: `/lpp`  
**Tag**: `LPP API`

Gestion des actes LPP (Liste Produits et Prestations) - dispositifs médicaux, prothèses, orthèses identifiés par code LPP (13 chiffres).

### Validation automatique

Identique à UCD:
- ✅ Code LPP : 13 chiffres
- ✅ Quantité > 0
- ✅ Prix unitaire > 0
- ✅ Cohérence prix

### Endpoints

Structure identique à l'API UCD :
- `POST /lpp/` - Créer
- `GET /lpp/{act_id}` - Récupérer
- `GET /lpp/dossier/{dossier_id}` - Lister par dossier
- `PUT /lpp/{act_id}` - Mettre à jour
- `DELETE /lpp/{act_id}` - Supprimer
- `POST /lpp/{act_id}/validate` - Valider

**Exemple**:
```json
{
  "dossier_id": 123,
  "code_lpp": "2109876543210",
  "quantity": 1,
  "unit_price": 450.00,
  "total_price": 450.00
}
```

---

## 🔐 Authentification

⚠️ Actuellement, les APIs ne nécessitent pas d'authentification.  
**TODO**: Implémenter JWT/OAuth2 pour production (Priority 1 - Sécurité).

---

## 📊 Codes de réponse HTTP

| Code | Signification |
|------|---------------|
| 200  | Succès |
| 201  | Créé |
| 204  | Succès sans contenu (DELETE) |
| 400  | Requête invalide (validation échouée) |
| 404  | Ressource non trouvée |
| 500  | Erreur serveur |

---

## 🧪 Tests

### Avec curl

```bash
# Liste patients
curl http://localhost:8000/api/patients?limit=5

# Créer un patient
curl -X POST http://localhost:8000/api/patients \
  -H "Content-Type: application/json" \
  -d '{"family":"TEST","given":"Test","gender":"M"}'

# Récupérer un dossier
curl http://localhost:8000/api/dossiers/123
```

### Avec Swagger UI

Accédez à `http://localhost:8000/api/docs` pour une interface interactive complète avec :
- 📖 Documentation de chaque endpoint
- 🧪 Formulaires de test intégrés
- 📋 Schémas de données
- 🎯 Exemples de requêtes/réponses

---

## 📝 Notes techniques

### Pagination

Tous les endpoints liste supportent la pagination via `skip` et `limit`:
```
GET /api/patients?skip=0&limit=100    # Page 1
GET /api/patients?skip=100&limit=100  # Page 2
```

### Filtres

Les filtres texte (family, given) utilisent `ILIKE` (insensible casse, recherche partielle):
```
GET /api/patients?family=DUP  # Trouve DUPONT, DUPRÈS, etc.
```

### Dates

Format ISO 8601: `YYYY-MM-DDTHH:MM:SS` ou `YYYY-MM-DD`
```
GET /api/dossiers?date_start=2025-01-01
GET /api/dossiers?date_start=2025-01-01T08:30:00
```

---

## 🚀 Prochaines évolutions

**Priority 1** (1-3 mois):
- [ ] Authentification JWT/OAuth2
- [ ] RBAC (rôles utilisateurs)
- [ ] Audit trail des modifications

**Priority 2** (3-6 mois):
- [ ] Webhooks pour événements
- [ ] Rate limiting
- [ ] Versioning API (v2)
- [ ] Filtres avancés (OR, IN, BETWEEN)

---

## 📚 Documentation complète

Pour la documentation complète de MedDataBridge, consultez:
- `/api/docs` - Swagger UI (OpenAPI)
- `/api/redoc` - ReDoc (alternative Swagger)
- Documentation projet: voir README principal

---

**Dernière mise à jour**: 2026-01-06  
**Version API**: 1.0  
**Contact**: Équipe MedDataBridge
