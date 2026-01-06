# Changelog - MedData Bridge

Toutes les modifications notables apportées à MedData Bridge seront documentées dans ce fichier.

Le format est basé sur [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
et ce projet respecte [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### 📝 Documentation
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

### ✨ Fonctionnalités
- **Gestion des namespaces améliorée** (2026-01-06)
  - Auto-extraction OID depuis URI FHIR
  - Auto-génération du nom HL7v2 si non fourni
  - Validation avec regex et cohérence URI/OID
  - UI redesignée avec badges FHIR (vert) et HL7v2 (bleu)
  - Aide contextuelle avec exemples concrets

### 🐛 Correctifs
- **Validation des namespaces** (2026-01-06)
  - Permet maintenant même URI pour types différents (IPP/NDA/MVT)
  - Messages d'erreur plus clairs lors de la création
  - Gestion des erreurs avec rollback et flash messages

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