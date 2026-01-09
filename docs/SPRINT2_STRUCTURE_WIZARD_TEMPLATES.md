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
    - [x] Édition inline des noms de pôles et services
    - [x] Édition inline des codes courts
    - [x] Ajout de pôle avec prompt
    - [x] Ajout de service par pôle
    - [x] Suppressions avec confirmation
  - [x] Étape 3 : UF + codes UM
  - [x] Étape 4 : Hébergement (UH/chambres/lits)
  - [x] Étape 5 : Synthèse & génération

### Étape 2.3 : Intégration données & validation
- [x] Implémentation Step 3 : Configuration UF + Codes UM
  - [x] Interface pour ajouter/éditer les UF par service
  - [x] Sélection et validation des codes UM (MCO, SSR, PSY, HAD)
  - [x] Prévisualisation de la structure UF
- [x] Implémentation Step 4 : Structure d'hébergement
  - [x] Configuration des UH (Unités d'Hébergement)
  - [x] Création de chambres par UH
  - [x] Attribution de lits par chambre
  - [x] Types de chambres et capacités
- [x] Implémentation Step 5 : Synthèse & Génération
  - [x] Prévisualisation complète de la structure
  - [x] Résumé des pôles, services, UF, UH, chambres, lits
  - [x] Validation finale
  - [x] Bouton "Générer la structure"
- [x] Endpoint POST `/api/structure/apply-template`
  - [x] Accepte payload JSON modifié + EJ/EG cible
  - [x] Crée les entités Pole, Service, UniteFonctionnelle en base
  - [x] Crée les UH, Chambre, Lit si définis
  - [x] Retourne un résumé de la structure créée
- [ ] Validation & Tests
  - [ ] Validation des codes UM avant création
  - [ ] Vérification unicité des codes courts
  - [ ] Tests unitaires du endpoint apply-template
  - [ ] Tests E2E du wizard complet

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
