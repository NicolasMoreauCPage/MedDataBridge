# 📊 Sprint 3.1 : Mode Gestionnaire - Analytics & KPIs

## 🎯 Objectif
Créer une interface dédiée aux **gestionnaires d'établissement** avec vue analytics, KPIs temps réel, graphiques de capacité et alertes de gestion.

---

## 📋 Fonctionnalités Principales

### 1. Dashboard Analytics
**Route** : `/structure/analytics` ou onglet "Analytics" dans `/structure`

#### KPIs Temps Réel
- **Taux d'occupation global** : Lits occupés / Lits disponibles (%)
- **Durée Moyenne de Séjour (DMS)** : Moyenne des durées de séjour par UF/Service
- **Taux de rotation** : Nombre admissions / Nombre lits
- **Capacité disponible** : Nombre lits libres par type (MCO, SSR, PSY, HAD)
- **Taux d'ouverture lits** : Lits ouverts / Lits installés

#### Période de référence
- Sélecteur : Aujourd'hui / 7 jours / 30 jours / Année en cours
- Comparaison avec période précédente (évolution %)

### 2. Graphiques de Capacité

#### Vue par Service
- **Graphique horizontal** : Capacité vs Occupation par service
- **Code couleur** : 
  - 🟢 Vert : < 80% occupation
  - 🟡 Jaune : 80-95% occupation
  - 🔴 Rouge : > 95% occupation

#### Vue par Type d'Activité (UM)
- **Pie chart** : Répartition lits MCO / SSR / PSY / HAD
- **Bar chart** : Évolution occupation sur période

#### Vue par Pôle
- **TreeMap** : Capacité proportionnelle par pôle → services
- **Drill-down** : Clic sur pôle → détail services/UF

### 3. Alertes & Seuils

#### Alertes Automatiques
- 🚨 **Suroccupation** : Service > 100% occupation (lits supplémentaires)
- ⚠️ **Tension** : Service > 95% occupation
- 💤 **Sous-utilisation** : Service < 50% occupation pendant 7 jours
- ⏰ **DMS anormale** : DMS > 150% de la médiane du service

#### Configuration Seuils
- Interface admin pour définir seuils par type UM
- Notifications par email/webhook (optionnel Phase 3.2)

### 4. Export Rapports Direction

#### Formats disponibles
- **Excel** : Tableaux croisés dynamiques (capacité, occupation, DMS)
- **PDF** : Rapport formaté avec graphiques
- **CSV** : Données brutes pour analyse externe

#### Rapports pré-configurés
- Rapport mensuel direction (KPIs + graphiques)
- Rapport occupation hebdomadaire
- Rapport audit capacité (lits installés vs ouverts vs occupés)

---

## 🏗️ Architecture Technique

### Backend (FastAPI)

#### Nouveaux Endpoints

```python
# app/routers/analytics.py

GET /api/analytics/kpis
- Query params: ?period=7d|30d|1y&eg_id=123
- Response: { occupation_rate, dms, rotation_rate, available_beds, ... }

GET /api/analytics/capacity-by-service
- Query params: ?eg_id=123
- Response: [{ service_name, total_beds, occupied_beds, rate }]

GET /api/analytics/capacity-by-um
- Query params: ?eg_id=123
- Response: [{ um_code, label, total_beds, occupied_beds }]

GET /api/analytics/alerts
- Query params: ?eg_id=123&severity=all|high|medium|low
- Response: [{ type, service_name, value, threshold, message }]

POST /api/analytics/export
- Body: { format: "excel"|"pdf"|"csv", report_type, eg_id, period }
- Response: File download (stream)
```

#### Modèles de données

```python
# Nouvelles tables (optionnel - peut être calculé à la volée)
class OccupationSnapshot(SQLModel, table=True):
    """Snapshot quotidien de l'occupation pour historique"""
    id: Optional[int]
    date: date
    lit_id: int
    is_occupied: bool
    eg_id: int

class AlertRule(SQLModel, table=True):
    """Configuration des seuils d'alerte"""
    id: Optional[int]
    type: str  # "suroccupation", "sous_utilisation", "dms_anormale"
    threshold_value: float
    um_code: Optional[str]  # Si null = tous les UM
    is_active: bool
```

### Frontend (HTML/JS)

#### Template principal
- `app/templates/analytics_dashboard.html` : Dashboard analytics complet
- Sections : KPIs cards, graphiques, alertes, exports

#### Bibliothèques JS
- **Chart.js** : Graphiques (pie, bar, line, horizontal bar)
- **ApexCharts** (alternative) : Graphiques plus avancés + animations
- Pas de framework lourd (rester vanilla JS comme existant)

#### Structure HTML
```html
<div class="analytics-container">
  <div class="kpis-grid">
    <!-- 5 cartes KPIs avec icônes et trends -->
  </div>
  
  <div class="charts-section">
    <div class="chart-card">
      <h3>Capacité par Service</h3>
      <canvas id="capacityByServiceChart"></canvas>
    </div>
    <div class="chart-card">
      <h3>Répartition par Type UM</h3>
      <canvas id="umDistributionChart"></canvas>
    </div>
  </div>
  
  <div class="alerts-section">
    <h3>🚨 Alertes Actives</h3>
    <div id="alertsList"><!-- Liste d'alertes --></div>
  </div>
  
  <div class="export-section">
    <button class="btn-export" data-format="excel">📊 Export Excel</button>
    <button class="btn-export" data-format="pdf">📄 Export PDF</button>
    <button class="btn-export" data-format="csv">📋 Export CSV</button>
  </div>
</div>
```

