/**
 * StructureEditor - Gestion édition inline et drag & drop
 * Phase 5 - UX Moderne
 */

class StructureEditor {
    constructor(treeElement) {
        this.tree = treeElement;
        this.selectedNode = null;
        this.selectedNodes = new Set();
        this.autoSaveTimeout = null;
        this.editingElement = null;
        
        this.init();
    }
    
    init() {
        this.initInlineEdit();
        this.initSelection();
        this.initKeyboardShortcuts();
        this.initDragDrop();
    }
    
    // ========================================
    // ÉDITION INLINE
    // ========================================
    
    initInlineEdit() {
        // Double-clic sur éléments éditables
        this.tree.addEventListener('dblclick', (e) => {
            const card = e.target.closest('.structure-card');
            const field = e.target.closest('[data-editable]') || card?.querySelector('[data-editable][data-field="name"]');
            if (field && !this.editingElement) {
                e.preventDefault();
                e.stopPropagation();
                this.startEdit(field);
            }
        });
    }
    
    startEdit(element) {
        if (this.editingElement) return;
        
        const originalValue = element.textContent.trim();
        const itemId = element.dataset.itemId;
        const itemType = element.dataset.itemType;
        const field = element.dataset.field;
        
        // Créer input
        const input = document.createElement('input');
        input.type = 'text';
        input.value = originalValue;
        input.className = 'inline-edit-input inline-edit-name inline-edit-mode px-2 py-1 border border-blue-400 rounded focus:outline-none focus:ring-2 focus:ring-blue-500';
        input.style.width = `${element.offsetWidth + 20}px`;
        
        // Remplacer l'élément
        element.replaceWith(input);
        input.focus();
        input.select();
        
        this.editingElement = {
            input,
            originalElement: element,
            originalValue,
            itemId,
            itemType,
            field
        };
        
        // Events
        input.addEventListener('blur', () => this.saveEdit());
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                this.saveEdit();
            } else if (e.key === 'Escape') {
                e.preventDefault();
                this.cancelEdit();
            }
        });
    }

    initSelection() {
        this.tree.addEventListener('click', (event) => {
            const card = event.target.closest('.structure-card');
            if (!card || this.editingElement) return;
            if (event.ctrlKey || event.metaKey) {
                this.selectedNodes.has(card) ? this.selectedNodes.delete(card) : this.selectedNodes.add(card);
            } else {
                this.selectedNodes.clear();
                this.selectedNodes.add(card);
            }
            this.selectedNode = this.selectedNodes.values().next().value || null;
            this.renderSelection();
        });
    }

    renderSelection() {
        this.tree.querySelectorAll('.structure-card').forEach((card) => {
            card.classList.toggle('selected', this.selectedNodes.has(card));
        });
    }

    selectAll() {
        this.selectedNodes = new Set(this.tree.querySelectorAll('.structure-card'));
        this.selectedNode = this.selectedNodes.values().next().value || null;
        this.renderSelection();
    }

    clearSelection() {
        this.selectedNodes.clear();
        this.selectedNode = null;
        this.renderSelection();
    }
    
    async saveEdit() {
        if (!this.editingElement) return;
        
        const { input, originalElement, originalValue, itemId, itemType, field } = this.editingElement;
        const newValue = input.value.trim();
        
        // Pas de changement
        if (newValue === originalValue) {
            this.cancelEdit();
            return;
        }
        
        // Validation
        if (!newValue) {
            this.showNotification('La valeur ne peut pas être vide', 'warning');
            input.focus();
            return;
        }
        
        // Afficher indicateur de sauvegarde
        const spinner = this.createSpinner();
        input.after(spinner);
        input.disabled = true;
        
        try {
            const response = await fetch(`/api/structure/${itemType}/${itemId}`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ [field]: newValue })
            });
            
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Erreur de sauvegarde');
            }
            
            const data = await response.json();
            
            // Succès - Restaurer l'élément avec nouvelle valeur
            originalElement.textContent = newValue;
            input.replaceWith(originalElement);
            spinner.remove();
            
            this.showSaveIndicator('success', originalElement);
            this.editingElement = null;
            
        } catch (error) {
            spinner.remove();
            input.disabled = false;
            input.focus();
            
            this.showNotification(`Erreur: ${error.message}`, 'error');
        }
    }
    
    cancelEdit() {
        if (!this.editingElement) return;
        
        const { input, originalElement, originalValue } = this.editingElement;
        originalElement.textContent = originalValue;
        input.replaceWith(originalElement);
        this.editingElement = null;
    }
    
    // ========================================
    // DRAG & DROP
    // ========================================
    
    initDragDrop() {
        // Pour chaque liste d'éléments dans l'arbre
        const sortableLists = this.tree.querySelectorAll('[data-sortable]');
        if (typeof window.Sortable !== 'function') {
            this.initNativeDragDrop(sortableLists);
            return;
        }
        
        sortableLists.forEach(list => {
            new Sortable(list, {
                group: 'structure',
                animation: 150,
                handle: '.drag-handle',
                ghostClass: 'bg-blue-100',
                chosenClass: 'bg-blue-50',
                dragClass: 'opacity-50',
                
                onStart: (evt) => {
            // L'état visuel est géré par Sortable.
                },
                
                onEnd: async (evt) => {
                    await this.handleDrop(evt);
                }
            });
        });
        
    }

    initNativeDragDrop(sortableLists) {
        let draggedItem = null;
        let sourceList = null;
        let sourceIndex = -1;
        let didDrop = false;

        const directItems = (list) => Array.from(list.children).filter(
            (item) => item.dataset.itemId && item.dataset.itemType,
        );
        const indexInList = (item, list) => directItems(list).indexOf(item);

        sortableLists.forEach((list) => {
            directItems(list).forEach((item) => {
                item.draggable = true;
                item.dataset.nativeDnd = 'true';
                item.addEventListener('dragstart', (event) => {
                    draggedItem = item;
                    sourceList = list;
                    sourceIndex = indexInList(item, list);
                    didDrop = false;
                    item.classList.add('opacity-50');
                    event.dataTransfer.effectAllowed = 'move';
                    event.dataTransfer.setData('text/plain', item.dataset.itemId);
                });
                item.addEventListener('dragend', () => {
                    item.classList.remove('opacity-50');
                    if (!didDrop && sourceList && sourceIndex >= 0) {
                        sourceList.insertBefore(item, sourceList.children[sourceIndex] || null);
                    }
                    draggedItem = null;
                    sourceList = null;
                    sourceIndex = -1;
                });
            });

            list.addEventListener('dragover', (event) => {
                if (!draggedItem) return;
                event.preventDefault();
                event.dataTransfer.dropEffect = 'move';
                const target = event.target.closest('[data-item-id][data-item-type]');
                if (!target || target.parentElement !== list || target === draggedItem) return;
                const bounds = target.getBoundingClientRect();
                list.insertBefore(draggedItem, event.clientY < bounds.top + bounds.height / 2 ? target : target.nextSibling);
            });

            list.addEventListener('drop', async (event) => {
                if (!draggedItem || !sourceList) return;
                event.preventDefault();
                const newIndex = indexInList(draggedItem, list);
                didDrop = true;
                await this.handleDrop({
                    item: draggedItem,
                    from: sourceList,
                    to: list,
                    oldIndex: sourceIndex,
                    newIndex,
                });
            });
        });
    }
    
    async handleDrop(evt) {
        const item = evt.item;
        const itemId = parseInt(item.dataset.itemId);
        const itemType = item.dataset.itemType;
        
        const newParent = evt.to.closest('[data-parent-id]');
        const newParentId = parseInt(newParent.dataset.parentId);
        const newParentType = newParent.dataset.parentType;
        
        // Indicateur de chargement
        const originalHTML = item.innerHTML;
        item.innerHTML = `<span class="text-gray-400">⏳ Déplacement...</span>`;
        
        try {
            const response = await fetch('/api/structure/move', {
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
            
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Erreur de déplacement');
            }
            
            const data = await response.json();
            
            // Restaurer HTML
            item.innerHTML = originalHTML;
            this.showNotification('✓ Déplacé avec succès', 'success');
            
        } catch (error) {
            // Annuler le déplacement visuellement
            item.remove();
            evt.from.insertBefore(item, evt.from.children[evt.oldIndex] || null);
            item.innerHTML = originalHTML;
            
            this.showNotification(`Erreur: ${error.message}`, 'error');
        }
    }
    
    // ========================================
    // RACCOURCIS CLAVIER
    // ========================================
    
    initKeyboardShortcuts() {
        document.addEventListener('keydown', (e) => {
            // Si on est en train d'éditer, ignorer
            if (this.editingElement) return;
            
            // Ctrl/Cmd + Key
            if (e.ctrlKey || e.metaKey) {
                switch(e.key.toLowerCase()) {
                    case 'n':
                        e.preventDefault();
                        this.createNew();
                        break;
                    case 'a':
                        e.preventDefault();
                        this.selectAll();
                        break;
                    case 'e':
                        e.preventDefault();
                        this.editSelected();
                        break;
                    case 'd':
                        e.preventDefault();
                        this.duplicateSelected();
                        break;
                    case 'f':
                        e.preventDefault();
                        this.focusSearch();
                        break;
                    case 's':
                        e.preventDefault();
                        this.saveIfFormOpen();
                        break;
                }
            }
            
            // Escape
            if (e.key === 'Escape') {
                if (this.editingElement) this.cancelEdit();
                this.clearSelection();
                this.closeModals();
            }
        });
        
    }
    
    createNew() {
        window.location.assign('/structure/wizard');
    }
    
    editSelected() {
        if (!this.selectedNode) {
            this.showNotification('Aucun élément sélectionné', 'warning');
            return;
        }
        const editable = this.selectedNode.querySelector('[data-editable][data-field="name"]');
        if (editable) this.startEdit(editable);
    }
    
    async duplicateSelected() {
        if (!this.selectedNode) {
            this.showNotification('Aucun élément sélectionné', 'warning');
            return;
        }
        
        const itemId = this.selectedNode.dataset.itemId;
        const itemType = this.selectedNode.dataset.itemType;
        
        const newCode = await this.requestDuplicateCode();
        if (!newCode) return;
        
        try {
            const response = await fetch('/api/structure/duplicate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    entity_type: itemType,
                    entity_id: parseInt(itemId),
                    new_code: newCode
                })
            });
            
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail);
            }
            
            const data = await response.json();
            this.showNotification('✓ Duplicaté avec succès', 'success');
            
            setTimeout(() => location.reload(), 1000);
            
        } catch (error) {
            this.showNotification(`Erreur: ${error.message}`, 'error');
        }
    }

    requestDuplicateCode() {
        const dialog = document.getElementById('structure-duplicate-dialog');
        const input = document.getElementById('structure-duplicate-code');
        if (!dialog || !input) return Promise.resolve(null);

        input.value = '';
        dialog.showModal();
        window.setTimeout(() => input.focus(), 0);
        return new Promise((resolve) => {
            dialog.addEventListener('close', () => {
                resolve(dialog.returnValue === 'confirm' ? input.value.trim() : null);
            }, { once: true });
        });
    }
    
    focusSearch() {
        const searchInput = document.getElementById('search-input') || document.querySelector('input[type="search"]');
        if (searchInput) {
            searchInput.focus();
            searchInput.select();
        }
    }
    
    saveIfFormOpen() {
        const submitBtn = document.querySelector('form button[type="submit"]');
        if (submitBtn) {
            submitBtn.click();
        }
    }
    
    closeModals() {
        const modals = document.querySelectorAll('.modal, [data-modal]');
        modals.forEach(modal => modal.classList.add('hidden'));
    }
    
    // ========================================
    // UI HELPERS
    // ========================================
    
    createSpinner() {
        const spinner = document.createElement('span');
        spinner.className = 'inline-block ml-2';
        spinner.innerHTML = `
            <svg class="animate-spin h-4 w-4 text-blue-600" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
        `;
        return spinner;
    }
    
    showSaveIndicator(status, element) {
        const indicator = document.createElement('span');
        indicator.className = 'inline-block ml-2 text-green-600 animate-fade-out';
        indicator.textContent = '✓';
        
        element.after(indicator);
        
        setTimeout(() => indicator.remove(), 2000);
    }
    
    showNotification(message, type = 'info') {
        window.toastSystem?.show(message, type);
    }
}

// ========================================
// INITIALISATION
// ========================================

document.addEventListener('DOMContentLoaded', () => {
    const tree = document.getElementById('structure-tree');
    
    if (tree) {
        window.structureEditor = new StructureEditor(tree);
    }
});
