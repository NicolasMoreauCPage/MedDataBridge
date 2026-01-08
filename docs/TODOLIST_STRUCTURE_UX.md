# 🏥 Plan d'Optimisation des IHM Structure Hospitalière

## 📋 État des lieux des interfaces actuelles

### Interfaces existantes analysées :
- `structure/ufs.html` - Liste des Unités Fonctionnelles (basique)
- `structure/uf_form.html` - Formulaire UF (old-school)  
- `structure/service_form.html` - Formulaire Service
- `structure/service_detail.html` - Vue détail Service
- `uf_detail.html` - Vue détail UF
- `eg_detail.html` - Vue détail Entité Géographique avec arbre structure

### Problèmes identifiés :

#### ❌ **UX/UI problématiques :**
1. **Formulaires old-school** : Style HTML basique sans workflow moderne
2. **Navigation complexe** : URLs longues avec hiérarchie rigide
3. **Pas de saisie guidée** : Aucun wizard pour créer structure complète
4. **Manque d'auto-complétion** : Saisie manuelle des codes/identifiants
5. **Pas de templates** : Aucun modèle pré-défini (CHU, CH, Clinique)
6. **Interface dispersée** : Pas de vue consolidée pour gérer toute la structure
7. **Filtrage limité** : Options de recherche/tri insuffisantes

#### 🏥 **Besoins des professionnels hospitaliers :**
1. **Gestionnaires d'établissement** : Vue globale + drill-down rapide
2. **Responsables de pôle** : Gestion de leurs services/UF uniquement
3. **DIM** : Codes FINESS, identifiants UM, statistiques
4. **Ingénieurs biomédicaux** : Gestion équipements par UF/chambre
5. **Directeurs soins** : Organisation UF de soins, capacité lits

---

## 🎯 Objectifs d'optimisation

### 1. **Interface Unifiée "Structure Manager"**
- Dashboard central avec vue hiérarchique interactive
- Navigation par arbre avec expand/collapse
- Actions contextuelles sur chaque niveau
- Indicateurs temps réel (occupation, capacité)

### 2. **Saisie Assistée & Templates**
- Wizard de création structure complète
- Templates pré-configurés (CHU, CH, Clinique, EHPAD)
- Auto-complétion codes (FINESS, UM, etc.)
- Duplication/clonage de structures similaires

### 3. **Interfaces Métier Spécialisées**
- **Mode "Gestionnaire"** : Vue globale + analytics
- **Mode "Médical"** : Focus UF de soins + effectifs
- **Mode "Technique"** : Gestion locaux + équipements
- **Mode "DIM"** : Codes + statistiques + export

---

## 📝 TODO Liste Détaillée

### Phase 1 : Interface Principale (Dashboard Structure)
- [x] **Dashboard Structure Unifié** _(Sprint 1 terminé)_
  - [x] Header moderne avec KPI (Pôles, Services, UF, Lits) dans `structure_new.html`
  - [x] Arbre interactif EJ → EG → Pôle → Service → UF → UH → Chambre → Lit
  - [x] Expand/collapse avec animations + icônes par type
  - [x] Compteurs temps réel (calculés côté client à partir de `/api/structure/tree`)
  - [x] Panneau de détails riche avec prévisualisation hiérarchique

- [x] **Navigation Optimisée** _(Sprint 1 terminé)_
  - [x] Route `/structure` avec nouveau dashboard et filtres EJ
  - [x] URLs simplifiées avec deep-link `#node-{type}-{id}`
  - [x] Breadcrumb intelligent dans le panneau de détails
  - [x] Cache client basique via `currentStructure` (une seule requête `/tree`)

### Phase 2 : Wizard de Saisie Assistée ✅ _(Sprint 2 terminé)_
- [x] **Templates Pré-configurés**
  - [x] Template CHU (Pôles multiples, services spécialisés)
  - [x] Template Centre Hospitalier (Organisation standard)
  - [x] Template Clinique (Plateaux techniques, ambulatoire)
  - [ ] Template EHPAD (UF hébergement, soins) _[Optionnel - Phase future]_
  - [ ] Template HAD (Équipes mobiles, secteurs) _[Optionnel - Phase future]_

- [x] **Wizard Multi-étapes**
  - [x] Étape 1 : Choix template + infos établissement
  - [x] Étape 2 : Configuration pôles/services (édition inline complète)
  - [x] Étape 3 : Définition UF + codes UM (MCO/SSR/PSY/HAD)
  - [x] Étape 4 : Structure hébergement (UH/chambres/lits)
  - [x] Étape 5 : Validation + génération automatique en base

- [ ] **Auto-complétion & Validation** _[Améliorations futures]_
  - [ ] API codes FINESS (établissement + géographique)
  - [ ] Référentiel codes UM (Médecine, Chirurgie, Obstétrique...)
  - [ ] Validation formats identifiants selon normes
  - [ ] Suggestions basées sur établissements similaires

### Phase 3 : Interfaces Métier Spécialisées
- [ ] **Mode Gestionnaire**
  - [ ] Vue analytics avec KPI (taux occupation, DMS, rotation)
  - [ ] Graphiques capacité par service/UF
  - [ ] Alertes seuils (suroccupation, sous-utilisation)
  - [ ] Export rapports direction (Excel, PDF)

- [ ] **Mode Médical**
  - [ ] Focus UF de soins avec effectifs médicaux/paramédicaux
  - [ ] Planning médecins par UF/service
  - [ ] Gestion gardes et astreintes
  - [ ] Interface mobile-friendly pour tablettes

- [ ] **Mode DIM**
  - [ ] Vue codes et statistiques
  - [ ] Validation cohérence PMSI
  - [ ] Export fichiers réglementaires
  - [ ] Historique modifications pour audit

