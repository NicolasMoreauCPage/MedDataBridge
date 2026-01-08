# 🧭 Sprint 2 - Wizard & Templates Structure

## 🎯 Objectif du Sprint

Mettre en place un wizard de saisie assistée pour créer/adapter rapidement une structure hospitalière complète à partir de templates pré-configurés (CHU, CH, Clinique, EHPAD, HAD).

---

## 🚀 Plan d'action

### Étape 2.1 : Modèle et API Templates
- [x] Créer un modèle `StructureTemplate` (SQLModel)
  - id, name, type (CHU/CH/Clinique/EHPAD/HAD), description courte
  - payload JSON décrivant la structure par défaut
- [x] Ajouter une API `/api/structure/templates` (GET)
  - [x] Liste des templates disponibles
  - [x] Détail d'un template par `id` avec son payload JSON
- [x] Ajouter quelques templates embarqués (hardcodés ou seed de base)
  - [x] CHU (4 pôles : Médecine, Chirurgie, Femme-Enfant, Urgences-Réanimation)
  - [x] CH (2 pôles : Médecine-Chirurgie, Gériatrie-SSR)
  - [x] Clinique (2 pôles : Chirurgie Ambulatoire, Imagerie-Consultations)

### Étape 2.2 : Page Wizard & Routing
- [x] Route `/structure/wizard` (GET)
  - [x] Template `structure_wizard.html`
  - [x] Header avec résumé établissement + progression étapes
- [x] Navigation multi-étapes côté front (JS)
  - [x] Étape 1 : Choix template + infos établissement (connecté à l'API)
  - [x] Étape 2 : Configuration pôles/services (affichage depuis template, suppression pôle)
  - [ ] Étape 3 : UF + codes UM
  - [ ] Étape 4 : Hébergement (UH/chambres/lits)
  - [ ] Étape 5 : Synthèse & génération

### Étape 2.3 : Intégration données & validation
- [ ] Préremplir le wizard à partir du template choisi
- [ ] Valider les champs clés (FINESS, codes UM, identifiants)
- [ ] API de prévisualisation : structure générée en JSON
- [ ] Action finale : appliquer le template à l'EJ cible (création structure réelle)

---

## 🔗 Liens avec la Phase 1

- Le wizard utilise les mêmes modèles et API de structure que le dashboard (`/api/structure/tree`, `/api/structure/details`).
- La structure générée doit être immédiatement visible et navigable dans le dashboard `/structure`.

---

## ✅ Définition du "Terminé" Sprint 2

- Wizard accessible via `/structure/wizard` avec au moins 3 templates utilisables
- Parcours complet 5 étapes fonctionnel (même si validations avancées limitées)
- Après validation, la structure générée est visible dans le dashboard et cohérente
- Documentation mise à jour (TODOLIST + ce fichier)
