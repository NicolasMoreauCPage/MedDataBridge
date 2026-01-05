# Organisation du projet MedData Bridge

## Vue d'ensemble

MedData Bridge est organisé en modules fonctionnels clairs avec séparation des responsabilités entre UI, API, services métier et infrastructure.

## Structure racine

```
MedDataBridge-main/
├── app/                    # Application principale FastAPI
├── tests/                  # Suite de tests complète (575+ tests)
├── docs/                   # Documentation projet
├── scripts/                # Scripts utilitaires et maintenance
├── adapters/               # Adaptateurs HL7
├── alembic/                # Migrations base de données
├── config/                 # Configuration centralisée
├── deployment/             # Configurations de déploiement
├── Deploiement/            # Scripts de déploiement alternatifs
├── requirements*.txt       # Fichiers de dépendances Python
├── pyproject.toml          # Configuration projet Python
└── medbridge.db            # Base SQLite (générée après init_db)
```

## 📁 app/ - Application principale

### Routers (62 fichiers)

**Organisation par domaine fonctionnel** :

#### Cœur métier (8 routers)
- `patients.py` - Gestion des patients (CRUD, recherche, fusion)
- `dossiers.py` - Gestion des dossiers patients (3 routers: UI, API, workflows)
- `venues.py` - Gestion des venues (séjours)
- `mouvements.py` - Mouvements intra-hospitaliers (2 routers: UI, AJAX)
- `home.py` - Page d'accueil et navigation principale
- `menu.py` - Menu mapping et navigation contextuelle
- `timeline.py` - Vue chronologique des événements
- `contacts.py` - Gestion des contacts patients

#### Structure hospitalière (8 routers)
- `structure.py` - Structure hiérarchique (3 routers: UI, API, redirects)
- `structure_hl7.py` - Export/Import structure via HL7 MFN
- `structure_select.py` - Sélecteur de structures
- `fhir_structure.py` - Structure FHIR (Location, Organization)
- `dossier_type.py` - Types de dossiers
- **Sous-module `ght/`** :
  - `ej.py` - Entités juridiques
  - `structure.py` - Structure GHT

#### Interopérabilité (12 routers)
- `messages.py` - Messages HL7/FHIR (historique, recherche, rejeu)
- `endpoints.py` - Configuration des endpoints (FILE, MLLP, REST)
- `transport.py` - Transport de messages
- `transport_views.py` - Vues transport et monitoring
- `ihe.py` - Profils IHE (PAM, PIX, PDQ)
- `fhir_export.py` - Export FHIR (bundles, ressources)
- `fhir_import.py` - Import FHIR (bundles, validation)
- `fhir_inbox.py` - Boîte de réception FHIR
- `interop.py` - Tests d'interopérabilité
- `generate.py` - Génération de messages test
- `workflow.py` - Workflows d'interopérabilité
- `validation.py` - Validation de messages

#### Cotation et nomenclatures (5 routers)
- `cotation_modern.py` - Cotation moderne (interface moderne)
- `cotation_selector.py` - Sélecteur de dossiers pour cotation
- `ccam.py` - Classification Commune des Actes Médicaux
- `ucd.py` - Unité Commune de Dispensation
- `lpp.py` - Liste des Produits et Prestations

#### Scénarios et tests (6 routers)
- `scenarios.py` - Gestion des scénarios d'interopérabilité
- `scenario_templates.py` - Templates de scénarios contextualisables
- `scenario_ej_config.py` - Configuration scénarios par EJ (UF, médecins)
- `interface_testing.py` - Tests d'interfaces GAM/GAP (2 routers: API, UI)
- `test_scenario_generator.py` - Générateur automatique de scénarios
- `ui_test_scenarios.py` - Interface UI pour scénarios de test

#### Administration et monitoring (8 routers)
- `admin_gateway.py` - Gateway d'administration (routage dynamique)
- `admin_protected.py` - Routes admin protégées
- `cache.py` - Gestion du cache Redis (API)
- `metrics.py` - Métriques applicatives (2 routers: UI, API)
- `health.py` - Health checks (app, DB)
- `auth.py` - Authentification et autorisation
- `context.py` - Gestion des contextes GHT/EJ
- `tasks.py` - Gestion de tâches asynchrones

