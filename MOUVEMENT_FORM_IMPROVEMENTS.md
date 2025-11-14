# Plan d'amélioration : Formulaire de création de mouvement

## Demandes utilisateur

1. ✅ **Restreindre les types de mouvements** selon le workflow  
   État: DÉJÀ IMPLÉMENTÉ (voir `allowed_events_codes` et `allowed_types`)

2. ❌ **Empêcher les mouvements historiques** (date < venue.start_time ou dernier mouvement)
   État: À IMPLÉMENTER
   - Validation côté Python dans `new_mouvement()` 
   - Validation côté HTML5 (min attribute sur datetime)
   - Message d'erreur au submit si violation

3. ❌ **Charger UniteHebergement depuis la structure géographique** de la venue
   État: À IMPLÉMENTER
   - Récupérer Venue → Dossier → EntiteGeographique
   - Charger les UniteHebergement liés à l'EntiteGeographique
   - Remplacer la logique UF → UH par EG → UH

4. ❌ **AJAX : mise à jour dynamique Chambre** selon UniteHebergement
   État: À IMPLÉMENTER
   - Endpoint `/api/mouvements/chambres/{uh_id}`
   - JavaScript listener sur changement UH
   - Mise à jour options Chambre

5. ❌ **AJAX : mise à jour dynamique Lit** selon Chambre
   État: À IMPLÉMENTER
   - Endpoint `/api/mouvements/lits/{chambre_id}`
   - JavaScript listener sur changement Chambre
   - Mise à jour options Lit

6. ❌ **Retirer "Localisation complète"** du formulaire
   État: À IMPLÉMENTER
   - Supprimer le champ `location` de la liste `fields`
   - Le champ sera généré automatiquement depuis Chambre/Lit si fournis

7. ❌ **AJAX : mise à jour dynamique Raison** selon type de mouvement
   État: À IMPLÉMENTER
   - Endpoint `/api/mouvements/reasons/{movement_type}`
   - JavaScript listener sur changement Type
   - Mise à jour options Raison

## Architecture

### Backend (app/routers/mouvements.py)
- `new_mouvement()` : ajout validation min_date
- Nouveaux endpoints AJAX:
  - `GET /api/mouvements/chambres/{uh_id}` → JSON list Chambres
  - `GET /api/mouvements/lits/{chambre_id}` → JSON list Lits
  - `GET /api/mouvements/reasons/{movement_type}` → JSON list Reasons

### Frontend (form.html ou JS dédié)
- Script AJAX pour chaque dépendance dynamique
- Event listeners sur select (uf_id, uh_id, chambre_id, type)
- Mise à jour du DOM avec options serveur

### Modèles
- Venue.start_time : déjà présent pour validation
- Mouvement.when : validation min vs start_time
- EntiteGeographique → UniteHebergement : relation existante

## Fichiers à modifier
1. `app/routers/mouvements.py` - new_mouvement(), AJAX endpoints
2. `app/templates/form.html` (ou JavaScript include) - AJAX handlers
