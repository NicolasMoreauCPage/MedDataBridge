# 🎨 Phase 5 : UX Moderne - Édition Interactive

## 🎯 Objectif
Moderniser l'expérience utilisateur avec des interactions avancées :
- Édition inline (double-clic pour modifier)
- Drag & drop pour réorganiser la structure
- Raccourcis clavier
- Auto-save

---

## 📋 Fonctionnalités

### 1. Édition Inline

#### Comportement
- **Double-clic** sur nom/code → Passe en mode édition
- **Entrée** → Sauvegarde
- **Échap** → Annule
- **Tab** → Passe au champ suivant
- Indicateur visuel de sauvegarde (✓ vert ou spinner)

#### Champs éditables
- Noms (EG, Pôle, Service, UF, UH, Chambre)
- Codes (avec validation unicité)
- Capacités (nombres uniquement)
- Téléphones, adresses
- Responsables

#### API
```python
PATCH /api/structure/{type}/{id}
Body: { "field": "nom", "value": "Nouveau nom" }
Response: { "success": true, "updated_at": "2026-01-08T15:30:00" }
```

### 2. Drag & Drop Réorganisation

#### Cas d'usage
1. **Déplacer Service** d'un Pôle à un autre
2. **Déplacer UF** d'un Service à un autre
3. **Déplacer Lit** d'une Chambre à une autre
4. **Réordonner** éléments dans même niveau

#### Comportement
- Drag handle (⋮⋮) visible au hover
- Indicateur visuel de drop zone
- Validation règles métier (pas de boucles)
- Confirmation si impact > 10 éléments
- Animation smooth

#### API
```python
POST /api/structure/move
Body: {
  "item_type": "service",
  "item_id": 123,
  "target_type": "pole",
  "target_id": 456,
  "position": 0  # Optionnel pour ordering
}
```

### 3. Raccourcis Clavier

| Raccourci | Action |
|-----------|--------|
| `Ctrl + N` | Nouveau (ouvre formulaire selon contexte) |
| `Ctrl + E` | Éditer élément sélectionné |
| `Ctrl + D` | Dupliquer élément |
| `Ctrl + S` | Sauvegarder (si form ouvert) |
| `Del` | Supprimer (avec confirmation) |
| `Échap` | Fermer modal/annuler édition |
| `↑ ↓` | Naviguer dans l'arbre |
| `←` | Replier nœud |
| `→` | Déplier nœud |
| `Ctrl + F` | Focus recherche |

### 4. Auto-Save

#### Fonctionnement
- Sauvegarde automatique après 2s d'inactivité
- Indicateur "Sauvegarde..." pendant l'opération
- "✓ Enregistré à HH:MM" quand terminé
- Gestion conflits (si modification simultanée)

#### States
- 🟡 **En cours d'édition** : Indicateur jaune
- 🔵 **Sauvegarde...** : Spinner bleu
- 🟢 **Enregistré** : Checkmark vert + timestamp
- 🔴 **Erreur** : Icône rouge + message

### 5. Sélection Multiple

#### Actions de masse
- Sélection via `Shift + Clic` ou checkboxes
- Barre d'actions flottante (copier, déplacer, supprimer)
- Export sélection en Excel
- Modification en masse (ex: changer pôle de 5 services)

---

## 🏗️ Architecture Technique

### Frontend

#### Librairies
```html
<!-- Drag & Drop -->
<script src="https://cdn.jsdelivr.net/npm/sortablejs@1.15.0/Sortable.min.js"></script>

<!-- Ou utiliser SortableJS via npm si bundler -->
```

#### Structure JavaScript
```javascript
// app/static/js/structure-interactive.js

class StructureEditor {
  constructor(treeElement) {
    this.tree = treeElement;
    this.selectedNode = null;
    this.autoSaveTimeout = null;
    this.initInlineEdit();
    this.initDragDrop();
    this.initKeyboardShortcuts();
  }
  
  initInlineEdit() {
    // Double-clic pour éditer
    this.tree.addEventListener('dblclick', (e) => {
      const field = e.target.closest('[data-editable]');
      if (field) this.startEdit(field);
    });
  }
  
  startEdit(element) {
    const originalValue = element.textContent;
    const input = document.createElement('input');
    input.value = originalValue;
    input.className = 'inline-edit-input';
    
    element.replaceWith(input);
    input.focus();
    input.select();
    
    input.addEventListener('blur', () => this.saveEdit(input, element));
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') this.saveEdit(input, element);
      if (e.key === 'Escape') this.cancelEdit(input, element, originalValue);
    });
  }
  
  async saveEdit(input, originalElement) {
    const newValue = input.value;
    const itemId = originalElement.dataset.itemId;
    const itemType = originalElement.dataset.itemType;
    const field = originalElement.dataset.field;
    
    try {
      const response = await fetch(`/api/structure/${itemType}/${itemId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ field, value: newValue })
      });
      
      if (response.ok) {
        originalElement.textContent = newValue;
        input.replaceWith(originalElement);
        this.showSaveIndicator('success');
      } else {
        throw new Error('Save failed');
      }
    } catch (error) {
      this.showSaveIndicator('error');
      this.cancelEdit(input, originalElement, input.value);
    }
  }
  
  initDragDrop() {
    // Utiliser SortableJS sur chaque liste
    const lists = this.tree.querySelectorAll('[data-sortable]');
    lists.forEach(list => {
      new Sortable(list, {
        group: 'structure',
        animation: 150,
        handle: '.drag-handle',
        onEnd: (evt) => this.handleDrop(evt)
      });
    });
  }
  
  async handleDrop(evt) {
    const itemId = evt.item.dataset.itemId;
    const itemType = evt.item.dataset.itemType;
    const newParentId = evt.to.dataset.parentId;
    const newParentType = evt.to.dataset.parentType;
    
    try {
      await fetch('/api/structure/move', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          item_type: itemType,
          item_id: itemId,
          target_type: newParentType,
          target_id: newParentId,
          position: evt.newIndex
        })
      });
      
      this.showNotification('Déplacé avec succès', 'success');
    } catch (error) {
      evt.item.remove();
      evt.from.insertBefore(evt.item, evt.from.children[evt.oldIndex]);
      this.showNotification('Erreur déplacement', 'error');
    }
  }
  
  initKeyboardShortcuts() {
    document.addEventListener('keydown', (e) => {
      if (e.ctrlKey || e.metaKey) {
        switch(e.key) {
          case 'n': e.preventDefault(); this.createNew(); break;
          case 'e': e.preventDefault(); this.editSelected(); break;
          case 'd': e.preventDefault(); this.duplicateSelected(); break;
          case 'f': e.preventDefault(); this.focusSearch(); break;
        }
      }
      
      if (e.key === 'Delete' && this.selectedNode) {
        e.preventDefault();
        this.deleteSelected();
      }
    });
  }
}