#### Documentation et utilitaires (8 routers)
- `guide.py` - Guide utilisateur interactif
- `docs.py` - Documentation API (OpenAPI)
- `documentation.py` - Documentation métier
- `doc_wrapper.py` - Wrapper HTML pour docs
- `vocabularies.py` - Gestion des vocabulaires
- `import_examples.py` - Import d'exemples et données de test
- `debug_events.py` - Debug événements (dev only)
- `roundtrip_hprim.py` - Tests roundtrip HPRIM

**Sous-module conformité** :
- `conformity/` - Vérification de conformité des messages

### Services (80+ fichiers)

**Organisation par catégorie** :

#### FHIR (12 fichiers)
```
fhir.py                          # Génération bundles FHIR
fhir_resources.py                # Génération ressources (Patient, Encounter, etc.)
fhir_encounters.py               # Encounters FHIR
fhir_export_service.py           # Service d'export FHIR
fhir_import_service.py           # Service d'import FHIR
fhir_organization.py             # Organizations FHIR
fhir_structure.py                # Structure FHIR (Locations)
fhir_structure_export.py         # Export structure FHIR
fhir_transport.py                # Transport FHIR
```

#### HL7/HPRIM (15 fichiers)
```
hl7_generator.py                 # Génération messages HL7
hl7_parser.py                    # Parsing HL7
adt_parser.py                    # Parsing ADT spécifique
mllp.py                          # Client/serveur MLLP
mllp_manager.py                  # Manager MLLP (lifecycle)
pam.py                           # IHE PAM (ADT messages)
pam_validation.py                # Validation PAM
pam_i18n.py                      # Internationalisation PAM
pam_sequence_validator.py        # Validation séquences PAM
mfn_importer.py                  # Import MFN
mfn_structure.py                 # Structure MFN (M05)
mfn_organization.py              # Organizations MFN
transport_inbound.py             # Pipeline ingestion messages
message_router.py                # Routage des messages
hprim/ (sous-dossier)            # Services HPRIM spécifiques
```

#### Scénarios (20+ fichiers)
```
scenario_runner.py               # Exécution de scénarios
scenario_capture.py              # Capture dossiers comme templates
scenario_dashboard.py            # Dashboard exécutions
scenario_loader.py               # Chargement scénarios
scenario_import.py               # Import scénarios
scenario_ihe_importer.py         # Import scénarios IHE
scenario_template_init.py        # Initialisation templates
scenario_template_materializer.py # Matérialisation templates
scenario_realistic_timeplan.py   # Génération timeplans réalistes
scenario_timeplan.py             # Gestion timeplans
scenario_date_updater.py         # Mise à jour dates
scenario_identifier_replacer.py  # Remplacement identifiants
scenario_identity_generator.py   # Génération identités
scenario_status_service.py       # Suivi statut
scenario_transform.py            # Transformations
scenario_validation.py           # Validation scénarios
```

#### Métier (10 fichiers)
```
dossiers_service.py              # Service dossiers
dossier_service.py               # Service dossier (singleton)
dossiers_presenter.py            # Présentation dossiers
patients_service.py              # Service patients
venues_service.py                # Service venues
patient_merge.py                 # Fusion patients
patient_update_helper.py         # Helper MAJ patients
dossier_type_mapping.py          # Mapping types dossiers
nature_mapping.py                # Mapping natures séjour
```

#### Structure et identifiants (8 fichiers)
```
structure_emit.py                # Émission messages structure
structure_schedule.py            # Planification structure
structure_seed.py                # Initialisation structure
structure_tree.py                # Arbre hiérarchique
identifier_generator.py          # Génération identifiants
identifier_manager.py            # Gestion identifiants
identifier_namespace_classifier.py # Classification namespaces
medecin_extractor.py             # Extraction médecins
```

#### Nomenclatures (4 fichiers)
```
ucd_service.py                   # Service UCD
lpp_service.py                   # Service LPP
ngap_service.py                  # Service NGAP
(ccam via modules externes)      # Service CCAM
```

