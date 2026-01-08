# 🚑 Phase 6 – Refonte UX Mouvements & Mise en lit

**Status** : 🟡 EN PLANIFICATION  
**Date** : 8 janvier 2026  
**Portée** : Interfaces de gestion des mouvements (admission, transfert, sortie, permissions…) et mise en lit / localisation pour les professionnels hospitaliers au lit du patient ou au poste de soins.

---

## 1. 🎯 Objectifs UX & Métier

- Rendre la **saisie de mouvements et de mise en lit ultra-rapide** pour les IDE, AS, cadres, secrétariats de service.
- Réduire les erreurs de localisation (mauvais lit, mauvaise UF, mauvaise chambre) grâce à un **parcours guidé**.
- Donner une **vision temps réel** du parcours de lit : d'où vient le patient, où il va, dans quel état.
- S'aligner visuellement et ergonomiquement avec les refontes **Dossier** et **Venue** (Phase 6.1–6.4).
- Préparer une base solide pour un futur **pilotage capacitaire temps réel** (dashboard lits/service).

---

## 2. 👥 Personas Cibles

### 2.1 IDE / AS de service
- Contexte : poste de soins, beaucoup d'interruptions, devices parfois lents.
- Besoins :
  - Saisir un **mouvement simple** (transfert de lit, retour de permission) en **moins de 30 secondes**.
  - Visualiser rapidement **le lit actuel** et la prochaine étape.
  - Comprendre les contraintes (lits fermés, chambres occupées, UF cible).

