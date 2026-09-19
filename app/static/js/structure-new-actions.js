/* Actions de navigation, recherche et traitement en lot de la vue structure.
 * Ce script classique partage volontairement l'état de structure_new.html.
 */

function toggleNode(nodeId, event) {
    event.stopPropagation();
    const button = event.currentTarget;
    const icon = button.querySelector('svg');

    if (expandedNodes.has(nodeId)) {
        expandedNodes.delete(nodeId);
        icon.classList.remove('rotate-90');
    } else {
        expandedNodes.add(nodeId);
        icon.classList.add('rotate-90');
    }
    renderStructure();
}

function expandAll() {
    document.querySelectorAll('.structure-node').forEach(node => {
        expandedNodes.add(node.dataset.nodeId);
    });
    renderStructure();
}

function collapseAll() {
    expandedNodes.clear();
    renderStructure();
}

function filterStructure() {
    const searchTerm = document.getElementById('searchInput').value.toLowerCase();
    const typeFilter = document.getElementById('structureTypeFilter').value;
    const statusFilter = document.getElementById('statusFilter').value;

    document.querySelectorAll('.structure-node').forEach(node => {
        const matches = (
            (searchTerm === '' || node.textContent.toLowerCase().includes(searchTerm)) &&
            (typeFilter === '' || node.dataset.type === typeFilter) &&
            (statusFilter === '' || node.dataset.status === statusFilter)
        );
        node.style.display = matches ? '' : 'none';
        if (matches) {
            let parent = node;
            while (parent = document.querySelector(`[data-node-id="${parent.dataset.parent}"]`)) {
                parent.style.display = '';
                expandedNodes.add(parent.dataset.nodeId);
            }
        }
    });

    if (viewMode === 'list') renderListView();
    else if (viewMode === 'cards') renderCardsView();
}

function toggleBulkSelection(type, id) {
    if (!type || !Number.isInteger(id)) return;
    const key = `${type}:${id}`;
    if (bulkSelection.has(key)) bulkSelection.delete(key);
    else bulkSelection.add(key);
    updateBulkBar();
}

function toggleSelectAll(checked) {
    const checkboxes = document.querySelectorAll('.list-row-select');
    bulkSelection.clear();
    checkboxes.forEach(cb => {
        cb.checked = checked;
        if (checked) {
            const id = Number(cb.dataset.id);
            if (cb.dataset.type && Number.isInteger(id)) bulkSelection.add(`${cb.dataset.type}:${id}`);
        }
    });
    updateBulkBar();
}

function updateBulkBar() {
    const bar = document.getElementById('bulkActionsBar');
    const countEl = document.getElementById('bulkSelectionCount');
    if (!bar || !countEl) return;
    const count = bulkSelection.size;
    countEl.textContent = count.toString();
    bar.classList.toggle('hidden', count === 0);
}

function clearBulkSelection() {
    bulkSelection.clear();
    const listSelectAll = document.getElementById('listSelectAll');
    if (listSelectAll) listSelectAll.checked = false;
    document.querySelectorAll('.list-row-select').forEach(cb => {
        cb.checked = false;
    });
    updateBulkBar();
}

async function applyBulkAction(action) {
    if (bulkSelection.size === 0) return;
    const readable = action === 'activate' ? 'activer' : action === 'deactivate' ? 'désactiver' : action;
    if (!['activate', 'deactivate'].includes(action)) {
        showError('Action en lot non supportée');
        return;
    }
    if (!window.PameliaUi?.confirm) {
        showError("Le dialogue de confirmation n'est pas disponible.");
        return;
    }
    const confirmed = await window.PameliaUi.confirm({
        title: 'Confirmer l’action en lot',
        message: `Voulez-vous vraiment ${readable} ${bulkSelection.size} élément(s) ?`,
        acceptLabel: readable.charAt(0).toUpperCase() + readable.slice(1),
        variant: action === 'deactivate' ? 'danger' : 'primary',
    });
    if (!confirmed) return;

    const items = Array.from(bulkSelection).map(key => {
        const [type, idStr] = key.split(':');
        return { type, id: parseInt(idStr, 10) };
    }).filter(item => !Number.isNaN(item.id));
    if (items.length === 0) {
        showError('Aucun élément valide à traiter');
        return;
    }
    try {
        const { data } = await window.medbridgeHttp.post('/api/structure/bulk-action', { action, items });
        showNotification(`${data.updated || 0} élément(s) mis à jour`, 'success');
        clearBulkSelection();
        initializeStructure();
    } catch (error) {
        console.error('Bulk action error', error);
        showError("Impossible de réaliser l'action en lot");
    }
}

function showError(message) {
    console.error(message);
    showNotification(message, 'error');
}

function showNotification(message, type = 'info') {
    if (window.toastSystem?.show) {
        window.toastSystem.show(message, type);
        return;
    }
    console.info(message);
}

function editNode(type, id) {
    if (!type || !id) return;
    const paths = {
        eg: `/structure/eg/${id}/edit`,
        pole: `/structure/poles/${id}/edit`,
        service: `/structure/services/${id}/edit`,
        uf: `/structure/ufs/${id}/edit`,
        uh: `/structure/chambres/new?uh_id=${id}`,
        chambre: `/structure/chambres/${id}/edit`,
        lit: `/structure/lits/${id}/edit`,
    };
    const url = paths[type];
    if (!url) {
        console.warn('Type non éditable dans cette vue:', type, id);
        return;
    }
    window.location.href = url;
}
