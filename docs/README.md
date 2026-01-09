# Documentation IntegraSanté

Ce dossier contient la documentation technique et fonctionnelle d'IntegraSanté.

## 📚 Documents disponibles

### Documentation technique principale

- **[PROGRAM_DOCUMENTATION.md](PROGRAM_DOCUMENTATION.md)** - Documentation complète du programme
  - Architecture générale de l'application
  - Composants clés et points d'entrée
  - Flux de données (FHIR, IHE PAM, MFN)
  - Modèles métier et services

### Guides spécifiques

- **[NAMESPACES_CLARIFICATION.md](NAMESPACES_CLARIFICATION.md)** - ⭐ Clarification des concepts de namespaces
  - Différence entre OID, URI et nom
  - HL7v2 : namespace = NOM + OID (reçu dans CX-4)
  - FHIR : namespace = URI uniquement (Identifier.system)
  - Exemples d'import/export pour chaque standard
  - Validation et auto-extraction

- **[API_REST_DOCUMENTATION.md](API_REST_DOCUMENTATION.md)** - Documentation de l'API REST
  - Endpoints disponibles
  - Schémas de requêtes/réponses
  - Exemples d'utilisation

- **[API_FHIR_STRUCTURE.md](API_FHIR_STRUCTURE.md)** - ⭐ API FHIR Structure (Location)
  - CRUD complet : GET/POST/PUT/DELETE `/fhir/Location`
  - Paramètres recherche FHIR (identifier, partof, status, name, type)
  - Conversion bidirectionnelle : DB ↔ FHIR R4
  - Cas d'usage : synchronisation SIH, navigation hiérarchique, export BI
  - Intégration avec Phases 4.1 (Import/Export) et 5.1 (UX Interactive)

### Organisation et cartographie

- **[PROJECT_ORGANIZATION.md](PROJECT_ORGANIZATION.md)** - Organisation du projet
  - Structure des dossiers et fichiers
  - Conventions de nommage
  - Arborescence détaillée

- **[MENU_MAP.md](MENU_MAP.md)** - Cartographie des routes
  - Routes de l'application web
  - Structure des menus
  - Navigation

### Fonctionnalités spécifiques

- **[COTATION_FONCTIONNELLE.md](COTATION_FONCTIONNELLE.md)** - Documentation de la cotation
  - CCAM, NGAP, UCD, LPP
  - Règles de cotation
  - Intégration avec les dossiers

### Refonte Interface Structure (2026)

- **[RECAPITULATIF_COMPLET.md](RECAPITULATIF_COMPLET.md)** - ⭐ Vue d'ensemble complète des phases
  - Résumé de toutes les phases accomplies
  - ~5000 lignes de code développées
  - Roadmap et prochaines étapes

- **[SPRINT1_DASHBOARD_STRUCTURE.md](SPRINT1_DASHBOARD_STRUCTURE.md)** - Phase 1: Dashboard
  - Visualisation hiérarchique (EG → Pôles → Services → UF/UH → Chambres → Lits)
  - Arbre interactif avec expand/collapse
  - Statistiques en temps réel

- **[SPRINT2_STRUCTURE_WIZARD_TEMPLATES.md](SPRINT2_STRUCTURE_WIZARD_TEMPLATES.md)** - Phase 2: Wizard
  - Création guidée en 3 étapes
  - 3 templates pré-configurés (Hôpital, Clinique, EHPAD)
  - Validation temps réel

- **[SPRINT3_MODE_GESTIONNAIRE.md](SPRINT3_MODE_GESTIONNAIRE.md)** - Phase 3.1: Analytics
  - Dashboard avec KPIs (occupation, DMS, rotation)
  - Graphiques Chart.js interactifs
  - Configuration alertes et export rapports (Excel/PDF/CSV)

- **[PHASE4_IMPORT_EXPORT.md](PHASE4_IMPORT_EXPORT.md)** - Phase 4.1: Spécifications Import/Export
  - Architecture et workflows détaillés
  - Format Excel (8 feuilles)
  - User stories et sprints

- **[PHASE4.1_IMPORT_EXPORT_COMPLETE.md](PHASE4.1_IMPORT_EXPORT_COMPLETE.md)** - ⭐ Phase 4.1: Documentation technique
  - Import/Export Excel complet (1100 LOC)
  - Validation Pydantic et transactions
  - Exemples code et API

- **[PHASE5_UX_MODERNE.md](PHASE5_UX_MODERNE.md)** - Phase 5.1: UX Interactive
  - Édition inline (double-clic)
  - Drag & drop avec SortableJS
  - Raccourcis clavier et opérations en masse

- **[PHASE4_GESTION_DROITS.md](PHASE4_GESTION_DROITS.md)** - Phase 4.2: Spécifications (TODO)
  - 6 rôles utilisateurs
  - Authentication JWT et audit logging
  - Matrice de permissions

- **[VALIDATION_NOUVELLES_IHMS.md](VALIDATION_NOUVELLES_IHMS.md)** - Validation technique
  - Vérification routes et accessibilité
  - Mapping complet des endpoints
  - Confirmation intégration menu

### Autres

- **[CHANGELOG.md](CHANGELOG.md)** - Historique des modifications
  - ⚠️ **À maintenir** : Mettre à jour régulièrement avec les nouvelles fonctionnalités

### 📦 Archive

Documents historiques conservés pour référence (non maintenus) :
- **[archive/](archive/)** - Documentation obsolète ou complétée
  - `TODO_UI_UX.md` - Refonte UI/UX (✅ terminée décembre 2025)
  - `VERSIONING_PROPOSAL.md` - Stratégie versioning (✅ appliquée)

## 🔍 Par où commencer ?

1. **Nouveaux développeurs** : Commencez par [PROGRAM_DOCUMENTATION.md](PROGRAM_DOCUMENTATION.md)
2. **Refonte Structure UX** : Consultez [RECAPITULATIF_COMPLET.md](RECAPITULATIF_COMPLET.md) pour une vue d'ensemble
3. **Intégration HL7v2/FHIR** : Consultez [NAMESPACES_CLARIFICATION.md](NAMESPACES_CLARIFICATION.md)
4. **API REST** : Voir [API_REST_DOCUMENTATION.md](API_REST_DOCUMENTATION.md)
5. **Structure du projet** : Référez-vous à [PROJECT_ORGANIZATION.md](PROJECT_ORGANIZATION.md)

## 📝 Standards supportés

- **FHIR R4** : Import/export de ressources (Patient, Encounter, Location, etc.)
- **HL7v2** : Messages ADT (IHE PAM), MFN (structure)
- **HPRIM** : Messages XML pour cotation et événements
- **IHE PAM France** : Profil d'intégration pour l'identité patient et mouvements
