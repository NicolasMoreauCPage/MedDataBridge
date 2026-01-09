"""
Tests E2E (End-to-End) pour Phase 5 - Interface Utilisateur Moderne

Ce module contient tous les tests end-to-end pour valider le bon fonctionnement
des interfaces utilisateur modernes implémentées dans la Phase 5.

Structure des tests:
├── conftest.py              - Configuration Playwright et fixtures communes
├── test_phase5_1_interactive.py  - Tests UX Interactive (/structure/interactive)
├── test_phase5_2_design_system.py - Tests Design System (/design-system)
├── test_phase5_3_search.py        - Tests Recherche Avancée (/structure/search)
├── test_integration_cross_phases.py - Tests d'intégration cross-phases
├── run_e2e_tests.py              - Script d'exécution avec options
└── pytest.ini                   - Configuration pytest E2E

Fonctionnalités testées:

Phase 5.1 - UX Interactive:
- Édition inline double-clic
- Drag & drop réorganisation
- Raccourcis clavier (Ctrl+A, Escape, Ctrl+E)
- Actions de masse avec sélection multiple
- Navigation et interactions fluides
- Design responsive (desktop/tablet/mobile)
- Gestion d'erreurs et performance

Phase 5.2 - Design System:
- Palette couleurs métier (7 niveaux hiérarchiques + 5 urgences)
- Composants JS réutilisables (StructureCard, SearchComponent, FilterComponent, etc.)
- Système de notifications
- Styles de boutons et cohérence visuelle
- Variables CSS et theming
- Accessibilité et navigation clavier

Phase 5.3 - Recherche Avancée:
- Recherche multi-critères via API FHIR Location
- Filtres avancés (type, statut, identifiant, FINESS)
- Pagination automatique avec navigation
- Historique des recherches dans localStorage
- Export des résultats au format JSON
- Statistiques temps réel
- Performance et responsive design
- Intégration API FHIR complète

Tests d'intégration cross-phases:
- Workflow utilisateur complet à travers toutes les phases
- Cohérence du Design System entre toutes les pages
- Navigation et menu consistants
- Cohérence des données entre interfaces
- Performance globale et accessibilité
- Compatibilité navigateurs simulée

Usage:

# Exécuter tous les tests E2E
python tests/e2e/run_e2e_tests.py

# Tests d'une phase spécifique
python tests/e2e/run_e2e_tests.py --phase 5.1
python tests/e2e/run_e2e_tests.py --phase 5.2
python tests/e2e/run_e2e_tests.py --phase 5.3
python tests/e2e/run_e2e_tests.py --phase integration

# Options avancées
python tests/e2e/run_e2e_tests.py --headless false --debug --record-video --report

# Via pytest directement
pytest tests/e2e/ -m e2e_phase5_1 -v
pytest tests/e2e/ -m e2e_phase5_2 -v
pytest tests/e2e/ -m e2e_phase5_3 -v
pytest tests/e2e/ -m e2e_integration -v

Configuration requise:
- Python 3.8+
- Playwright avec navigateur Chromium
- FastAPI server en cours d'exécution sur localhost:8000
- pytest-playwright, pytest-asyncio, pytest-html

Artifacts générés:
- Screenshots dans tests/artifacts/screenshots/
- Vidéos dans tests/artifacts/videos/ (si --record-video)
- Rapports HTML dans tests/artifacts/reports/ (si --report)
- Fichiers HAR dans tests/artifacts/ (si --record-har)

Les tests E2E valident l'expérience utilisateur complète et garantissent
que toutes les fonctionnalités Phase 5 fonctionnent correctement ensemble
dans un environnement proche de la production.
"""

__version__ = "1.0.0"
__author__ = "Phase 5 Development Team"
__description__ = "Tests E2E pour Phase 5 - Interface Utilisateur Moderne"