### Phase 4 : Fonctionnalités Avancées
- [ ] **Import/Export Excel**
  - [ ] Template Excel pour import structure complète
  - [ ] Validation données avant import
  - [ ] Export structure vers Excel avec formatage
  - [ ] Mapping automatique colonnes

- [ ] **Gestion des Droits**
  - [ ] Profils utilisateurs (Gestionnaire, Médical, DIM, Technique)
  - [ ] Restrictions par établissement/pôle
  - [ ] Logs d'audit des modifications
  - [ ] Workflow validation changements critiques

- [ ] **Intégration Temps Réel**
  - [ ] Synchronisation avec SIH
  - [ ] Mise à jour statuts lits automatique
  - [ ] Notifications changements structure
  - [ ] API REST pour intégrations tierces

### Phase 5 : UX/UI Moderne
- [ ] **Design System Hospitalier**
  - [ ] Palette couleurs par type structure (MCO=bleu, PSY=violet, SSR=vert)
  - [ ] Icônes métier (🏥 EJ, 🏢 Pôle, 🏛️ Service, 🔹 UF, 🏠 UH, 🛏️ Chambre, 💺 Lit)
  - [ ] Composants réutilisables (cards, forms, tables)
  - [ ] Responsive design (desktop/tablet/mobile)

- [ ] **Interactions Avancées**
  - [ ] Drag & drop pour réorganiser structure
  - [ ] Édition inline pour modifications rapides
  - [ ] Raccourcis clavier (Ctrl+N nouvelle UF, etc.)
  - [ ] Sauvegarde automatique (auto-save)

- [ ] **Recherche & Filtres Intelligents**
  - [ ] Recherche globale multi-critères
  - [ ] Filtres facettes (type, statut, capacité)
  - [ ] Recherche par géolocalisation
  - [ ] Historique recherches utilisateur

---

## 🎨 Mockups & Inspirations

### Dashboard Principal
```
┌─ Structure Manager ─────────────────────────────────────────┐
│ CHU Démo ▼                                    👤 Dupont     │
├─────────────────────────────────────────────────────────────┤
│ 📊 Vue d'ensemble    🏗️ Wizard    👥 Équipes    📈 Analytics │
├─────────────────────────────────────────────────────────────┤
│ 🏥 CHU Démo (FINESS: 123456789)                            │
│ ├─ 🏢 Site Principal [📍 Lyon] (287 lits) ───────── [+][✏️] │
│ │  ├─ 🏛️ Pôle Médecine (156 lits, 85% occ.) ──── [+][✏️]   │
│ │  │  ├─ 🔹 Cardiologie (32 lits) ─────────── [+][✏️][🗑️]  │
│ │  │  ├─ 🔹 Gastroentérologie (28 lits) ──── [+][✏️][🗑️]  │
│ │  │  └─ 🔹 Pneumologie (24 lits) ─────────── [+][✏️][🗑️]  │
│ │  └─ 🏛️ Pôle Chirurgie (131 lits, 92% occ.) ─── [+][✏️]   │
│ │     ├─ 🔹 Orthopédie (45 lits) ──────────── [+][✏️][🗑️]  │
│ │     └─ 🔹 Viscérale (38 lits) ───────────── [+][✏️][🗑️]  │
│ └─ 🏢 Site Annexe [📍 Bron] (98 lits) ─────────── [+][✏️]   │
└─────────────────────────────────────────────────────────────┘
```

### Wizard Template
```
┌─ Création Structure ─ Étape 1/5 ─────────────────────────────┐
│ Choisir un template                                          │
│                                                              │
│ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌──────────┐ │
│ │    🏥 CHU   │ │    🏨 CH    │ │  🏪 Clinique │ │ 🏠 EHPAD │ │
│ │ Universitaire│ │   Général   │ │   Privée    │ │ Personnes│ │
│ │   Complexe  │ │  Standard   │ │  Ambulatoire │ │  Âgées   │ │
│ │ [RECOMMANDÉ]│ │             │ │             │ │          │ │
│ └─────────────┘ └─────────────┘ └─────────────┘ └──────────┘ │
│                                                              │
│ ✨ Ce template inclut :                                      │
│ • 4 Pôles pré-configurés (Med, Chir, Femme-Enfant, USIC)   │  
│ • 15 Services spécialisés                                   │
│ • Codes UM standardisés                                     │
│ • Structure hébergement type                                │
│                                                              │
│                              [Précédent] [Suivant >]        │
└──────────────────────────────────────────────────────────────┘
```

---

## 🚀 Priorités de développement

### Sprint 1 (2 semaines) - Foundation
1. Dashboard structure avec arbre hiérarchique
2. Router optimisé et navigation fluide
3. API endpoints pour CRUD rapide

### Sprint 2 (2 semaines) - Templates  
1. Wizard multi-étapes base
2. 3 templates essentiels (CHU, CH, Clinique)
3. Auto-complétion codes de base

### Sprint 3 (2 semaines) - UX Polish
1. Design system hospitalier
2. Interactions avancées (drag&drop, inline edit)
3. Responsive mobile

### Sprint 4 (1 semaine) - Intégrations
1. Import/export Excel
2. Validation FINESS
3. Mode gestionnaire avec analytics

---

## 📈 Métriques de succès

- **Temps de saisie structure complète** : < 15 min (vs 2h actuellement)
- **Erreurs de saisie codes** : -80% grâce auto-complétion
- **Adoption par profils** : 90% gestionnaires, 70% médical
- **Satisfaction utilisateur** : > 8/10
- **Mobile usage** : 40% consultations sur tablette

---

**Prêt pour démarrer le développement ! 🚀**