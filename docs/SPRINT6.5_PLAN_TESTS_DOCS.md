# 🧪 Sprint 6.5 - Plan Tests E2E & Documentation (Phase 6)

**Date** : 8 janvier 2026  
**Portée** : Validation de la refonte UX Dossiers & Venues (Phase 6.1 → 6.4)

---

## 1. 🎯 Objectifs

- Couvrir les workflows critiques par des tests E2E Playwright.
- Documenter clairement les nouveaux écrans et patterns UX.
- Sécuriser la mise en production de la Phase 6.

---

## 2. ✅ Tests E2E prévus (Playwright)

Fichier : `tests/e2e/test_phase6_dossiers_venues.py`

### 2.1. Listings & Filtres
- [x] `test_dossiers_listing_loads` : chargement listing dossiers + UI de base.
- [x] `test_dossiers_filters_work` : filtres avancés (UF) + persistance valeur.
- [x] `test_venues_listing_loads` : chargement listing venues.
- [x] `test_venues_filters_work` : filtres venues (service).
- [x] `test_mouvements_filters_work` : filtres mouvements.
- [x] `test_filters_persist_after_navigation` : persistance filtres via URL.

### 2.2. Raccourcis Clavier
- [x] `test_keyboard_shortcut_ctrl_n_dossiers` : `Ctrl+N` → nouveau dossier.
- [x] `test_keyboard_shortcut_slash_focus_filter` : `/` → focus filtre.
- [x] `test_keyboard_shortcut_escape_closes_filters` : `Esc` → ferme filtres.
- [x] `test_form_keyboard_shortcut_ctrl_s` : `Ctrl+S` → soumission formulaire.

### 2.3. Détails & Workflows
- [x] `test_dossier_detail_view_modern_ui` : header moderne + sections.
- [x] `test_venue_detail_view_modern_ui` : UI moderne venue.
- [x] `test_quick_action_nouvelle_venue_from_dossier` : quick action.
- [x] `test_admission_wizard_navigation` : navigation wizard admission.
- [x] `test_cross_navigation_patient_dossier_venue` : navigation croisée.

---

## 3. 📚 Documentation Utilisateur à produire

Fichier cible (à venir) : `docs/PHASE6_GUIDE_UTILISATEUR.md`

### 3.1. Guide "Créer une admission complète"
- Chemin : Patient → Nouveau dossier → Venue initiale.
- Screenshots :
  - Vue patient avec bouton "Nouveau dossier".
  - Étape 1/3 : identité patient.
  - Étape 2/3 : dossier administratif.
  - Étape 3/3 : venue initiale.

### 3.2. Guide "Gérer les venues d'un dossier"
- Sections :
  - Comprendre le header du dossier.
  - Liste des venues associées.
  - Quick action "Nouvelle venue".
  - Navigation vers mouvements.

### 3.3. Guide "Filtres avancés & recherche"
- Dossiers : UF, médecin, type, période, état.
- Venues : UF, service, localisation, dates.
- Mouvements : type, statut, localisation.
- Exemples concrets (CARDIO, période du mois courant, etc.).

### 3.4. Guide "Raccourcis clavier pour power users"
- `Ctrl+N` : Nouveau (listing).
- `Ctrl+S` : Sauvegarde formulaire.
- `/` : Focus bar de filtre.
- `Esc` : Fermeture panel.
- Bonnes pratiques (où ça fonctionne, focus, limitations).

### 3.5. FAQ
- "Je ne trouve pas un dossier par UF".
- "Le raccourci Ctrl+S ne fonctionne pas".
- "Pourquoi je ne vois pas le bouton Nouvelle venue ?".
- "Comment filtrer sur une période de dates ?".

---

## 4. 🧩 Documentation Technique à produire

Fichier cible (à venir) : `docs/PHASE6_NOTES_TECHNIQUES.md`

- Architecture des vues dossier/venue.
- Wizard admission (3 étapes) : routing, validation, persistance.
- Patterns de filtres génériques (list.html + services).
- Gestion des raccourcis clavier (list.html, form.html).
- Intégration Alpine.js.

---

## 5. ✅ État d'avancement

- Tests E2E : structure de fichier créée + scénarios couvrant Phase 6.
- Docs utilisateur : **à rédiger**.
- Docs techniques : **à rédiger**.

---

**Prochaine étape** :
- Rédiger `PHASE6_GUIDE_UTILISATEUR.md` (guides + FAQ).
- Rédiger `PHASE6_NOTES_TECHNIQUES.md`.
- Lancer les tests E2E Phase 6 et consigner les résultats.