#### Vocabulaires (12 fichiers)
```
vocabulary_loader.py             # Chargement vocabulaires
vocabulary_lookup.py             # Recherche vocabulaires
vocabulary_mappings.py           # Mappages vocabulaires
vocabulary_translate.py          # Traduction codes
vocabulary_fallback.py           # Valeurs par défaut
vocabulary_fhir_fr.py            # Vocabulaires FHIR FR
vocabulary_ihe_fr.py             # Vocabulaires IHE FR
vocabulary_mfn.py                # Vocabulaires MFN
```

#### Infrastructure (10 fichiers)
```
cache_service.py                 # Service cache Redis
scheduler.py                     # Scheduler tâches
file_poller.py                   # Polling endpoints FILE
entity_events.py                 # Événements entités
entity_events_structure.py       # Événements structure
emit_on_create.py                # Émission auto à création
z99_handler.py                   # Handler segments Z99
```

**Sous-dossier conformity/** :
- Services de vérification de conformité des messages

### Modèles (17 fichiers models_*.py)

```
models.py                        # Modèles principaux (Patient, Dossier, Venue, Mouvement, UCDAct, LPPAct)
models_structure.py              # Structure (EG, Pole, Service, UF, UH, Chambre, Lit, GHT)
models_identifiers.py            # Identifiants et namespaces
models_endpoints.py              # Endpoints et transport
models_context.py                # Contextes GHT et mappings
models_scenarios.py              # Scénarios d'interopérabilité
models_scenario_config.py        # Configuration scénarios
models_scenario_runs.py          # Exécutions et logs
models_contacts.py               # Contacts patients/venues
models_practitioners.py          # Praticiens
models_transport.py              # Messages et logs transport
models_vocabulary.py             # Vocabulaires
models_workflows.py              # Workflows
models_structure_fhir.py         # Mapping structure FHIR
models_shared.py                 # Modèles partagés
```

### Converters (2 fichiers)

```
fhir_converter.py                # Conversion modèles → FHIR
fhir_import_converter.py         # Conversion FHIR → modèles (avec FHIRBundleImporter)
```

### Schemas (package)

```
schemas/__init__.py              # Package schemas Pydantic
schemas/ucd.py                   # Schémas UCD
schemas/lpp.py                   # Schémas LPP
```

### API (package)

```
api/__init__.py                  # Package API REST externe
api/ucd.py                       # API REST UCD
api/lpp.py                       # API REST LPP
```

### Autres modules

#### Templates (87+ fichiers)
```
app/templates/                   # Templates Jinja2
  ├── base.html                  # Template de base
  ├── home.html                  # Page d'accueil
  ├── patients/                  # Templates patients
  ├── dossiers/                  # Templates dossiers
  ├── structure/                 # Templates structure
  ├── scenarios/                 # Templates scénarios
  ├── admin/                     # Templates admin
  └── ...
```

#### Static (assets)
```
app/static/
  ├── css/                       # Feuilles de style
  ├── js/                        # JavaScript
  └── images/                    # Images et icônes
```

#### Middleware (4 fichiers)
```
app/middleware/
  ├── flash.py                   # Flash messages
  ├── ght_context.py             # Contexte GHT
  ├── version.py                 # Version tracking
  └── error_handler.py           # Gestion erreurs
```

#### Autres composants
```
app/metrics.py                   # Métriques applicatives
app/logging_config.py            # Configuration logging
app/version.py                   # Version de l'app
app/auth.py                      # Authentification JWT
app/db.py                        # Configuration DB et sessions
app/dependencies/                # Dependencies FastAPI
app/validators/                  # Validateurs contextuels
app/vocabularies/                # Données vocabulaires
app/workflows/                   # Définitions workflows
app/admin/                       # Vues SQLAdmin
app/adapters/                    # Adaptateurs protocoles
app/forms/                       # Formulaires
app/runtime/                     # Runtime helpers
app/infrastructure/              # Infrastructure
```

## 📁 tests/ - Suite de tests complète

**575+ tests** organisés par type :

```
tests/
├── api/                         # Tests API REST (endpoints, réponses, erreurs)
├── integration/                 # Tests d'intégration (workflows complets)
├── unit/                        # Tests unitaires (services, convertisseurs)
├── ui/                          # Tests UI (Playwright, forms, navigation)
├── security/                    # Tests de sécurité (auth, permissions)
├── performance/                 # Tests de performance (load, stress)
├── mutation/                    # Tests de mutation (robustesse code)
├── property/                    # Property-based testing (Hypothesis)
├── messages/                    # Tests messages HL7/FHIR
├── Interfaces/                  # Tests d'interfaces
├── artifacts/                   # Artefacts de test (bundles, messages)
├── exemples/                    # Exemples de données test
├── generated/                   # Fichiers générés pendant tests
├── test_archive/                # Archives de tests
├── test_reports/                # Rapports de tests
├── coverage/                    # Rapports de couverture
└── conftest.py                  # Configuration pytest globale
```

## 📁 scripts/ - Scripts utilitaires

```
scripts/
├── archive/                     # Scripts archivés
├── maintenance/                 # Scripts de maintenance (à créer)
├── deploy_to_qualifinterop.ps1  # Déploiement serveur qualif
├── disable_demo_endpoint.*      # Désactivation démo
├── mfn_roundtrip.py             # Tests MFN roundtrip
├── remote_*.py/sh/sql           # Requêtes distantes et diagnostics
└── run_*.sh                     # Scripts d'exécution
```

## 📁 docs/ - Documentation

```
docs/
├── CHANGELOG.md                 # Historique des versions
├── PROGRAM_DOCUMENTATION.md     # Documentation technique complète
├── PROJECT_ORGANIZATION.md      # Ce fichier - organisation projet
├── MENU_MAP.md                  # Carte des menus et routes
├── COTATION_FONCTIONNELLE.md    # Documentation cotation
├── TODO_UI_UX.md                # TODO améliorations UI/UX
└── VERSIONING_PROPOSAL.md       # Stratégie de versioning
```

## 📁 deployment/ - Configurations déploiement

```
deployment/
├── general/                     # Configuration générale
│   ├── .env.example             # Variables d'environnement
│   └── systemd/                 # Services systemd
└── postgresql/                  # Configuration PostgreSQL
    └── alembic/                 # Migrations PostgreSQL
```

## 📁 alembic/ - Migrations base de données

```
alembic/
├── versions/                    # Versions de migration
│   └── *.py                     # Scripts de migration
├── env.py                       # Configuration environnement
├── script.py.mako               # Template génération migrations
└── README                       # Instructions migrations
```

## 📁 config/ - Configuration centralisée

```
config/
├── .env.example                 # Exemple variables environnement
└── settings.py                  # Paramètres centralisés (non présent actuellement)
```

## 📁 adapters/ - Adaptateurs HL7

```
adapters/
└── (fichiers adaptateurs HL7)   # Adaptateurs protocoles externes
```

## Conventions de nommage

### Routers
- **Format** : `{domain}[_{subdomain}].py`
- **Exemples** : `patients.py`, `fhir_export.py`, `cotation_modern.py`
- **Sous-modules** : `ght/`, `conformity/`
- **Préfixe** : Défini dans le router avec `APIRouter(prefix="/...")`

### Services
- **Format** : `{domain}[_{function}].py`
- **Exemples** : `dossiers_service.py`, `scenario_runner.py`, `vocabulary_loader.py`
- **Suffixe** : `_service.py` pour les services métier principaux

### Modèles
- **Format** : `models[_{category}].py`
- **Exemples** : `models.py`, `models_structure.py`, `models_scenarios.py`
- **Convention** : Classes SQLModel avec `table=True` pour tables DB

### Tests
- **Format** : `test_{feature}.py` ou `test_{domain}_{feature}.py`
- **Exemples** : `test_fhir_import.py`, `test_patient_workflow.py`
- **Organisation** : Par type de test (unit, integration, api, ui, etc.)

## Architecture et flux de données

```
┌─────────────────────────────────────────────────────────┐
│                      Browser / Client                    │
│                  (UI + API consumers)                    │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│                   FastAPI Application                    │
│  ┌──────────────────────────────────────────────────┐   │
│  │              Routers (62)                        │   │
│  │   UI routes + API routes + Admin routes          │   │
│  └───────────────────┬──────────────────────────────┘   │
│                      │                                   │
│                      ▼                                   │
│  ┌──────────────────────────────────────────────────┐   │
│  │              Services (80+)                       │   │
│  │   Business logic + HL7/FHIR + Scenarios          │   │
│  └───────────────────┬──────────────────────────────┘   │
│                      │                                   │
│                      ▼                                   │
│  ┌──────────────────────────────────────────────────┐   │
│  │           Models (17 fichiers)                   │   │
│  │   SQLModel entities + Pydantic schemas           │   │
│  └───────────────────┬──────────────────────────────┘   │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
         ┌───────────────────────────────────┐
         │      SQLite Database              │
         │      (medbridge.db)               │
         └───────────────────────────────────┘

Flux FHIR/HL7:
  Converters ←→ Services ←→ Models ←→ Database
  
Cache:
  Services ←→ Cache Service ←→ Redis (optionnel)
  
Monitoring:
  Middleware → Metrics → Dashboard
```

## Points d'entrée du code

### Application
- **Principal** : `app/app.py` - Fonction `create_app()` et instance FastAPI
- **Lifespan** : Gestion du cycle de vie (init DB, MLLP manager, scheduler)

### Base de données
- **Configuration** : `app/db.py` - Engine, sessions, sequences
- **Migrations** : `alembic/env.py` - Configuration Alembic
- **Initialisation** : Fonction `init_db()` dans `app/db.py`

### Configuration
- **Environnement** : Variables d'environnement (voir `.env.example`)
- **Paramètres** : `config/settings.py` (à créer) ou variables directes

### Tests
- **Configuration** : `tests/conftest.py` - Fixtures pytest globales
- **Exécution** : `pytest tests/` ou `pytest tests/{category}/`

## Bonnes pratiques

### Ajout de fonctionnalités

1. **Nouveau router** :
   - Créer fichier dans `app/routers/`
   - Définir `router = APIRouter(prefix="/...", tags=["..."])`
   - Inclure dans `app/app.py` : `app.include_router(module.router)`

2. **Nouveau service** :
   - Créer fichier dans `app/services/`
   - Définir classe de service avec méthodes métier
   - Importer dans router et utiliser

3. **Nouveau modèle** :
   - Ajouter dans fichier `models_*.py` approprié
   - Hériter de `SQLModel` avec `table=True` pour tables DB
   - Créer migration Alembic si structure DB change

4. **Nouveaux tests** :
   - Ajouter dans `tests/{category}/` selon type
   - Nommer `test_{feature}.py`
   - Utiliser fixtures de `conftest.py`

### Organisation du code

1. **Séparation des responsabilités** :
   - Routers : Endpoints HTTP, validation requêtes, réponses
   - Services : Logique métier, orchestration
   - Models : Entités DB, schémas Pydantic
   - Converters : Transformations entre formats

2. **Gestion des dépendances** :
   - Utiliser `Depends()` FastAPI pour injection
   - Session DB via `get_session`
   - Auth via `get_current_user`

3. **Gestion des erreurs** :
   - Lever `HTTPException` pour erreurs HTTP
   - Utiliser middleware `error_handler` pour centralisation
   - Logger les erreurs avec contexte

### Documentation

1. **Code** :
   - Docstrings pour toutes les fonctions publiques
   - Type hints pour tous les paramètres
   - Commentaires pour logique complexe

2. **API** :
   - Descriptions dans décorateurs de routes
   - Exemples de requêtes/réponses
   - Documentation OpenAPI automatique (`/docs`)

3. **Architecture** :
   - Mettre à jour ce fichier pour nouveaux modules
   - Documenter flux de données complexes
   - Maintenir CHANGELOG.md à jour

## Conventions de commit

- `feat:` - Nouvelle fonctionnalité
- `fix:` - Correction de bug
- `docs:` - Documentation uniquement
- `refactor:` - Refactoring sans changement fonctionnel
- `test:` - Ajout/modification de tests
- `chore:` - Tâches de maintenance

## Ressources externes

### Dépendances principales
- **FastAPI** : Framework web
- **SQLModel** : ORM (basé sur SQLAlchemy + Pydantic)
- **Jinja2** : Moteur de templates
- **Pytest** : Framework de tests
- **Alembic** : Migrations DB
- **Redis** : Cache (optionnel)
- **Playwright** : Tests UI (optionnel)

### Outils de développement
- **uvicorn** : Serveur ASGI
- **mypy** : Vérification types (optionnel)
- **black** : Formatage code (optionnel)
- **pytest-cov** : Couverture de code

---

**Document mis à jour** : 5 janvier 2026  
**Version du projet** : 1.0.0