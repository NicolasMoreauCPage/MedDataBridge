# 🧱 Notes Techniques Phase 6 – Dossiers & Venues

**Contexte** : Refonte UX Dossiers & Venues (Phase 6.1 → 6.4)

---

## 1. Architecture générale

- Routers principaux :
  - `app/routers/dossiers.py`
  - `app/routers/venues.py`
  - `app/routers/mouvements.py`
- Services métier :
  - `app/services/dossiers_service.py`
- Templates clés :
  - `app/templates/dossier_detail.html`
  - `app/templates/venue_detail.html`
  - `app/templates/admission_wizard.html`
  - `app/templates/list.html`
  - `app/templates/form.html`

---

## 2. Wizard d'admission (Phase 6.3)

- Implémenté dans `admission_wizard.html` + router associé.
- 3 étapes principales :
  1. Identité patient (lecture / création).
  2. Dossier administratif.
  3. Venue initiale.
- Navigation : boutons **Suivant / Précédent**, avec persistance de l'état.
- Validation : contrôles côté backend + feedback visuel.

---

## 3. Patterns de filtres génériques (Phase 6.4)

### 3.1 Router Dossiers
- Fonction : `list_dossiers` dans `app/routers/dossiers.py`.
- Query params principaux :
  - `uf: str | None`
  - `attending_provider: str | None` (alias `medecin` en interne)
  - `dossier_type: DossierType | None`
  - `admit_from: str | None`
  - `admit_to: str | None`
  - `current_state: str | None`
- Les paramètres sont transmis au service `get_dossiers`.

### 3.2 Service get_dossiers
- Fichier : `app/services/dossiers_service.py`.
- Signature enrichie avec les filtres avancés.
- Application des filtres :
  - ILIKE sur champs texte (`uf_responsabilite`, `attending_provider`, `current_state`).
  - Filtre de dates sur `admit_time`.
- Parsing de dates : helper interne `_parse_date`.

### 3.3 Template list.html
- Réception d'une liste de `filters` depuis les routers.
- Utilisation d'un panneau de filtres (souvent avec Alpine.js) :
  - `x-data="{ showFilters: false }"`
  - `x-show="showFilters"` sur le panneau.
- Champs générés via un composant `filter_field` (selon configuration).

---

## 4. Gestion des raccourcis clavier

### 4.1 list.html
- Zone concernée : script en bas du template.
- Raccourcis gérés :
  - `Ctrl+N / Cmd+N` : nouveau.
  - `/` : focus premier champ de filtre.
  - `Esc` : fermeture panneau filtres.
- Logique :
  - Écoute globale `document.addEventListener('keydown', ...)`.
  - Vérification du `target` pour ne pas perturber la saisie dans les inputs.
  - Interaction avec Alpine.js : accès à `showFilters` via `_x_dataStack` si disponible.

### 4.2 form.html
- Raccourci : `Ctrl+S / Cmd+S`.
- Comportement :
  - `preventDefault()` sur l'événement.
  - Recherche du **bouton de soumission principal** et `click()` programmatique.

---

## 5. Intégration Alpine.js

- Utilisé pour les panneaux dynamiques (filtres, sections repliables, etc.).
- Exemple type :
  - `x-data="{ showFilters: false }"` sur un conteneur.
  - `@click="showFilters = !showFilters"` sur le bouton Filtres.
  - `x-show="showFilters"` sur le panneau.
- Le raccourci `Esc` tente d'accéder à cet état pour fermer proprement le panneau.

---

## 6. Navigation croisée et liens

- Patient → Dossier → Venue → Mouvements :
  - Les templates incluent des liens explicites entre entités.
  - Les headers rappellent le contexte (Patient / Dossier / Venue).
- Quick action "Nouvelle venue" :
  - Lien `href="/venues/new?dossier_id={{ dossier.id }}"`.
  - Permet de pré-remplir le contexte côté backend.

---

## 7. Tests E2E Phase 6

- Fichier : `tests/e2e/test_phase6_dossiers_venues.py`.
- Couvre :
  - Chargement des pages clés.
  - Fonctionnement des filtres.
  - Raccourcis clavier (Ctrl+N, Ctrl+S, /, Esc).
  - Navigation croisée.
  - Quick actions.
  - Wizard d'admission.

---

## 8. Points de vigilance

- Les filtres doivent rester **optionnels** pour ne pas casser les usages existants.
- Les raccourcis clavier doivent toujours :
  - Respecter le focus de l'utilisateur.
  - Ne pas masquer des comportements natifs critiques.
- Les évolutions futures (Phase 7) pourront exploiter :
  - Sauvegarde de presets de filtres (localStorage).
  - Export CSV avec filtres appliqués.

---

## 9. Références

- Plan fonctionnel : `docs/PHASE6_PLAN_REFONTE_DOSSIERS_VENUES_UX.md`.
- Validation Sprint 6.4 : `docs/SPRINT6.4_VALIDATION.md`.
- Plan Sprint 6.5 : `docs/SPRINT6.5_PLAN_TESTS_DOCS.md`.
