# Documentation MedData Bridge

Ce dossier contient la documentation technique et fonctionnelle de MedData Bridge.

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
2. **Intégration HL7v2/FHIR** : Consultez [NAMESPACES_CLARIFICATION.md](NAMESPACES_CLARIFICATION.md)
3. **API REST** : Voir [API_REST_DOCUMENTATION.md](API_REST_DOCUMENTATION.md)
4. **Structure du projet** : Référez-vous à [PROJECT_ORGANIZATION.md](PROJECT_ORGANIZATION.md)

## 📝 Standards supportés

- **FHIR R4** : Import/export de ressources (Patient, Encounter, Location, etc.)
- **HL7v2** : Messages ADT (IHE PAM), MFN (structure)
- **HPRIM** : Messages XML pour cotation et événements
- **IHE PAM France** : Profil d'intégration pour l'identité patient et mouvements