### 2.2 Cadre de santé / Gestionnaire de lits
- Contexte : gestion de la capacité de l'unité / service.
- Besoins :
  - Voir les **mouvements récents et à venir**.
  - Comprendre les **changements de lit / chambre** dans la journée.
  - Vérifier la **cohérence des séquences** (pas de double-occupation, pas de sortie sans mouvement d'entrée, etc.).

### 2.3 Secrétariat médical / Admissions locales
- Contexte : saisie a posteriori de certains mouvements, corrections.
- Besoins :
  - Retrouver facilement un mouvement / une venue.
  - Corriger un mouvement (statut, dates, motif) sans casser le workflow.

---

## 3. 🔍 Analyse de l’Existant (Haut Niveau)

### 3.1 Router & Logique
- `app/routers/mouvements.py` :
  - Liste des mouvements (`list_mouvements`) filtrable par `venue_id`, `dossier_id`, contexte EJ.
  - Filtres déjà implémentés (type, status, location) + ordre chronologique.
  - Construction de `rows` pour le template générique `list.html`.
- `app/services/mouvements_service.py` :
  - Logique backend de création / mise à jour.
- `app/models_structure.py` :
  - Modèles `UniteFonctionnelle`, `UniteHebergement`, `Chambre`, `Lit` utilisés dans le workflow.

### 3.2 Templates existants
- `app/templates/mouvement_detail.html` :
  - Vue détaillée moderne (header gradient, cartes infos, identifiants, actions).
  - Déjà dans l’esprit Phase 6 (glassmorphism, badges, sections claires).
- `app/templates/mouvement_workflow.html` :
  - Grand formulaire "Nouveau mouvement" avec contexte patient/dossier/venue en haut.
  - Sélection d’événement via `event_catalog` (IHE/IHE-PAM/FHIR).
  - Sélecteur de lit en dropdown (hierarchie service > UF > UH > chambre > lit).
  - Historique des mouvements en bas (table).

### 3.3 Limites actuelles pressenties
- Sélecteur de lit volumineux (toute la structure dans un seul `<select>`).
- Peu de **raccourcis contextuels** : pas de presets "transfert dans même chambre", "simple changement de lit".
- Pas de **mode rapide** pour les mouvements fréquents (ex : retour de permission, transfert intra-service).
- Historique linéaire mais peu "timeline" (pas de hiérarchie visuelle forte entre types d’événements).

---

## 4. 😣 Pain Points Métier

### 4.1 Pour la saisie de mouvements
- Trop de champs visibles en même temps → surcharge cognitive.
- Pas de **distinction claire** entre mouvements majeurs (admission/sortie) et micro-mouvements (changement de lit).
- Le champ localisation dépend de la structure complète → difficile de retrouver rapidement le lit voulu.

### 4.2 Pour la mise en lit / changement de lit
- L’IDE veut surtout répondre à : *« Dans quel lit ce patient va maintenant ? »*.
- Le code lit (ex : `CH12-L2`) n’est pas toujours évident à retrouver.
- Besoin de voir en un coup d’œil :
  - Chambres libres / occupées.
  - Statut du lit (ouvert, fermé, réservé).

### 4.3 Pour la cohérence des mouvements
- Difficile de voir si la **séquence** est correcte : pas de timeline manipulable.
- Corrections (annulations) peu guidées.

---

## 5. 🧭 Principes UX Cibles

- **Mode opérateur** : limiter la réflexion, guider par des **questions simples**.
- **Progressivité** : afficher d’abord les choix métier (type d’événement), puis seulement les champs nécessaires.
- **Contextualisation forte** : rappel constant du patient, du dossier, de la venue et de la localisation actuelle.
- **Ergonomie tactile-compatible** : gros boutons, listes cliquables, évitement de menus déroulants trop longs.
- **Cohérence avec Phase 6** : même style visuel (gradients, cartes, badges), mêmes patterns (wizards, panneaux latéraux).

---

## 6. 🗺️ Plan d’Action Global

### Étape 1 – Cartographie fonctionnelle & scénarios
1. Lister les **types de mouvements les plus fréquents** (admission, transfert intra-service, transfert inter-service, changement de lit, sortie, permissions).
2. Pour chaque type, définir :
   - Champs indispensables (date/heure, UF, chambre, lit, motif, intervenant).
   - Champs optionnels.
   - Règles de validation métier (date > dernier mouvement, lit disponible, etc.).
3. Clarifier les **rôles** : qui crée quoi (IDE, cadre, secrétariat) pour adapter les labels/messages.

### Étape 2 – Refondre l’écran `mouvement_workflow.html`
1. Transformer le formulaire actuel en **mini-wizard d’une page** :
   - Bloc 1 : Contexte patient/dossier/venue (déjà présent, à enrichir avec badges état/lit actuel).
   - Bloc 2 : Choix du type de mouvement (grille de cartes au lieu d’un simple `<select>`).
   - Bloc 3 : Champs dynamiques selon le type (localisation, dates, motif, intervenant).
   - Bloc 4 : Résumé + bouton "Enregistrer".
2. Ajouter des **presets rapides** :
   - "Transfert dans la même chambre" → proposer seulement les lits disponibles de cette chambre.
   - "Transfert intra-UF" → filtrer lits de la même UF.
   - "Retour permission" → proposer la localisation précédente.
3. Réduire le `<select>` de lits :
   - Remplacer par un **panneau latéral ou modal** de sélection lit avec arborescence visuelle + statut (libre/occupé/fermé).
   - Permettre la **recherche texte** (nom chambre/lit).

### Étape 3 – Vue timeline des mouvements (améliorer l’historique)
1. Transformer l’historique tabulaire en **timeline verticale** :
   - Badge type d’événement (admission, transfert, sortie, permission…).
   - Date/heure en gras, commentaire en dessous.
   - Code couleur par nature de mouvement.
2. Ajouter des **actions contextualisées** :
   - Bouton "Voir détail" (ouvre `mouvement_detail.html` dans un panneau latéral).
   - Bouton "Annuler / corriger" selon état.
3. Mettre en évidence le **mouvement courant** (dernier effectif) et les prochains planifiés (si supportés).

### Étape 4 – UI de mise en lit dédiée
1. Concevoir une **vue "Plan de lits" simplifiée** pour un service / UF :
   - Liste / grille des chambres avec lits (status : occupé, libre, fermé).
   - Bouton "Affecter ce patient" sur chaque lit disponible.
2. Intégrer cette vue dans le workflow mouvement :
   - Depuis `mouvement_workflow`, bouton "Choisir un lit" ouvre la vue plan de lits en overlay.
   - Une fois le lit choisi, le champ localisation est auto-rempli.
3. Prévoir la **mise en avant des contraintes** :
   - Lit femme/homme, isolement, pédiatrie, etc. (si données disponibles à terme).

### Étape 5 – Raccourcis & productivité
1. Raccourcis clavier dans `mouvement_workflow` :
   - `Ctrl+S` : enregistrer le mouvement (déjà pattern Phase 6).
   - `Alt+1/2/3...` : sélectionner rapidement un type de mouvement dans la grille.
2. Raccourcis sur la timeline :
   - `N` : nouveau mouvement.
   - `↑/↓` : naviguer dans les événements.

### Étape 6 – Validation métier & erreurs UX
1. Afficher **en clair** les conflits potentiels :
   - Deux patients sur le même lit à la même période.
   - Mouvement en doublon (même date/heure et même destination).
2. Feedback UX :
   - Bannières explicites (vert/orange/rouge) selon la gravité.
   - Messages courts, orientés action ("Sélectionnez un autre lit", "Corrigez la date", etc.).

### Étape 7 – Intégration & cohérence avec Dossiers/Venues
1. Depuis `dossier_detail.html` et `venue_detail.html` :
   - Bouton quick action "Nouveau mouvement" qui ouvre directement le workflow pré-filtré.
2. Conserver le **fil d’Ariane** Dossier → Venue → Mouvements.
3. Harmoniser les **headers et cartes d’infos** avec les écrans Phase 6 (mêmes classes utilitaires, même langage visuel).

---

## 7. 📦 Livrables prévus

1. **Refonte `mouvement_workflow.html`** :
   - UI guidée par types de mouvements.
   - Sélecteur de lit ergonomique.
   - Timeline modernisée.
2. **Ajustements `mouvement_detail.html`** :
   - Aligner avec nouveaux labels / badges / navigation.
3. **Raccourcis & validations** :
   - Raccourcis clavier cohérents avec Phase 6.
   - Messages d’erreurs métier explicites.
4. **Documentation** :
   - Mini plan Phase 6 Mouvements & Lits (ce fichier).
   - Futur guide utilisateur ciblé "Saisir un mouvement / mise en lit".

---

## 8. 📅 Proposition de Sprints

- **Sprint 6.M1 – Workflow mouvement & timeline** (2–3 jours)
  - Refonte `mouvement_workflow.html` + timeline améliorée.
- **Sprint 6.M2 – Mise en lit & plan de lits** (3–4 jours)
  - Sélecteur de lit visuel + intégration dans le workflow.
- **Sprint 6.M3 – Finitions, raccourcis, docs** (1–2 jours)
  - Raccourcis, messages d’erreur, documentation.
