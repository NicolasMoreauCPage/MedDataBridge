/**
 * StructureEditor - Gestion édition inline et drag & drop
 * Phase 5 - UX Moderne
 */

class StructureEditor {
    constructor(treeElement) {
        this.tree = treeElement;
        this.selectedNode = null;
        this.autoSaveTimeout = null;
        this.editingElement = null;
        
        this.init();
    }
    
    init() {
        this.initInlineEdit();
        this.initKeyboardShortcuts();
        this.initDragDrop();
        console.log('✅ StructureEditor initialized');
    }
    
    // ========================================
    // ÉDITION INLINE
    // ========================================
    
    initInlineEdit() {
        // Double-clic sur éléments éditables
        this.tree.addEventListener('dblclick', (e) => {
            const field = e.target.closest('[data-editable]');
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
        input.className = 'inline-edit-input px-2 py-1 border border-blue-400 rounded focus:outline-none focus:ring-2 focus:ring-blue-500';
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
            alert('La valeur ne peut pas être vide');
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
            
            console.log('✅ Saved:', field, '=', newValue);
            
        } catch (error) {
            console.error('❌ Save error:', error);
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
        
        sortableLists.forEach(list => {
            new Sortable(list, {
                group: 'structure',
                animation: 150,
                handle: '.drag-handle',
                ghostClass: 'bg-blue-100',
                chosenClass: 'bg-blue-50',
                dragClass: 'opacity-50',
                
                onStart: (evt) => {
                    console.log('🎯 Drag start:', evt.item);
                },
                
                onEnd: async (evt) => {
                    await this.handleDrop(evt);
                }
            });
        });
        
        console.log('✅ Drag & drop initialized on', sortableLists.length, 'lists');
    }
    
    async handleDrop(evt) {
        const item = evt.item;
        const itemId = parseInt(item.dataset.itemId);
        const itemType = item.dataset.itemType;
        
        const newParent = evt.to.closest('[data-parent-id]');
        const newParentId = parseInt(newParent.dataset.parentId);
        const newParentType = newParent.dataset.parentType;
        
        console.log(`📦 Moving ${itemType} #${itemId} to ${newParentType} #${newParentId}`);
        
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
            
            console.log('✅ Moved successfully');
            
        } catch (error) {
            console.error('❌ Move error:', error);
            
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
            
            // Delete
            if (e.key === 'Delete' && this.selectedNode) {
                e.preventDefault();
                this.deleteSelected();
            }
            
            // Escape
            if (e.key === 'Escape') {
                this.closeModals();
            }
        });
        
        console.log('✅ Keyboard shortcuts initialized');
        this.showShortcutsHelp();
    }
    
    createNew() {
        console.log('🆕 Create new (TODO: ouvrir modal approprié)');
        // TODO: Ouvrir le modal de création selon le contexte
        this.showNotification('Ctrl+N - Créer (à implémenter)', 'info');
    }
    
    editSelected() {
        if (!this.selectedNode) {
            this.showNotification('Aucun élément sélectionné', 'warning');
            return;
        }
        console.log('✏️ Edit selected:', this.selectedNode);
        // TODO: Ouvrir modal d'édition
        this.showNotification('Ctrl+E - Éditer (à implémenter)', 'info');
    }
    
    async duplicateSelected() {
        if (!this.selectedNode) {
            this.showNotification('Aucun élément sélectionné', 'warning');
            return;
        }
        
        const itemId = this.selectedNode.dataset.itemId;
        const itemType = this.selectedNode.dataset.itemType;
        
        const newCode = prompt('Code du duplicata:');
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
            
            // TODO: Rafraîchir l'arbre ou insérer le nouvel élément
            setTimeout(() => location.reload(), 1000);
            
        } catch (error) {
            this.showNotification(`Erreur: ${error.message}`, 'error');
        }
    }
    
    deleteSelected() {
        if (!this.selectedNode) return;
        
        const itemName = this.selectedNode.querySelector('[data-field="nom"]')?.textContent || 'cet élément';
        const confirmed = confirm(`Supprimer "${itemName}" ?\n\n⚠️ Cette action est irréversible.`);
        
        if (confirmed) {
            console.log('🗑️ Delete:', this.selectedNode);
            // TODO: Implémenter DELETE endpoint
            this.showNotification('Delete - à implémenter', 'info');
        }
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
    
    showShortcutsHelp() {
        // Ajouter un petit panneau d'aide en bas à droite
        const helpPanel = document.createElement('div');
        helpPanel.className = 'fixed bottom-4 right-4 bg-white border border-gray-300 rounded-lg shadow-lg p-4 text-xs hidden';
        helpPanel.id = 'shortcuts-help';
        helpPanel.innerHTML = `
            <div class="font-bold mb-2">⌨️ Raccourcis clavier</div>
            <div class="space-y-1 text-gray-600">
                <div><kbd class="px-1 bg-gray-100 border rounded">Ctrl+N</kbd> Nouveau</div>
                <div><kbd class="px-1 bg-gray-100 border rounded">Ctrl+E</kbd> Éditer</div>
                <div><kbd class="px-1 bg-gray-100 border rounded">Ctrl+D</kbd> Dupliquer</div>
                <div><kbd class="px-1 bg-gray-100 border rounded">Ctrl+F</kbd> Rechercher</div>
                <div><kbd class="px-1 bg-gray-100 border rounded">Del</kbd> Supprimer</div>
                <div><kbd class="px-1 bg-gray-100 border rounded">Esc</kbd> Fermer/Annuler</div>
            </div>
            <button onclick="this.parentElement.classList.add('hidden')" class="mt-2 text-blue-600 hover:underline">Fermer</button>
        `;
        document.body.appendChild(helpPanel);
        
        // Bouton pour afficher l'aide
        const helpBtn = document.createElement('button');
        helpBtn.className = 'fixed bottom-4 right-4 bg-blue-600 text-white w-10 h-10 rounded-full shadow-lg hover:bg-blue-700';
        helpBtn.innerHTML = '?';
        helpBtn.title = 'Raccourcis clavier';
        helpBtn.onclick = () => helpPanel.classList.toggle('hidden');
        document.body.appendChild(helpBtn);
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
        const colors = {
            success: 'bg-green-100 border-green-400 text-green-700',
            error: 'bg-red-100 border-red-400 text-red-700',
            warning: 'bg-yellow-100 border-yellow-400 text-yellow-700',
            info: 'bg-blue-100 border-blue-400 text-blue-700'
        };
        
        const notification = document.createElement('div');
        notification.className = `fixed top-4 right-4 border-l-4 p-4 rounded shadow-lg z-50 ${colors[type]}`;
        notification.innerHTML = `
            <div class="flex items-center justify-between">
                <span>${message}</span>
                <button onclick="this.parentElement.parentElement.remove()" class="ml-4 font-bold">&times;</button>
            </div>
        `;
        
        document.body.appendChild(notification);
        
        // Auto-remove après 4s
        setTimeout(() => {
            notification.style.transition = 'opacity 0.3s';
            notification.style.opacity = '0';
            setTimeout(() => notification.remove(), 300);
        }, 4000);
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
