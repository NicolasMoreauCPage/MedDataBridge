# Menu Map — MedData Bridge

Ce fichier répertorie la carte complète des menus et routes de l'application MedData Bridge.

> **Mise à jour** : Janvier 2026 - Documentation complète basée sur 62 routers existants.

> Note: certaines entrées sont conditionnelles (ex. filtrées par contexte GHT / EJ / patient). Les routes indiquées correspondent aux prefixes des routers dans `app/routers/`.

## Organisation des routes

L'application MedData Bridge est structurée autour de **200+ endpoints** répartis dans **62 routers**. Les routes sont organisées par domaine fonctionnel.

## Navigation principale (bureau)

- Structure (visible si `ght_context`):
  - Tableau structurel: `/structure`
  - Contexts GHT (admin): `/admin/ght`
  - Namespaces GHT: `/{context_id}/namespaces`
  - Recherche avancée: `/structure/search`
  - Export/Import structure HL7: `/structure/hl7`
  - Structure FHIR: `/fhir/structure`
  - Entités (grouped):
    - Entités géographiques: `/structure/eg`
    - Pôles: `/structure/poles`
    - Services: `/structure/services`
    - UF: `/structure/ufs`
    - UH: `/structure/uh`
    - Chambres: `/structure/chambres`
    - Lits: `/structure/lits`

- Activités (visible si `ght_context`):
  - Patients: `/patients`
  - Dossiers & Cotation: `/dossiers`
  - Types de dossiers: `/dossier-type`
  - Venues: `/venues` (optionnel `?dossier_id=`)
  - Mouvements: `/mouvements` (optionnel `?venue_id=` ou `?dossier_id=`)
  - API Mouvements: `/mouvements/api` (AJAX)
  - API Structure (mouvements): `/api/mouvements`

- Interopérabilité:
  - Tous les messages: `/messages`
  - Par dossier: `/messages/by-dossier`
  - Messages rejetés: `/messages/rejections`
  - Envoi de message: `/messages/send`
  - Validation HL7: `/validation`
  - Conformité IHE: `/conformity`
  - Fichiers de test HPRIM: `/hprim/test-files`
  - Roundtrip HPRIM: `/roundtrip-hprim`
  - Scénarios IHE PAM: `/scenarios`
  - Import HPRIM: `/hprim/import`
  - Import d'exemples: `/import`
  - Cotation moderne: `/cotation-modern`
  - Endpoints (gestion): `/endpoints`
  - Génération de messages test: `/generate`
  - Tests d'interopérabilité: `/interop`
  - Interface testing (GAM/GAP): `/interface-testing` et `/ui/interface-testing`
  - Profils IHE: `/ihe`
  - Workflows d'interopérabilité: `/workflow`
  - Boîte de réception FHIR: `/inbox/fhir`
  - API FHIR export: `/api/fhir` (export)
  - API FHIR import: `/api/fhir` (import)

- Ressources / Documentation:
  - Guide utilisateur: `/guide`
  - Documentation API: `/api-docs`
  - FHIR (site externe): https://www.hl7.org/fhir/
  - Index Documentation: `/documentation`
  - Docs programme / architecture / API / utilisateur / modèles: `/docs/PROGRAM_DOCUMENTATION.md`, `/docs/architecture.md`, `/docs/api_guide.md`, `/docs/user_guide.md`, `/docs/models_reference.md`
  - FHIR API (markdown): `/docs/FHIR_API.md`

- Outils & Exemples:
  - Authentification: `/auth/login`, `/auth/logout`
  - Exemples HL7 v2: `/examples/hl7v2`
  - Exemples MFN: `/examples/mfn`
  - Bundles FHIR: `/examples/fhir-bundles`
  - Endpoints de test internes: `/tools/endpoints-test`
  - Guide MLLP: `/tools/mllp`
  - UCD (Unité Commune de Dispensation): `/ucd`
  - LPP (Liste des Produits et Prestations): `/lpp`
  - CCAM (Classification des Actes Médicaux): `/ccam`

- Scénarios (section dédiée):
  - Scénarios d'interopérabilité: `/scenarios`
  - Templates de scénarios: `/scenarios/templates`
  - Dashboard des exécutions: `/scenarios/runs`
  - Configuration UF / Médecins par EJ: `/config/scenario-ej`
  - Documentation scénarios: `/docs/SCENARIOS_DOCUMENTATION.md`
  - Générateur de scénarios de test: `/test-scenario-generator`
  - UI scénarios de test: `/ui/test-scenarios`

- Administration:
  - Interface d'administration SQL: `/sqladmin` (ou `/admin` selon contexte)
  - API admin protégée: `/api/admin`
  - Vocabularies (listes de valeurs): `/vocabularies`
  - Dashboard principal: `/dashboard`
  - Cache Redis: `/cache-dashboard`
  - Cache API: `/cache`
  - Métriques opérations: `/metrics/dashboard`
  - API Métriques: `/api/metrics`
  - Gestion des tâches: `/tasks`
  - Debug événements (dev only): `/debug`

- Footer quicklinks (select):
  - Documentation: `/documentation`
  - API: `/api/docs`
  - Signaler un problème (mailto): `mailto:nicolas.moreau@cpage.fr`


## Menu mobile

Le menu mobile contient des raccourcis similaires :
- Tableau de bord `/`
- Dossiers & Cotation `/dossiers`
- Messages `/messages` (si `ght_context`)
- Patients, Dossiers, Venues, Mouvements, Formulaires
- Structure (tableau / admin / recherche / entités spécifiques)
- Interopérabilité (Messages, Injecter HL7/FHIR `/messages/send`, Endpoints `/endpoints`, Scénarios `/scenarios`)
- Ressources (Guide `/guide`, API docs `/api-docs`, documentation technique)