---

## 📝 Plan de Développement

### Sprint 3.1.1 : KPIs & Backend _(1-2 jours)_
- [x] Création document de sprint
- [ ] Créer modèles `OccupationSnapshot` et `AlertRule`
- [ ] Migration Alembic pour nouvelles tables
- [ ] Endpoint `GET /api/analytics/kpis` avec calculs
- [ ] Endpoint `GET /api/analytics/capacity-by-service`
- [ ] Endpoint `GET /api/analytics/capacity-by-um`
- [ ] Tests unitaires des endpoints analytics

### Sprint 3.1.2 : Interface Dashboard _(2-3 jours)_
- [ ] Template `analytics_dashboard.html` avec structure HTML
- [ ] 5 cartes KPIs avec styles et icônes
- [ ] Intégration Chart.js
- [ ] Graphique capacité par service (horizontal bar)
- [ ] Graphique répartition UM (pie chart)
- [ ] Sélecteur de période avec rafraîchissement
- [ ] Responsive design

### Sprint 3.1.3 : Alertes & Seuils _(1-2 jours)_
- [ ] Endpoint `GET /api/analytics/alerts` avec logique calcul
- [ ] Section alertes dans le dashboard
- [ ] Code couleur par sévérité (rouge/jaune/bleu)
- [ ] Configuration seuils via interface admin (simple)
- [ ] Badge compteur d'alertes dans navigation principale

### Sprint 3.1.4 : Export Rapports _(2-3 jours)_
- [ ] Endpoint `POST /api/analytics/export` avec génération fichiers
- [ ] Export Excel avec `openpyxl` : tableaux + graphiques
- [ ] Export PDF avec `reportlab` : mise en page professionnelle
- [ ] Export CSV : données brutes avec headers
- [ ] Boutons export dans dashboard
- [ ] Téléchargement fichier avec nom formaté (eg: rapport_occupation_2026-01-08.xlsx)

### Sprint 3.1.5 : Tests & Validation _(1 jour)_
- [ ] Tests E2E du dashboard analytics
- [ ] Vérification calculs KPIs avec données réelles
- [ ] Tests export des 3 formats
- [ ] Documentation utilisateur (captures d'écran)
- [ ] Commit final + mise à jour TODOLIST

---

## 🎨 Design Guidelines

### Palette Couleurs KPIs
- **Occupation** : 🔵 Bleu (#3B82F6)
- **DMS** : 🟢 Vert (#10B981)
- **Rotation** : 🟣 Violet (#8B5CF6)
- **Capacité** : 🟡 Jaune (#F59E0B)
- **Alertes** : 🔴 Rouge (#EF4444)

### Icônes
- 📊 KPIs & Graphiques
- 🏥 Établissement
- 🛏️ Lits
- ⏱️ DMS / Temps
- 🔄 Rotation
- 🚨 Alertes

### Layout
- **Grille KPIs** : 5 colonnes sur desktop, 2 sur tablet, 1 sur mobile
- **Graphiques** : 2 colonnes sur desktop, stack sur mobile
- **Alertes** : Liste avec scroll si > 5 items

---

## 📚 Dépendances Techniques

### Backend
```txt
# requirements.txt additions
openpyxl>=3.1.2          # Export Excel
reportlab>=4.0.0         # Export PDF
pillow>=10.0.0           # Images pour PDF
```

### Frontend
```html
<!-- Chart.js CDN -->
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
```

---

## ✅ Définition du "Terminé" Sprint 3.1

- Dashboard `/structure/analytics` accessible et fonctionnel
- 5 KPIs affichés avec calculs corrects
- 2 graphiques minimum (capacité par service + répartition UM)
- Système d'alertes basique (suroccupation > 95%)
- Export Excel fonctionnel avec données réelles
- Interface responsive et cohérente avec design system existant
- Documentation utilisateur à jour

---

## 🔗 Intégration avec Phases Précédentes

- Utilise les modèles `Lit`, `UniteFonctionnelle`, `Service`, `Pole` de Phase 1
- S'intègre dans la navigation principale à côté de "Structure"
- Réutilise le style CSS et composants de `structure_new.html`
- Les données d'occupation doivent être simulées ou intégrées via module "Mouvements" (Phase future)

---

## 📌 Notes Importantes

⚠️ **Données d'occupation** : Pour Sprint 3.1, on va simuler l'occupation des lits (random ou fixtures) car le module "Mouvements patients" n'existe pas encore. Prévoir hooks pour intégration future.

⚠️ **Performances** : Si > 1000 lits, prévoir cache Redis pour KPIs (Phase 3.2+)

⚠️ **Sécurité** : Exports limités aux utilisateurs avec rôle "Gestionnaire" (Phase 4 - Gestion droits)
