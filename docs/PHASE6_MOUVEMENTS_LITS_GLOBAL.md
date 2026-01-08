# Phase 6 - Refonte UX Mouvements & Plan de Lits

**Date :** 8 janvier 2026  
**Scope :** Workflow mouvements (admission, transfert, sortie, changement de lit) et gestion visuelle des lits

---

## 1. Objectifs

- Offrir aux IDE, cadres et gestionnaires de lits une **interface moderne, rapide et sûre** pour gérer les mouvements et l’occupation des lits.
- Réduire le temps de saisie et les erreurs de localisation.
- Donner une **vision temps réel** de la capacité par service et détecter les conflits (plusieurs patients sur un même lit).

---

## 2. Synthèse fonctionnelle

### 2.1 Workflow mouvements (`mouvement_workflow.html`)

- **Cartes d’événements** :
  - Sélection visuelle des mouvements (A01, A02, A03, etc.) via cartes interactives.
  - Badges indiquant si un mouvement **nécessite une localisation** ("🛏️ avec lit").
  - Description affichée automatiquement pour guider l’utilisateur.
- **Formulaire guidé** :
  - Date/heure du mouvement avec validation (pas avant la venue ni avant le dernier mouvement).
  - Commentaire/motif + intervenant.
- **Sélecteur de lits** :
  - Panneau hiérarchique Service → UF → UH → Chambre → Lits.
  - Statuts visuels : libre, occupé, fermé.
  - Barre de recherche temps réel.
  - Bandeau de confirmation avec chemin complet.
- **Historique** :
  - Timeline verticale moderne avec badges d’événements et détails.

### 2.2 Plan de lits (`/mouvements/plan-lits`)

- Vue globale des lits par service avec :
  - KPIs (total, libres, occupés, taux d’occupation).
  - Hiérarchie visuelle claire.
  - Occupants visibles directement sur chaque lit.
- Filtres par UF, Service, Statut.
- Actions rapides :
  - Affecter un patient (modal).
  - Muter un patient (lien vers workflow pré-rempli).
  - Voir la venue.

---

## 3. Raccourcis clavier

### 3.1 Dans le workflow mouvements

- `Ctrl+S / Cmd+S` : **enregistrer le mouvement** (déjà pattern Phase 6 global).
- `Alt+1`, `Alt+2`, `Alt+3` :
  - Sélection rapide des **premiers types de mouvements** dans la grille (les plus fréquents).
  - Scroll automatique vers la carte sélectionnée.
- `Ctrl+L / Cmd+L` :
  - Ouverture directe du **plan de lits** `/mouvements/plan-lits`.
- `Escape` :
  - Ferme les modals (si utilisés à terme) et respecte les comportements natifs.

### 3.2 Dans le plan de lits

- `Ctrl+F / Cmd+F` :
  - Focus sur la barre de filtres (UF) pour **rechercher rapidement**.
- `Escape` :
  - Ferme le modal d’affectation si ouvert.

Tous les raccourcis sont **désactivés automatiquement** si le focus est dans un champ de saisie (`input`, `textarea`, `select`).

---

## 4. Validations métier

### 4.1 Mouvements

Côté backend (`mouvements.py` et `workflow.py`) :

- **Temporalité** :
  - Interdiction de créer un mouvement **avant** le début de la venue.
  - Interdiction de créer un mouvement **avant** le dernier mouvement existant sur la venue.
- **Transitions autorisées** :
  - Basées sur `ALLOWED_TRANSITIONS` et `INITIAL_EVENTS`.
  - L’UI ne propose que les événements cohérents avec l’état courant.
  - Une validation serveur renforce la règle (l’UI ne suffit pas).
- **Localisation obligatoire** :
  - Certains événements (ex : A01, A02, A22…) exigent une localisation (UH/Chambre/Lit).
  - Vérification serveur pour bloquer une saisie sans UH/Chambre/Lit.
- **Transfert (A02)** :
  - Obligation d’avoir UH + Chambre + Lit de destination.

### 4.2 Plan de lits et conflits

- **Occupant actif** :
  - Un lit est considéré occupé si une `Venue` avec `lit_id` donné a `end_time IS NULL`.
- **Détection de conflits** :
  - Conflit détecté si **plus d’une venue active** sur le même lit.
  - Sur la carte lit :
    - Bordure et fond rouges.
    - Badge "⚠️ Conflit" + compteur de patients.
    - Bouton "🔍 Résoudre conflit" redirige vers `/mouvements?lit_id={id}` (vue à enrichir ultérieurement).
- **Lits inactifs** :
  - Lits dont `operational_status != 'active'` exclus du plan standard.

---

## 5. Fichiers clés

- **Backend** :
  - `app/routers/workflow.py` :
    - Récupération structure + mouvements.
    - Gestion `prefill_lit` pour pré-remplir la localisation depuis le plan de lits.
  - `app/routers/mouvements.py` :
    - Route `/mouvements/plan-lits` + construction hiérarchie lits.
    - Logique de validation des mouvements (dates, transitions, localisation).
- **Templates** :
  - `app/templates/mouvement_workflow.html` : écran workflow mouvement moderne.
  - `app/templates/plan_lits.html` : vue plan de lits avec actions rapides.

- **Documentation sprint** :
  - `docs/SPRINT6.M1_VALIDATION.md` : Workflow mouvements & timeline.
  - `docs/SPRINT6.M2_VALIDATION.md` : Plan de lits interactif.

---

## 6. Recommandations d’utilisation

### 6.1 Pour les IDE / cadres

- Pour **créer ou corriger un mouvement** :
  - Utiliser la page workflow depuis une venue.
  - Choisir le type via les cartes.
  - Utiliser le panneau de lits si un changement de localisation est nécessaire.
  - Vérifier la timeline pour contrôler la cohérence chronologique.

- Pour **trouver rapidement un lit libre** :
  - Aller sur `/mouvements/plan-lits` (ou `Ctrl+L` depuis le workflow).
  - Filtrer par UF/service.
  - Repérer un lit vert (libre) et utiliser **"➕ Affecter"** ou revenir dans le workflow avec le lit pré-rempli.

### 6.2 Pour les gestionnaires de lits

- Utiliser principalement le **plan de lits** pour :
  - Avoir la vue globale des capacités.
  - Identifier les zones en tension (taux d’occupation elevé).
  - Identifier les **conflits** (badge rouge) et lancer leur résolution.

---

## 7. Pistes pour Phase 7

- Intégration **temps réel** (WebSockets) : mise à jour automatique du plan de lits.
- Drag & drop pour mutation visuelle.
- Moteur d’alertes temps réel basé sur les conflits et la surcharge.
- Complétion des endpoints d’affectation / recherche patient.
- Amélioration accessibilité (ARIA, navigation clavier complète).

---

## 8. Commit de synthèse recommandé

Les commits Sprint 6.M1 et 6.M2 existent déjà :
- `Sprint 6.M1 - Refonte Workflow Mouvements & Timeline`
- `Sprint 6.M2 - Plan de Lits Interactif`

Il est recommandé de référencer ce document dans les notes de version Phase 6 globale, aux côtés :
- Des refontes dossiers/venues.
- Des tests E2E et de la documentation utilisateur générale.