## Références aux templates et routers
- Template principal contenant la navigation: `app/templates/base.html`
- Composants et macros: `app/templates/components.html` et `app/templates/components/` (macros)
- Routage d'exemples: voir `app/routers/` pour les routers exposant les pages listées ci-dessus (ex. `app/routers/scenarios.py`, `app/routers/messages.py`, `app/routers/endpoints.py`)


## Notes
- Cette documentation liste **tous les routers existants** (62 au total, ~200+ endpoints).
- Les routes API sont préfixées par `/api/` pour la plupart.
- Les routes UI utilisent souvent `/ui/` ou sont directement à la racine.
- Certaines routes peuvent exister en plusieurs copies (déploiement vs. app) dans `deployment/*/app/routers` et `deployment/*/app/templates`.
- Quelques entrées nécessitent un contexte (GHT/EJ/Patient) et peuvent être masquées ou annotées d'un avertissement dans l'interface.
- Pour la liste complète des endpoints avec méthodes HTTP, consulter `/api/docs` (OpenAPI).

## Routes par catégorie détaillée

### Cœur métier
- **Patients** : `/patients` - CRUD complet des patients
- **Dossiers** : `/dossiers` - Gestion des dossiers médicaux
- **Venues** : `/venues` - Gestion des séjours hospitaliers
- **Mouvements** : `/mouvements` - Mouvements intra-hospitaliers (admissions, transferts, sorties)
- **Contacts** : `/contacts` - Contacts patients et venues
- **Timeline** : `/timeline` - Vue chronologique des événements

### Structure hospitalière
- **Structure globale** : `/structure` - Hiérarchie complète (EG, Pôles, Services, UF, UH, Chambres, Lits)
- **Structure FHIR** : `/fhir/structure` - Locations et Organizations FHIR
- **Structure HL7** : `/structure/hl7` - Export/Import MFN M05
- **GHT** : `/admin/ght`, `/{context_id}/namespaces` - Contextes et namespaces GHT
- **Types de dossiers** : `/dossier-type` - Configuration des types de dossiers

### Interopérabilité
- **Messages** : `/messages` - Historique, recherche, rejeu de messages HL7/FHIR
- **Endpoints** : `/endpoints` - Configuration FILE, MLLP, REST
- **Transport** : `/transport` - Monitoring et logs de transport
- **IHE PAM** : `/ihe` - Profils IHE (PAM, PIX, PDQ)
- **FHIR Export** : `/api/fhir` (export) - Génération de bundles et ressources FHIR
- **FHIR Import** : `/api/fhir` (import) - Import de bundles FHIR
- **FHIR Inbox** : `/inbox/fhir` - Boîte de réception FHIR
- **Génération** : `/generate` - Génération de messages test
- **Validation** : `/validation` - Validation HL7/FHIR
- **Conformité** : `/conformity` - Vérification de conformité IHE
- **Workflows** : `/workflow` - Workflows d'interopérabilité

### Scénarios de test
- **Scénarios** : `/scenarios` - Gestion complète des scénarios IHE PAM
- **Templates** : `/scenarios/templates` - Templates contextualisables
- **Exécutions** : `/scenarios/runs` - Dashboard des exécutions
- **Configuration EJ** : `/config/scenario-ej` - Configuration UF et médecins par EJ
- **Générateur** : `/test-scenario-generator` - Génération automatique
- **Interface de test** : `/interface-testing`, `/ui/interface-testing` - Tests GAM/GAP
- **UI Test Scenarios** : `/ui/test-scenarios` - Interface UI pour scénarios

### Cotation et nomenclatures
- **Cotation moderne** : `/cotation-modern` - Interface de cotation moderne
- **Sélecteur** : `/cotation-modern/selector` - Sélection de dossiers pour cotation
- **CCAM** : `/ccam` - Classification Commune des Actes Médicaux
- **UCD** : `/ucd` - Unité Commune de Dispensation (médicaments)
- **LPP** : `/lpp` - Liste des Produits et Prestations
- **NGAP** : (via services) - Nomenclature Générale des Actes Professionnels

### Administration et monitoring
- **SQLAdmin** : `/sqladmin`, `/admin` - Interface d'administration SQL
- **Admin API** : `/api/admin` - API admin protégée
- **Vocabulaires** : `/vocabularies` - Gestion des vocabulaires et mappages
- **Cache** : `/cache`, `/cache-dashboard` - Gestion du cache Redis
- **Métriques** : `/metrics/dashboard`, `/api/metrics` - Métriques et monitoring
- **Tâches** : `/tasks` - Gestion de tâches asynchrones
- **Debug** : `/debug` - Debug événements (dev only)
- **Health** : `/health` - Health checks
- **Contextes** : `/context` - Gestion des contextes GHT/EJ

### Documentation et outils
- **Guide** : `/guide` - Guide utilisateur interactif
- **API Docs** : `/api/docs`, `/docs` - Documentation OpenAPI
- **Documentation** : `/documentation` - Index de documentation
- **Documentation métier** : `/docs/*.md` - Fichiers markdown
- **Import** : `/import` - Import d'exemples et données de test
- **Roundtrip HPRIM** : `/roundtrip-hprim` - Tests roundtrip HPRIM
- **Authentification** : `/auth` - Login, logout, JWT

---
_Généré automatiquement à partir de `app/templates/base.html` le 24 décembre 2025._
