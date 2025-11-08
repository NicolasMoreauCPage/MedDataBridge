# Architecture MedData Bridge

## Vue d'ensemble

MedData Bridge est une plateforme d'interopérabilité médicale supportant FHIR R4 et HL7 v2.5 (profil IHE PAM France).

## Stack technique

- **Backend**: FastAPI 0.112.2 + SQLModel 0.0.21

- **Base de données**: SQLite (dev) / PostgreSQL (prod)

- **UI**: Jinja2 + Tailwind CSS + Vanilla JS

- **Admin**: SQLAdmin 0.20.1

- **Tests**: Pytest + Playwright

## Structure des modules

### Core (`app/`)

| Module | Responsabilité |

|--------|---------------|
| `app.py` | Point d'entrée FastAPI, configuration middleware, routing |
| `db.py` | Session factory SQLModel, init DB |
| `db_session_factory.py` | Gestion sessions DB avancée |

### Modèles de données (`app/models*.py`)

| Fichier | Domaine |

|---------|---------|
| `models.py` | Patient, Dossier, Venue, Mouvement (entités de base PAM) |
| `models_structure.py` | Hiérarchie géographique (Pôle, Service, UF, UH, Chambre, Lit) |
| `models_structure_fhir.py` | Contextes GHT, Entité Juridique |
| `models_endpoints.py` | SystemEndpoint, MessageLog (connectivité) |
| `models_identifiers.py` | IdentifierNamespace, Identifier (espaces de nommage) |
| `models_workflows.py` | PatientWorkflow, DossierWorkflow (orchestration) |
| `models_scenarios.py` | Scenario, ScenarioStep (tests fonctionnels) |
| `models_vocabulary.py` | VocabularyDomain, VocabularyValue (référentiels) |
| `models_transport.py` | MLLP, File, HTTP transport configs |

### Services (`app/services/`)

| Service | Fonction |

|---------|----------|
| `hl7_generator.py` | Génération messages HL7 v2.5 (ADT^A01..A47, ZBE) |
| `pam_validation.py` | Validation IHE PAM France (segments, datatypes, ZBE) |
| `nature_mapping.py` | Mapping trigger→nature (ZBE-9) |
| `transport_inbound.py` | Traitement messages entrants (UPDATE/CANCEL/INSERT) |
| `transport_file.py` | Polling dossiers (inbox/outbox) |
| `transport_mllp.py` | Serveur/client MLLP HL7 |

### Parsing (`app/infrastructure/hl7/parsing/`)

| Parser | Rôle |

|--------|------|
| `msh_parser.py` | En-tête message (MSH) |
| `pid_parser.py` | Identité patient (PID) |
| `pv1_parser.py` | Visite patient (PV1) |
| `zbe_parser.py` | Segment ZBE national (IHE PAM FR) |

### Routeurs (`app/routers/`)

| Router | Endpoints |

|--------|-----------|
| `admin.py` | `/admin/ght` (sélection contexte) |
| `patients.py` | CRUD patients |
| `dossiers.py` | CRUD dossiers |
| `venues.py` | CRUD venues/séjours |
| `mouvements.py` | CRUD mouvements patient |
| `structure.py` | Hiérarchie locations FHIR |
| `endpoints.py` | Configuration endpoints système |
| `messages.py` | Consultation logs messages |
| `documentation.py` | Interface doc markdown |
| `health.py` | `/health`, `/api/version` |

### Middleware (`app/middleware/`)

| Middleware | Fonction |

|------------|----------|
| `ght_context.py` | Injection contextes GHT/EJ/Patient/Dossier dans request.state |
| `flash.py` | Messages flash (success/error/info) |

### Workflows (`app/workflows/`)

Orchestration métier pour scénarios complexes (admission, transfert, sortie).

### Formulaires (`app/forms/`)

Définition forms Jinja2 + validation Pydantic pour UI.

### Dépendances (`app/dependencies/`)

Fonctions de dépendance FastAPI (require_ght_context, etc.).

## Flux de données

### Inbound (Réception)

```text

Message HL7 → Parser → Validation PAM → Transport Inbound → DB
                ↓                           ↓
           MessageLog              Mouvement/Dossier/Patient

```

### Outbound (Émission)

```text

DB → HL7 Generator → Validation → Transport (MLLP/File) → Destinataire
         ↓
     MessageLog

```

## Conformité IHE PAM France

- Segment ZBE complet (ZBE-1..9)

- Actions INSERT/UPDATE/CANCEL

- Nature mouvement (S,H,M,L,D,SM)

- UF médicale & UF soins (XON)

- Provenance PV1-6 (A02 transferts)

- Validation stricte datatypes HL7 v2.5

## Base de données

Modèle relationnel avec:

- **Hiérarchie patient**: Patient → Dossier → Venue → Mouvement

- **Hiérarchie structure**: GHT → EJ → Pôle → Service → UF → UH → Chambre → Lit

- **Traçabilité**: MessageLog (tous messages in/out)

- **Référentiels**: VocabularyDomain/Value (codes métier)

## Migration & Évolution

- Alembic pour migrations schema

- Scripts one-shot dans `one_shot_legacy/`

- Migrations SQL manuelles dans `migrations/`

## Tests

- **Unit**: `tests/test_*.py` (pytest)

- **E2E**: `tests/playwright_*.py` (Playwright)

- **Benchmark**: `program_docs/benchmark_zbe_performance.py`

## Documentation

- **Externe**: `/Doc` (specs IHE PAM, HL7 v2.5)

- **Interne**: `/program_docs` (impl, compliance matrix, legacy behavior)

- **UI**: `/documentation` (accès web aux docs markdown)

## Sécurité & Sessions

- SessionMiddleware (cookies signés)

- SECRET_KEY depuis env ou généré éphémère

- Contextes GHT/EJ/Patient isolés par session

## Performance

- Benchmark génération: ~1.78 ms/message (1000 A01)

- Parsing/validation: négligeable (<5% overhead)

- MLLP async (sans blocage)

---
Dernière mise à jour automatique.
