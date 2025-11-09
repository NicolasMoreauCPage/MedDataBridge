# Priorisation des Améliorations Techniques

_Date: 2025-11-09_
_Branche: `refonte-uiux-2025`_

## Critères de Priorisation

| Critère | Poids | Description |
|---------|-------|-------------|
| **Impact Utilisateur** | ×3 | Amélioration UX, stabilité, temps de réponse |
| **Dette Technique** | ×2 | Réduction warnings, maintenabilité, évolutivité |
| **Effort** | ÷ | Heures estimées (inverse: moins d'effort = priorité haute) |
| **Risque** | ÷ | Complexité, dépendances, potentiel de régression |

**Score = ((Impact × 3) + (Dette × 2)) / (Effort + Risque)**

---

## Tâches Évaluées

### 1. Réduction Warnings Critiques (TemplateResponse + SAWarnings)

**Objectif**: Éliminer 94% des warnings (351 → <20).

**Détail**:
- TemplateResponse: refactor 15-20 routes restantes (dossiers, patients, timeline)
- SAWarnings: disable autoflush local + audit cascades SQLModel

**Bénéfices**:
- Clarté logs → détection bugs plus rapide
- Conformité futures versions Starlette/SQLAlchemy
- CI/CD plus fiable (pas de noise warnings)

**Impact**: 7/10 (stabilité + maintenabilité)  
**Dette**: 9/10 (bloquant migration future)  
**Effort**: 5h  
**Risque**: 2/10 (changes isolés, tests en place)  
**Score**: **8.2** → **Priorité 1**

---

### 2. Indexation MessageLog pour Dashboard ACK

**Objectif**: Optimiser requêtes dashboard scénarios (statut ACK par endpoint/période).

**Détail**:
```sql
CREATE INDEX idx_messagelog_status_endpoint 
  ON messagelog(status, endpoint_id, created_at DESC);
CREATE INDEX idx_messagelog_correlation 
  ON messagelog(correlation_id) WHERE correlation_id IS NOT NULL;
```

**Bénéfices**:
- Temps requête dashboard: 2-3s → <300ms (estimé)
- Support volume croissant messages (>10k lignes)

**Impact**: 8/10 (UX dashboard critique)  
**Dette**: 4/10 (performance, pas bloquant immédiat)  
**Effort**: 1h (migration Alembic + test)  
**Risque**: 1/10 (ajout index = sans danger)  
**Score**: **10.0** → **Priorité 1 (égalité)**

---

### 3. Consolidation Admin (Suppression Route SQL Directe)

**Objectif**: Retirer lien `/sqladmin` de la navigation; centraliser via `/admin` gateway.

**Détail**:
- Navigation: supprimer item standalone SQLAdmin
- Gateway: ajouter liens vers `/sqladmin` + futurs outils admin (logs, config)
- Sécurité: documenter nécessité auth middleware (hors scope milestone actuel)

**Bénéfices**:
- UX cohérente (point d'entrée unique)
- Préparation intégration auth

**Impact**: 5/10 (UX mineure, pas critique)  
**Dette**: 6/10 (organisation, futur auth)  
**Effort**: 30 min (template edit + test)  
**Risque**: 1/10 (changement cosmétique)  
**Score**: **7.3** → **Priorité 2**

---

### 4. Extraction Macros Jinja Navigation

**Objectif**: Réduire duplication desktop/mobile menus (base.html).

**Détail**:
```jinja
{# macros/nav_item.html #}
{% macro nav_dropdown(label, icon, items, data_test) %}
  <li class="relative group" data-test-nav="{{ data_test }}">
    <button>{{ label }}</button>
    <div class="dropdown">
      {% for item in items %}
        <a href="{{ item.url }}">{{ item.label }}</a>
      {% endfor %}
    </div>
  </li>
{% endmacro %}
```

**Bénéfices**:
- DRY: 1 définition menu → 2 usages (desktop + mobile)
- Accessibilité: ARIA roles centralisés

**Impact**: 4/10 (maintenabilité)  
**Dette**: 7/10 (duplication actuelle = risque oubli sync)  
**Effort**: 2h (refactor + test UI)  
**Risque**: 3/10 (changement structure template)  
**Score**: **5.0** → **Priorité 3**

---

### 5. Performance: Index Mouvement.when + Venue.dossier_id

**Objectif**: Accélérer listes mouvements filtrées (par dossier/venue + tri chronologique).

**Détail**:
```sql
CREATE INDEX idx_mouvement_when ON mouvement(when DESC);
CREATE INDEX idx_mouvement_venue_when ON mouvement(venue_id, when DESC);
CREATE INDEX idx_venue_dossier ON venue(dossier_id);
```

**Bénéfices**:
- Requêtes `/mouvements?dossier_id=X`: 1-2s → <200ms
- Tri chronologique sans full scan

**Impact**: 7/10 (UX fréquente, utilisateurs actifs)  
**Dette**: 3/10 (perf, pas bloquant <1000 mouvements)  
**Effort**: 45 min (migration + validation)  
**Risque**: 1/10 (index = safe)  
**Score**: **7.8** → **Priorité 2**

---

### 6. Accessibilité: ARIA Landmarks Complets

**Objectif**: Ajouter `role="navigation"`, `aria-label` cohérents sur toutes pages.

**Détail**:
- Navigation: `<nav role="navigation" aria-label="Menu principal">`
- Main: `<main role="main">`
- Formulaires: `aria-describedby` pour hints

**Bénéfices**:
- Conformité WCAG 2.1 AA
- Meilleure expérience lecteurs écran

**Impact**: 6/10 (accessibilité = obligation légale à terme)  
**Dette**: 5/10 (qualité, pas technique)  
**Effort**: 3h (audit + corrections)  
**Risque**: 1/10 (ajouts attributs = sans risque)  
**Score**: **5.7** → **Priorité 3**

---

### 7. Documentation Milestone Scénarios (README Section)

**Objectif**: Documenter usage scénarios (replay, capture dossier, preview identifiants).

**Détail**:
- README.md: Section "Scénarios de Non-Régression"
- Guide opérateur: Procédure capture dossier → export JSON
- API Reference: Endpoints `/scenarios/*`

**Bénéfices**:
- Onboarding nouveaux utilisateurs
- Réduction support questions récurrentes

**Impact**: 5/10 (utilisabilité future)  
**Dette**: 4/10 (doc = faible couplage code)  
**Effort**: 2h (rédaction + exemples)  
**Risque**: 0/10 (doc = sans risque)  
**Score**: **4.5** → **Priorité 4**

---

### 8. Tests: Couverture Scénarios Avancés

**Objectif**: +10 tests couvrant date shifting, identifier replacement, ACK aggregation.

**Détail**:
- `test_scenario_date_coherence.py`: validation séquence A01→A02 gaps temporels
- `test_identifier_namespaces.py`: préfixes custom, collisions, tracking
- `test_ack_dashboard.py`: agrégation statuts par endpoint

**Bénéfices**:
- Confiance milestone scénarios
- Détection régression rapide

**Impact**: 6/10 (qualité, prévention bugs)  
**Dette**: 7/10 (couverture actuelle insuffisante domaine scénarios)  
**Effort**: 4h (écriture tests + fixtures)  
**Risque**: 2/10 (tests = safe, mais effort découverte edge cases)  
**Score**: **5.4** → **Priorité 3**

---

## Synthèse & Recommandation

### Ordre d'Exécution (Milestones Courts)

#### **Sprint 1 (Pré-merge main)** — 7h total
1. ✅ **Réduction warnings** (5h) → Score 8.2
   - Cible: <20 warnings totaux
2. ✅ **Index MessageLog** (1h) → Score 10.0
   - Dashboard ACK rapide
3. ✅ **Consolidation Admin** (30m) → Score 7.3
   - UX cohérente
4. ✅ **Index Mouvement/Venue** (45m) → Score 7.8
   - Performance listes

**Livrable**: Branche `refonte-uiux-2025` prête pour merge main (tests verts, <20 warnings, dashboards réactifs).

---

#### **Sprint 2 (Post-merge, début milestone scénarios)** — 5h total
5. Macros Jinja Navigation (2h) → Score 5.0
6. Accessibilité ARIA (3h) → Score 5.7

---

#### **Sprint 3 (Pendant dev scénarios)** — 6h total
7. Tests Scénarios Avancés (4h) → Score 5.4
8. Documentation README (2h) → Score 4.5

---

### Jalons de Validation

| Jalon | Critère | Date Cible |
|-------|---------|------------|
| Sprint 1 done | Warnings <20, tests passés, perf +70% | Avant merge main |
| Sprint 2 done | Navigation DRY, ARIA complet | Semaine 1 milestone |
| Sprint 3 done | Couverture tests >85%, doc complète | Semaine 2 milestone |

---

## KPI Post-Implémentation

| KPI | Baseline | Cible Sprint 1 | Cible Sprint 3 |
|-----|----------|-----------------|----------------|
| Warnings totaux | 351 | <20 | <10 |
| Dashboard load time | 2-3s | <300ms | <200ms |
| Liste mouvements (1000 items) | 1-2s | <200ms | <150ms |
| Couverture tests scénarios | ~5 tests | 5 tests | >15 tests |
| Score accessibilité (audit manuel) | 60% | 65% | 85% |

---

_Fin du plan de priorisation. Prochaine action: exécuter Sprint 1 (tâches 1-4)._
