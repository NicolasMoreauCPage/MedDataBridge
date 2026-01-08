
# Rapport de Couverture des Tests - 2025-12-22 10:38

## Métriques Globales
- **Couverture totale**: 42.6%
- **Lignes totales**: 25,343
- **Lignes couvertes**: 10,786
- **Lignes manquantes**: 14,557

## Modules Critiques (0% de couverture)
- app/routers/patients.py: 0%
- app/routers/context.py: 0%

## Priorité Haute (< 30% de couverture)
- app/routers/namespaces.py: 7%
- app/routers/fhir_export.py: 16%
- app/routers/ngap.py: 19%
- app/services/lpp_service.py: 16%
- app/services/scenario_status_service.py: 8%

## Priorité Moyenne (30-50% de couverture)
- app/routers/contacts.py: 21%
- app/routers/structure_hl7.py: 24%
- app/routers/fhir_import.py: 26%
- app/routers/ucd.py: 26%
- app/services/ucd_service.py: 22%


## Objectifs d'Amélioration

### Phase 1 (1-2 semaines)
- Corriger les erreurs de modèles DB (183 erreurs)
- Atteindre 60% de couverture globale
- Couvrir tous les modules critiques (0%)

### Phase 2 (2-4 semaines)
- Atteindre 75% de couverture globale
- Couvrir tous les modules haute priorité (< 30%)

### Phase 3 (1-2 mois)
- Atteindre 85% de couverture globale
- Ajouter tests d'intégration end-to-end
- Tests de performance et sécurité

## Recommandations Immédiates

1. **Corriger les modèles de base de données** pour éliminer les 183 erreurs
2. **Créer des tests unitaires** pour `patients.py` et `context.py`
3. **Ajouter des mocks appropriés** pour les services externes
4. **Séparer les tests unitaires** des tests d'intégration

---
*Rapport généré automatiquement par coverage_tracker.py*