// Initialisation
document.addEventListener('DOMContentLoaded', () => {
  const tree = document.getElementById('structure-tree');
  if (tree) {
    window.structureEditor = new StructureEditor(tree);
  }
});
```

### Backend

#### Nouveaux Endpoints

```python
# app/routers/structure_interactive.py

@router.patch("/{entity_type}/{entity_id}")
async def update_field(
    entity_type: str,
    entity_id: int,
    field: str = Body(...),
    value: str = Body(...),
    session: Session = Depends(get_session)
):
    """Mise à jour d'un champ unique en inline"""
    # Validation + update
    pass

@router.post("/move")
async def move_entity(
    item_type: str = Body(...),
    item_id: int = Body(...),
    target_type: str = Body(...),
    target_id: int = Body(...),
    position: Optional[int] = Body(None),
    session: Session = Depends(get_session)
):
    """Déplacement d'entité dans la hiérarchie"""
    # Validation + update foreign keys
    pass
```

---

## 🎨 Design Patterns

### Édition Inline
```html
<div class="tree-node">
  <span class="drag-handle">⋮⋮</span>
  <span class="node-icon">🏛️</span>
  <span 
    data-editable 
    data-item-id="123" 
    data-item-type="service" 
    data-field="nom"
    class="node-name"
  >
    Cardiologie
  </span>
  <span class="edit-indicator hidden">
    <svg class="spinner">...</svg>
  </span>
</div>
```

### Drag Handle
```css
.drag-handle {
  opacity: 0;
  cursor: grab;
  transition: opacity 0.2s;
}

.tree-node:hover .drag-handle {
  opacity: 1;
}

.drag-handle:active {
  cursor: grabbing;
}
```

### Save Indicator
```html
<div class="save-indicator" data-state="saved">
  <svg class="icon-spinner hidden">...</svg>
  <svg class="icon-check">✓</svg>
  <span class="save-text">Enregistré à 15:32</span>
</div>
```

---

## ✅ Plan de Développement

### Sprint 5.1 : Édition Inline _(1 jour)_
- [ ] Endpoint PATCH /structure/{type}/{id}
- [ ] JavaScript StructureEditor class
- [ ] Double-clic → input avec sauvegarde
- [ ] Validation champs (codes uniques, formats)
- [ ] Indicateurs visuels (spinner, checkmark)

### Sprint 5.2 : Drag & Drop _(1 jour)_
- [ ] Intégration SortableJS
- [ ] Drag handles sur chaque élément
- [ ] Endpoint POST /structure/move
- [ ] Validation règles métier
- [ ] Animations smooth

### Sprint 5.3 : Raccourcis & Auto-save _(0.5 jour)_
- [ ] Gestionnaire raccourcis clavier
- [ ] Auto-save après 2s inactivité
- [ ] Panneau aide raccourcis (? ou F1)
- [ ] État sauvegarde temps réel

### Sprint 5.4 : Sélection Multiple _(0.5 jour)_
- [ ] Checkboxes + Shift-clic
- [ ] Barre actions flottante
- [ ] Actions de masse (déplacer, supprimer)
- [ ] Export sélection

---

## 📌 Notes Importantes

⚠️ **Conflits d'édition** : Utiliser `updated_at` + version pour détecter modifications concurrentes

⚠️ **Performance** : Pour >1000 nœuds, virtualiser l'arbre (render only visible)

⚠️ **Accessibilité** : Conserver navigation clavier et screen reader

💡 **Progressive Enhancement** : Fonctionnalités JS optionnelles, base HTML fonctionnelle

🔒 **Validation** : Règles métier strictes (ex: Service doit avoir un Pôle)

---

**Prêt pour implémentation ! 🚀**
