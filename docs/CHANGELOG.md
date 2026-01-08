# Changelog - MedData Bridge

Toutes les modifications notables apportées à MedData Bridge seront documentées dans ce fichier.

Le format est basé sur [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
et ce projet respecte [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### ✨ Fonctionnalités
- **Phase 6: Dossiers, Venues & Mouvements** (2026-01-08)
  - Refonte complète des IHMs Dossiers & Venues (headers contextuels, listes modernisées, wizard d'admission en 3 étapes)
  - Filtres avancés unifiés sur les listes (dossiers, venues, mouvements) avec raccourcis clavier globaux (Ctrl+N, Ctrl+S, /, Esc)
  - Workflow mouvements moderne par venue (cartes d'événements, timeline chronologique, sélecteur hiérarchique de lits avec recherche)
  - Plan de lits interactif par service/UF/UH/chambre avec KPIs d'occupation, statuts couleur, actions rapides (affecter, muter, voir venue)
  - Détection des conflits de lits (plusieurs venues actives sur un même lit) avec mise en évidence visuelle et point d'entrée dédié pour résolution

- **Phase 4.1: Import/Export Excel Structure** (2026-01-08)
  - Import/Export complet de la structure hospitalière via Excel (8 feuilles)
  - POST `/api/structure/import/excel` : Preview avec validation Pydantic
  - POST `/api/structure/import/confirm` : Import transactionnel avec rollback
  - 3 modes d'import : create, update, replace
  - Interface Dropzone.js avec preview détaillée et gestion erreurs
  - Documentation technique complète : [PHASE4.1_IMPORT_EXPORT_COMPLETE.md](PHASE4.1_IMPORT_EXPORT_COMPLETE.md)

- **Phase 5.1: UX Interactive Moderne** (2026-01-08)
  - Édition inline avec double-clic (PATCH `/api/structure/interactive/{type}/{id}`)
  - Drag & drop avec SortableJS (POST `/api/structure/interactive/move`)
  - Raccourcis clavier (Ctrl+N/E/D/F, Del, Esc, ?)
  - Opérations en masse (POST `/api/structure/interactive/bulk-update`)
  - Duplication d'entités (POST `/api/structure/interactive/duplicate`)
  - Page démo interactive : `/structure/interactive`
  - Documentation : [PHASE5_UX_MODERNE.md](PHASE5_UX_MODERNE.md)

- **Phase 3.1: Mode Gestionnaire** (2026-01-08)
  - Dashboard analytics avec KPIs temps réel
  - 4 endpoints analytics : kpis, capacity-by-service, capacity-by-um, alerts
  - Configuration des alertes (seuils d'occupation)
  - Export rapports Excel/PDF/CSV
  - Graphiques interactifs Chart.js
  - Documentation : [SPRINT3_MODE_GESTIONNAIRE.md](SPRINT3_MODE_GESTIONNAIRE.md)

- **Phases 1-2: Dashboard et Wizard Structure** (2026-01-08)
  - Dashboard structure avec arbre hiérarchique (EG → Pôles → Services → UF/UH → Chambres → Lits)
  - Wizard de création en 3 étapes avec templates (Hôpital, Clinique, EHPAD)
  - CRUD complet pour toutes les entités
  - Validation temps réel et calculs automatiques
  - Documentation : [SPRINT1_DASHBOARD_STRUCTURE.md](SPRINT1_DASHBOARD_STRUCTURE.md), [SPRINT2_STRUCTURE_WIZARD_TEMPLATES.md](SPRINT2_STRUCTURE_WIZARD_TEMPLATES.md)

- **Interface visualisation et import actes HPRIM** (2026-01-07)
  - Nouveau router `/hprim-cotation` pour visualiser les messages HPRIM de cotation reçus
  - Dashboard avec filtres par statut et recherche par NDA/IPP
  - Vue détaillée des messages avec parsing XML et affichage des actes (CCAM, NGAP, UCD, LPP)
  - Routes d'import pour intégrer les actes dans les tables CCAMAct, NGAPAct, UCDAct, LPPAct
  - Détection automatique des doublons lors de l'import
  - Association automatique des actes aux dossiers via le NDA
  - Templates responsive avec statistiques et boutons d'import par type d'acte

- **Gestion des namespaces améliorée** (2026-01-06)
  - Auto-extraction OID depuis URI FHIR
  - Auto-génération du nom HL7v2 si non fourni
  - Validation avec regex et cohérence URI/OID
  - UI redesignée avec badges FHIR (vert) et HL7v2 (bleu)
  - Aide contextuelle avec exemples concrets

### 🐛 Correctifs
- **Correction StaleDataError dans file_poller.py** (2026-01-07)
  - Utilisation de `session.merge()` au lieu de `session.add()` après `rollback()`
  - Évite les erreurs de concurrence lors de la mise à jour du statut MessageLog
  - Meilleure gestion des objets détachés de la session SQLAlchemy
  - Correction appliquée aux handlers d'exception ADT et MFN

- **Validation des namespaces** (2026-01-07)
  - Permet maintenant même URI pour types différents (IPP/NDA/MVT)
  - Vérification combinée `system + type` au lieu de `system` seul
  - Messages d'erreur plus clairs lors de la création
  - Gestion des erreurs avec rollback et flash messages
  - Logs détaillés pour le débogage

### 📝 Documentation
- **Phase 6 – Dossiers, Venues & Mouvements** (2026-01-08)
  - Guide utilisateur Phase 6 : [PHASE6_GUIDE_UTILISATEUR.md](PHASE6_GUIDE_UTILISATEUR.md)
  - Notes techniques Phase 6 (filtres, raccourcis, architecture) : [PHASE6_NOTES_TECHNIQUES.md](PHASE6_NOTES_TECHNIQUES.md)
  - Synthèse mouvements & plan de lits : [PHASE6_MOUVEMENTS_LITS_GLOBAL.md](PHASE6_MOUVEMENTS_LITS_GLOBAL.md)

- **Clarification des namespaces** (2026-01-06)
  - Nouveau guide `NAMESPACES_CLARIFICATION.md` expliquant OID/URI/nom
  - Distinction claire : HL7v2 (NOM+OID) vs FHIR (URI uniquement)
  - Exemples d'import/export pour chaque standard
  - Documentation indexée dans `docs/README.md`

- **Refonte de la documentation** (2026-01-06)
  - Création de `docs/README.md` comme index central
  - Archivage des documents obsolètes (`TODO_UI_UX.md`, `VERSIONING_PROPOSAL.md`)
  - Liens croisés entre documents améliorés
  - Structure docs/ clarifiée et maintenue

## [1.0.0] - 2025-12-26

### 🎉 Release Notes
**MedData Bridge atteint la version stable 1.0.0 !** Après plus de 4 mois de développement actif avec 272 commits, cette version marque la maturité production-ready du système d'interopérabilité médicale.

### ✨ Fonctionnalités Majeures
- **Refonte complète UI/UX** : Interface moderne avec thème sombre, animations fluides et composants DaisyUI
- **Système de facturation médicale avancé** : Recherche, pagination et gestion complète des cotations médicales
- **Système d'héritage intelligent** : Gestion automatique des structures médicales avec héritage physique et opérationnel
- **Scénarios intégrés HL7/HPRIM** : Base de données de scénarios consolidée pour les tests et la démonstration
- **Recherche et sélecteurs améliorés** : Expérience utilisateur optimisée avec recherche intelligente

### 🏗️ Infrastructure Production
- **Design responsive moderne** : Interface adaptative pour tous les appareils
- **Suite de tests robuste** : Tests unitaires et d'intégration complets
- **Configurations de déploiement** : Docker, scripts de déploiement et environnements de production
- **Documentation exhaustive** : Guides utilisateur, API et architecture technique
- **Gestion de version automatisée** : Scripts de versioning et changelog intégré

### 🔄 Changements depuis 1.0.0-alpha.1
- **Stabilité production** : Passage en version stable après validation complète
- **Documentation de release** : Notes de version détaillées et stratégie de versioning
- **Optimisations finales** : Performance et stabilité pour l'environnement de production

### 📦 Compatibilité
- **Migration transparente** : Aucune rupture depuis la version alpha
- **API stable** : Contrats d'interface maintenus pour la compatibilité
- **Base de données** : Migrations fluides et préservation des données

### 🎯 Objectifs Atteints
Cette release positionne MedData Bridge comme solution prête pour la production dans les workflows d'interopérabilité de santé, avec une interface moderne et des fonctionnalités complètes pour la gestion des données médicales.

## [1.0.0-alpha.1] - 2025-12-26

### ✨ Ajouté
- **Système de versioning** : Fichier VERSION et changelog intégré
- **Footer moderne** : Avec version, liens documentation et contact
- **Logo corrigé** : Variables CSS accent-alt restaurées pour le gradient du logo
- **Organisation des fichiers** : Scripts, logs et fichiers temporaires réorganisés
- **Documentation complète** : Structure de projet documentée dans docs/

### 🔧 Modifié
- **Refactoring UI/UX complet** : 50 tâches accomplies sur l'interface utilisateur
- **Templates corrigés** : Pages de dashboard LPP et UCD créées
- **Macros Jinja2** : Imports corrigés dans base.html
- **Structure de projet** : Organisation logique des dossiers

### 🐛 Corrigé
- **Logo header vide** : Classes CSS accent et accent-alt restaurées
- **Templates manquants** : lpp/dashboard.html et ucd/dashboard.html créés
- **Imports de macros** : Erreurs de syntaxe Jinja2 corrigées
- **Tests de rendu** : Validation des templates restaurée

### 📚 Documentation
- **docs/PROJECT_ORGANIZATION.md** : Structure complète du projet
- **docs/TODO_UI_UX.md** : Liste des tâches UI/UX finalisée
- **docs/CHANGELOG.md** : Historique des versions (ce fichier)

### 🏗️ Infrastructure
- **Organisation des scripts** : scripts/maintenance/ et scripts/analysis/
- **Logs centralisés** : Dossier logs/ pour tous les fichiers de log
- **Fichiers temporaires** : Dossier temp/ pour les fichiers éphémères

## [1.0.0-alpha.0] - 2025-12-01

### ✨ Ajouté
- **Application FastAPI** : Framework principal avec routes et modèles
- **Interface web moderne** : Templates Jinja2 avec Tailwind CSS
- **Base de données** : Modèles SQLAlchemy avec migrations Alembic
- **API REST** : Endpoints pour la gestion des données médicales
- **Interfaçage HL7/FHIR** : Adaptateurs pour l'interopérabilité
- **Tests unitaires** : Suite de tests avec pytest
- **Documentation** : README et guides utilisateur

### 🏗️ Infrastructure
- **Configuration** : Paramètres d'environnement et settings
- **Déploiement** : Docker et configurations de production
- **CI/CD** : Workflows GitHub Actions
- **Sécurité** : Authentification et autorisations

---

## Types de changements
- `✨ Ajouté` pour les nouvelles fonctionnalités
- `🔧 Modifié` pour les changements aux fonctionnalités existantes
- `🐛 Corrigé` pour les corrections de bugs
- `🗑️ Supprimé` pour les fonctionnalités supprimées
- `📚 Documentation` pour les changements de documentation
- `🏗️ Infrastructure` pour les changements d'infrastructure

## Versions
- **MAJEURE.MINORE.CORRECTIVE** selon [Semantic Versioning](https://semver.org/)
- **alpha/beta/rc** pour les pré-versions