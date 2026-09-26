// Configuration depuis le backend
const FILTERED_EGS = JSON.parse(document.getElementById('backend-config').textContent);

// État global
let currentStructure = null;
let selectedNode = null;
let expandedNodes = new Set();
let viewMode = 'tree'; // 'tree' | 'list' | 'cards'

// Sélection bulk (mode liste)
const bulkSelection = new Set();

// Statistiques globales structurelles
const structureStats = {
    poles: 0,
    services: 0,
    ufs: 0,
    lits: 0,
};

function escapeHtml(value) {
    const node = document.createElement('span');
    node.textContent = String(value ?? '');
    return node.innerHTML;
}

function safeIdentifier(value) {
    return Number.isInteger(Number(value)) ? String(Number(value)) : '';
}

// Initialisation
document.addEventListener('DOMContentLoaded', () => {
    initializeStructure();
    setupEventListeners();
});

// Configuration des écouteurs d'événements
function setupEventListeners() {
    // Filtres
    document.getElementById('searchInput').addEventListener('input', filterStructure);
    document.getElementById('structureTypeFilter').addEventListener('change', filterStructure);
    document.getElementById('statusFilter').addEventListener('change', filterStructure);
    
    // Boutons d'expansion
    document.getElementById('expandAllBtn').addEventListener('click', expandAll);
    document.getElementById('collapseAllBtn').addEventListener('click', collapseAll);

    // Modes d'affichage
    const treeBtn = document.getElementById('modeTreeBtn');
    const listBtn = document.getElementById('modeListBtn');
    const cardsBtn = document.getElementById('modeCardsBtn');
    if (treeBtn && listBtn && cardsBtn) {
        treeBtn.addEventListener('click', () => setViewMode('tree'));
        listBtn.addEventListener('click', () => setViewMode('list'));
        cardsBtn.addEventListener('click', () => setViewMode('cards'));
        const modeButtons = [treeBtn, listBtn, cardsBtn];
        modeButtons.forEach((button, index) => button.addEventListener('keydown', (event) => {
            const keys = ['ArrowLeft', 'ArrowRight', 'Home', 'End'];
            if (!keys.includes(event.key)) return;
            event.preventDefault();
            const targetIndex = event.key === 'Home' ? 0 : event.key === 'End' ? modeButtons.length - 1 : (index + (event.key === 'ArrowRight' ? 1 : -1) + modeButtons.length) % modeButtons.length;
            const target = modeButtons[targetIndex];
            target.focus();
            setViewMode(target.dataset.viewMode);
        }));
    }

    const listSelectAll = document.getElementById('listSelectAll');
    if (listSelectAll) {
        listSelectAll.addEventListener('change', (e) => toggleSelectAll(e.target.checked));
    }

    document.getElementById('bulk-clear-button')?.addEventListener('click', clearBulkSelection);
    document.getElementById('bulk-activate-button')?.addEventListener('click', () => applyBulkAction('activate'));
    document.getElementById('bulk-deactivate-button')?.addEventListener('click', () => applyBulkAction('deactivate'));

    document.getElementById('listViewBody')?.addEventListener('change', (event) => {
        const checkbox = event.target.closest('.list-row-select');
        if (!checkbox) return;
        toggleBulkSelection(checkbox.dataset.type, Number(checkbox.dataset.id));
    });
    document.getElementById('listViewBody')?.addEventListener('click', (event) => {
        const control = event.target.closest('[data-select-node]');
        if (!control) return;
        selectNode(control.dataset.type, Number(control.dataset.id));
    });
    document.getElementById('cardsViewBody')?.addEventListener('click', (event) => {
        const control = event.target.closest('[data-select-node]');
        if (!control) return;
        selectNode(control.dataset.type, Number(control.dataset.id));
    });

    document.addEventListener('click', (event) => {
        const control = event.target.closest('[data-structure-action]');
        const action = control?.dataset.structureAction;
        if (!action) return;

        const id = Number(control.dataset.nodeId);
        if (action === 'select-node' && control.dataset.nodeType && Number.isInteger(id)) {
            selectNode(control.dataset.nodeType, id);
        }
        if (action === 'toggle-node') {
            toggleNode(control.dataset.treeNodeId, event);
        }
        if (action === 'edit-node' && control.dataset.nodeType && Number.isInteger(id)) {
            editNode(control.dataset.nodeType, id);
        }
    });
}

// Initialisation de la structure
async function initializeStructure() {
    // Strict EJ filtering: if no EGs for current EJ, show message and do not call API
    if (!FILTERED_EGS || FILTERED_EGS.length === 0) {
        document.getElementById('treeView').innerHTML = '<div class="text-slate-500 py-8 text-center">Aucune structure disponible pour cet établissement juridique.</div>';
        return;
    }
    try {
        // Construire l'URL de l'API
        const apiUrl = '/api/structure/tree?eg_ids=' + FILTERED_EGS.join(',');
        // Charger les données par le client commun (timeout et erreurs unifiés).
        const { data } = await window.medbridgeHttp.get(apiUrl);
        currentStructure = data;

        // Calculer les statistiques globales
        computeStructureStats();
        renderKpiCards();

        // Pré-sélection éventuelle depuis l'URL (#node-type-id)
        let preselect = null;
        if (window.location.hash && window.location.hash.startsWith('#node-')) {
            const parts = window.location.hash.substring(1).split('-');
            if (parts.length === 3 && parts[0] === 'node') {
                const type = parts[1];
                const id = parseInt(parts[2], 10);
                if (!Number.isNaN(id)) {
                    preselect = { type, id };
                    const path = findPathInTree(type, id);
                    if (path) {
                        path.forEach(node => {
                            expandedNodes.add(`node-${node.type}-${node.id}`);
                        });
                    }
                }
            }
        }

        // Rendu initial en mode arbre
        renderStructure();

        // Si une structure est indiquée dans l'URL, la sélectionner
        if (preselect) {
            selectNode(preselect.type, preselect.id);
        }
    } catch (error) {
        console.error('Erreur:', error);
        showError('Impossible de charger la structure');
    }
}

// Rendu de la structure
function renderStructure() {
    const treeView = document.getElementById('treeView');
    if (!treeView || !Array.isArray(currentStructure)) return;
    treeView.innerHTML = currentStructure.map(eg => renderNode(eg)).join('');

    // Si on est en mode liste, régénérer aussi la vue liste
    if (viewMode === 'list') {
        renderListView();
    }
}

function renderNode(node, level = 0, parentId = null) {
    const padding = level * 16;
    const nodeId = `node-${node.type}-${node.id}`;
    const hasChildren = node.poles?.length > 0 || node.services?.length > 0 || 
                       node.ufs?.length > 0 || node.unites_hebergement?.length > 0 ||
                       node.chambres?.length > 0 || node.lits?.length > 0;
    
    const icon = getTypeIcon(node.type);

    let html = `
        <div class="structure-node" data-node-id="${escapeHtml(nodeId)}" data-type="${escapeHtml(node.type)}" data-status="${escapeHtml(node.status || '')}" data-parent="${escapeHtml(parentId || '')}">
            <div class="flex items-center gap-2 py-1 px-2 rounded hover:bg-slate-50 cursor-pointer" 
                 style="padding-left: ${padding + 8}px"
                 data-structure-action="select-node" data-node-type="${escapeHtml(node.type)}" data-node-id="${safeIdentifier(node.id)}">
                ${hasChildren ? `
                    <button type="button" class="w-4 h-4 flex items-center justify-center text-slate-400 hover:text-slate-600"
                            data-structure-action="toggle-node" data-tree-node-id="${escapeHtml(nodeId)}">
                        <svg class="w-3 h-3 transform transition-transform ${expandedNodes.has(nodeId) ? 'rotate-90' : ''}"
                             fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/>
                        </svg>
                    </button>
                ` : '<div class="w-4"></div>'}
                <span class="w-5 text-xs">${icon}</span>
                <span class="flex-1 truncate">${escapeHtml(node.name)}</span>
            </div>
    `;

    if (hasChildren && expandedNodes.has(nodeId)) {
        // Récursion sur les enfants
        if (node.poles?.length > 0) {
            html += node.poles.map(pole => renderNode(pole, level + 1, nodeId)).join('');
        }
        if (node.services?.length > 0) {
            html += node.services.map(service => renderNode(service, level + 1, nodeId)).join('');
        }
        if (node.ufs?.length > 0) {
            html += node.ufs.map(uf => renderNode(uf, level + 1, nodeId)).join('');
        }
        if (node.unites_hebergement?.length > 0) {
            html += node.unites_hebergement.map(uh => renderNode(uh, level + 1, nodeId)).join('');
        }
        if (node.chambres?.length > 0) {
            html += node.chambres.map(chambre => renderNode(chambre, level + 1, nodeId)).join('');
        }
        if (node.lits?.length > 0) {
            html += node.lits.map(lit => renderNode(lit, level + 1, nodeId)).join('');
        }
    }

    html += '</div>';
    return html;
}

// Icônes par type de structure
function getTypeIcon(type) {
    switch (type) {
        case 'eg':
            return '🏥';
        case 'pole':
            return '🏢';
        case 'service':
            return '🏛️';
        case 'uf':
            return '🔹';
        case 'uh':
            return '🏠';
        case 'chambre':
            return '🚪';
        case 'lit':
            return '🛏️';
        default:
            return '•';
    }
}

// Rendu de la vue liste à plat
function renderListView() {
    const tbody = document.getElementById('listViewBody');
    if (!tbody) return;

    const rows = [];

    function walk(node, pathLabels) {
        const label = node.name || '';
        const newPath = [...pathLabels, label];
        rows.push({
            id: node.id,
            name: label,
            type: node.type,
            path: newPath.join(' / '),
            status: node.status || null,
        });

        if (node.poles?.length) node.poles.forEach(p => walk(p, newPath));
        if (node.services?.length) node.services.forEach(s => walk(s, newPath));
        if (node.ufs?.length) node.ufs.forEach(u => walk(u, newPath));
        if (node.unites_hebergement?.length) node.unites_hebergement.forEach(uh => walk(uh, newPath));
        if (node.chambres?.length) node.chambres.forEach(c => walk(c, newPath));
        if (node.lits?.length) node.lits.forEach(l => walk(l, newPath));
    }

    currentStructure.forEach(eg => walk(eg, []));

    // Appliquer les filtres de type et de recherche sur la liste
    const searchTerm = document.getElementById('searchInput').value.toLowerCase();
    const typeFilter = document.getElementById('structureTypeFilter').value;
    const statusFilter = document.getElementById('statusFilter').value;

    const filteredRows = rows.filter(row => {
        const matchesSearch = !searchTerm || row.name.toLowerCase().includes(searchTerm) || row.path.toLowerCase().includes(searchTerm);
        const matchesType = !typeFilter || row.type === typeFilter;
        const matchesStatus = !statusFilter || row.status === statusFilter;
        return matchesSearch && matchesType && matchesStatus;
    });

    tbody.innerHTML = filteredRows.map(row => {
        const key = `${row.type}:${row.id}`;
        const checked = bulkSelection.has(key) ? 'checked' : '';
        return `
        <tr class="hover:bg-slate-50">
            <td class="px-2 py-1 w-6">
                <input type="checkbox" class="rounded border-slate-300 list-row-select" ${checked}
                       data-type="${escapeHtml(row.type)}" data-id="${safeIdentifier(row.id)}" aria-label="Sélectionner ${escapeHtml(getTypeLabel(row.type))} ${escapeHtml(row.name)}">
            </td>
            <td class="px-2 py-1 text-slate-600"><button type="button" data-select-node data-type="${escapeHtml(row.type)}" data-id="${safeIdentifier(row.id)}" class="text-left hover:text-blue-700">${escapeHtml(getTypeLabel(row.type))}</button></td>
            <td class="px-2 py-1 text-slate-900"><button type="button" data-select-node data-type="${escapeHtml(row.type)}" data-id="${safeIdentifier(row.id)}" class="text-left hover:text-blue-700">${escapeHtml(row.name)}</button></td>
            <td class="px-2 py-1 text-slate-500"><button type="button" data-select-node data-type="${escapeHtml(row.type)}" data-id="${safeIdentifier(row.id)}" class="text-left hover:text-blue-700">${escapeHtml(row.path)}</button></td>
        </tr>`;
    }).join('');

    updateBulkBar();
}

// Changement de mode d'affichage
function setViewMode(mode) {
    if (!['tree', 'list', 'cards'].includes(mode)) return;
    viewMode = mode;

    const treeView = document.getElementById('treeView');
    const listView = document.getElementById('listView');
    const cardsView = document.getElementById('cardsView');
    const treeBtn = document.getElementById('modeTreeBtn');
    const listBtn = document.getElementById('modeListBtn');
    const cardsBtn = document.getElementById('modeCardsBtn');
    if (!treeView || !listView || !cardsView || !treeBtn || !listBtn || !cardsBtn) return;

    // Masquer toutes les vues
    treeView.classList.add('hidden');
    listView.classList.add('hidden');
    cardsView.classList.add('hidden');
    treeBtn.classList.remove('bg-slate-900', 'text-white');
    listBtn.classList.remove('bg-slate-900', 'text-white');
    cardsBtn.classList.remove('bg-slate-900', 'text-white');
    [treeBtn, listBtn, cardsBtn].forEach(button => button.setAttribute('aria-selected', 'false'));

    if (mode === 'tree') {
        treeView.classList.remove('hidden');
        treeBtn.classList.add('bg-slate-900', 'text-white');
        treeBtn.setAttribute('aria-selected', 'true');
    } else if (mode === 'list') {
        listView.classList.remove('hidden');
        listBtn.classList.add('bg-slate-900', 'text-white');
        listBtn.setAttribute('aria-selected', 'true');
        renderListView();
    } else if (mode === 'cards') {
        cardsView.classList.remove('hidden');
        cardsBtn.classList.add('bg-slate-900', 'text-white');
        cardsBtn.setAttribute('aria-selected', 'true');
        renderCardsView();
    }
}

// Vue cards : mosaïque d'éléments filtrés
function renderCardsView() {
    const container = document.getElementById('cardsViewBody');
    if (!container || !Array.isArray(currentStructure)) return;

    const rows = [];

    function walk(node, pathLabels) {
        const label = node.name || '';
        const newPath = [...pathLabels, label];
        rows.push({
            id: node.id,
            name: label,
            type: node.type,
            path: newPath.join(' / '),
            status: node.status || null,
        });

        if (node.poles?.length) node.poles.forEach(p => walk(p, newPath));
        if (node.services?.length) node.services.forEach(s => walk(s, newPath));
        if (node.ufs?.length) node.ufs.forEach(u => walk(u, newPath));
        if (node.unites_hebergement?.length) node.unites_hebergement.forEach(uh => walk(uh, newPath));
        if (node.chambres?.length) node.chambres.forEach(c => walk(c, newPath));
        if (node.lits?.length) node.lits.forEach(l => walk(l, newPath));
    }

    currentStructure.forEach(eg => walk(eg, []));

    const searchTerm = document.getElementById('searchInput').value.toLowerCase();
    const typeFilter = document.getElementById('structureTypeFilter').value;
    const statusFilter = document.getElementById('statusFilter').value;

    const filtered = rows.filter(row => {
        const matchesSearch = !searchTerm || row.name.toLowerCase().includes(searchTerm) || row.path.toLowerCase().includes(searchTerm);
        const matchesType = !typeFilter || row.type === typeFilter;
        const matchesStatus = !statusFilter || row.status === statusFilter;
        return matchesSearch && matchesType && matchesStatus;
    });

    container.innerHTML = filtered.map(row => `
        <button type="button" data-select-node data-type="${escapeHtml(row.type)}" data-id="${safeIdentifier(row.id)}"
                class="flex flex-col items-start p-3 rounded-lg border border-slate-200 bg-white hover:border-blue-400 hover:shadow-sm text-left">
            <div class="text-[10px] uppercase tracking-wide text-slate-400 mb-1">${escapeHtml(getTypeLabel(row.type))}</div>
            <div class="font-medium text-slate-900">${escapeHtml(row.name)}</div>
            <div class="mt-1 text-[11px] text-slate-500 truncate w-full">${escapeHtml(row.path)}</div>
        </button>
    `).join('');
}

// Calcul des statistiques globales à partir de l'arbre
function computeStructureStats() {
    structureStats.poles = 0;
    structureStats.services = 0;
    structureStats.ufs = 0;
    structureStats.lits = 0;

    if (!Array.isArray(currentStructure)) return;

    function walk(node) {
        switch (node.type) {
            case 'pole':
                structureStats.poles += 1;
                break;
            case 'service':
                structureStats.services += 1;
                break;
            case 'uf':
                structureStats.ufs += 1;
                break;
            case 'lit':
                structureStats.lits += 1;
                break;
        }

        if (node.poles?.length) node.poles.forEach(walk);
        if (node.services?.length) node.services.forEach(walk);
        if (node.ufs?.length) node.ufs.forEach(walk);
        if (node.unites_hebergement?.length) node.unites_hebergement.forEach(walk);
        if (node.chambres?.length) node.chambres.forEach(walk);
        if (node.lits?.length) node.lits.forEach(walk);
    }

    currentStructure.forEach(walk);
}

// Mise à jour des cartes KPI
function renderKpiCards() {
    const polesEl = document.getElementById('kpi-poles');
    const servicesEl = document.getElementById('kpi-services');
    const ufsEl = document.getElementById('kpi-ufs');
    const litsEl = document.getElementById('kpi-lits');

    if (!polesEl || !servicesEl || !ufsEl || !litsEl) return;

    polesEl.textContent = structureStats.poles.toString();
    servicesEl.textContent = structureStats.services.toString();
    ufsEl.textContent = structureStats.ufs.toString();
    litsEl.textContent = structureStats.lits.toString();
}

// Sélection d'un nœud
async function selectNode(type, id) {
    try {
        const { data: details } = await window.medbridgeHttp.get(
            `/api/structure/details/${type}/${id}`,
        );
        selectedNode = { type, id };

        // Afficher le panneau de détails et masquer le message initial
        const selectMessage = document.getElementById('selectMessage');
        const detailInfo = document.getElementById('detailInfo');
        const detailChildren = document.getElementById('detailChildren');

        if (selectMessage) selectMessage.classList.add('hidden');
        if (detailInfo) detailInfo.classList.remove('hidden');
        if (detailChildren) detailChildren.classList.remove('hidden');

        renderDetails(details);

        // Mettre à jour l'URL pour permettre un lien direct
        window.location.hash = `node-${type}-${id}`;

        // Mettre en surbrillance le nœud sélectionné
        document.querySelectorAll('.structure-node > div').forEach(el => {
            el.classList.remove('bg-blue-50', 'text-blue-700');
        });
        document.querySelector(`[data-node-id="node-${type}-${id}"] > div`)
            ?.classList.add('bg-blue-50', 'text-blue-700');
    } catch (error) {
        console.error('Erreur:', error);
        showError('Impossible de charger les détails');
    }
}

// Rendu des détails
function renderDetails(details) {
    // Titre et type
    document.getElementById('detailTitle').textContent = details.name;
    document.getElementById('detailType').textContent = getTypeLabel(details.type);

    // Chemin hiérarchique (breadcrumb interne)
    const pathEl = document.getElementById('detailPath');
    if (pathEl) {
        const path = findPathInTree(details.type, details.id);
        if (path && path.length > 0) {
            pathEl.innerHTML = path.map((node, index) => `
                <button type="button"
                        class="inline-flex items-center text-xs text-slate-500 hover:text-blue-600"
                        data-structure-action="select-node" data-node-type="${escapeHtml(node.type)}" data-node-id="${safeIdentifier(node.id)}">
                    ${escapeHtml(node.name || getTypeLabel(node.type))}
                </button>
            `).join('<span class="mx-1 text-slate-400">/</span>');
            pathEl.classList.remove('hidden');
        } else {
            pathEl.textContent = '';
            pathEl.classList.add('hidden');
        }
    }
    
    // Actions
    const actionsHtml = `
        <button type="button" data-structure-action="edit-node" data-node-type="${details.type}" data-node-id="${details.id}"
                class="px-3 py-1.5 text-sm text-blue-600 hover:text-blue-800">
            Modifier
        </button>
        <span class="px-3 py-1.5 text-sm text-slate-400">
            Voir sur le plan (bientôt disponible)
        </span>
    `;
    document.getElementById('detailActions').innerHTML = actionsHtml;
    
    // Informations détaillées
    let infoHtml = `
        <dl class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
                <dt class="text-sm font-medium text-slate-500">Identifiant</dt>
                <dd class="mt-1">${escapeHtml(details.identifier || '-')}</dd>
            </div>
            <div>
                <dt class="text-sm font-medium text-slate-500">Statut</dt>
                <dd class="mt-1">
                    <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium
                               ${details.status === 'active' ? 'bg-green-100 text-green-800' : 'bg-slate-100 text-slate-800'}">
                        ${details.status === 'active' ? 'Actif' : 'Inactif'}
                    </span>
                </dd>
            </div>
    `;
    
    // Bloc localisation (adresse / étage / aile)
    const hasAddress = details.address_line1 || details.address_city || details.address_postalcode;
    const hasLocationInfo = hasAddress || details.etage || details.aile;
    if (hasLocationInfo) {
        infoHtml += `
            <div class="md:col-span-2">
                <dt class="text-sm font-medium text-slate-500">Localisation</dt>
                <dd class="mt-1 text-sm text-slate-700">
                    ${[details.address_line1, details.address_line2, details.address_line3]
                        .filter(Boolean).map(escapeHtml).join('<br>') || ''}
                    ${details.address_postalcode || details.address_city ? '<br>' : ''}
                    ${[details.address_postalcode, details.address_city].filter(Boolean).map(escapeHtml).join(' ')}
                    ${details.etage ? `<br>Étage : ${escapeHtml(details.etage)}` : ''}
                    ${details.aile ? `<br>Aile : ${escapeHtml(details.aile)}` : ''}
                </dd>
            </div>
        `;
    }

    // Champs spécifiques par type
    if (details.type === 'eg') {
        infoHtml += `
            <div>
                <dt class="text-sm font-medium text-slate-500">FINESS</dt>
                <dd class="mt-1">${escapeHtml(details.finess || '-')}</dd>
            </div>
            <div>
                <dt class="text-sm font-medium text-slate-500">Catégorie</dt>
                <dd class="mt-1">${escapeHtml(details.category_name || details.category_code || '-')}</dd>
            </div>
        `;
    } else if (details.type === 'service') {
        infoHtml += `
            <div>
                <dt class="text-sm font-medium text-slate-500">Type de service</dt>
                <dd class="mt-1">${escapeHtml(details.service_type || '-')}</dd>
            </div>
            <div>
                <dt class="text-sm font-medium text-slate-500">Typologie</dt>
                <dd class="mt-1">${escapeHtml(details.typology || '-')}</dd>
            </div>
        `;
    } else if (details.type === 'uf') {
        infoHtml += `
            <div>
                <dt class="text-sm font-medium text-slate-500">Code UM</dt>
                <dd class="mt-1">${escapeHtml(details.um_code || '-')}</dd>
            </div>
            <div>
                <dt class="text-sm font-medium text-slate-500">Type d'unité</dt>
                <dd class="mt-1">${escapeHtml(details.uf_type || '-')}</dd>
            </div>
        `;
    } else if (details.type === 'uh') {
        infoHtml += `
            <div>
                <dt class="text-sm font-medium text-slate-500">Typologie</dt>
                <dd class="mt-1">${details.typology || '-'}</dd>
            </div>
            <div>
                <dt class="text-sm font-medium text-slate-500">Type d'unité</dt>
                <dd class="mt-1">${details.uf_type || '-'}</dd>
            </div>
        `;
    } else if (details.type === 'chambre' || details.type === 'lit') {
        const isGeneric = details.is_generic ? 'Oui' : 'Non';
        const capacity = details.max_occupancy != null ? details.max_occupancy : '-';
        infoHtml += `
            <div>
                <dt class="text-sm font-medium text-slate-500">Capacité</dt>
                <dd class="mt-1">${capacity}</dd>
            </div>
            <div>
                <dt class="text-sm font-medium text-slate-500">Générique</dt>
                <dd class="mt-1">${isGeneric}</dd>
            </div>
        `;
    }

    // Informations de chambre / genre d'usage
    if (details.type_chambre || details.gender_usage) {
        infoHtml += `
            <div>
                <dt class="text-sm font-medium text-slate-500">Type de chambre</dt>
                <dd class="mt-1">${details.type_chambre || '-'}</dd>
            </div>
            <div>
                <dt class="text-sm font-medium text-slate-500">Genre d'usage</dt>
                <dd class="mt-1">${details.gender_usage || '-'}</dd>
            </div>
        `;
    }

    // Description
    infoHtml += `
            <div class="md:col-span-2">
                <dt class="text-sm font-medium text-slate-500">Description</dt>
                <dd class="mt-1">${escapeHtml(details.description || '-')}</dd>
            </div>
        </dl>
    `;
    document.getElementById('detailInfo').innerHTML = infoHtml;
    
    // Sous-éléments
    renderChildren(details);
}

// Recherche du chemin d'un noeud dans l'arbre courant
function findPathInTree(type, id) {
    if (!Array.isArray(currentStructure)) return null;

    const search = (nodes, currentPath) => {
        for (const node of nodes) {
            const newPath = [...currentPath, node];
            if (node.type === type && node.id === id) {
                return newPath;
            }

            const childGroups = [
                node.poles,
                node.services,
                node.ufs,
                node.unites_hebergement,
                node.chambres,
                node.lits
            ].filter(Array.isArray);

            for (const group of childGroups) {
                const found = search(group, newPath);
                if (found) return found;
            }
        }
        return null;
    };

    return search(currentStructure, []);
}

// Recherche d'un noeud dans l'arbre courant
function findNodeInTree(type, id) {
    if (!Array.isArray(currentStructure)) return null;

    const search = (nodes) => {
        for (const node of nodes) {
            if (node.type === type && node.id === id) {
                return node;
            }

            const childGroups = [
                node.poles,
                node.services,
                node.ufs,
                node.unites_hebergement,
                node.chambres,
                node.lits
            ].filter(Array.isArray);

            for (const group of childGroups) {
                const found = search(group);
                if (found) return found;
            }
        }
        return null;
    };

    return search(currentStructure);
}

// Rendu des sous-éléments
function renderChildren(details) {
    const childrenContainer = document.getElementById('detailChildren');
    if (!childrenContainer || !selectedNode) {
        if (childrenContainer) {
            childrenContainer.innerHTML = '';
            childrenContainer.classList.add('hidden');
        }
        return;
    }

    const node = findNodeInTree(selectedNode.type, selectedNode.id);

    if (!node) {
        childrenContainer.innerHTML = '';
        childrenContainer.classList.add('hidden');
        return;
    }

    let hasChildren = false;
    let childrenHtml = '';

    if (node.poles?.length) {
        hasChildren = true;
        childrenHtml += renderChildrenSection('Pôles', node.poles);
    }
    if (node.services?.length) {
        hasChildren = true;
        childrenHtml += renderChildrenSection('Services', node.services);
    }
    if (node.ufs?.length) {
        hasChildren = true;
        childrenHtml += renderChildrenSection('Unités Fonctionnelles', node.ufs);
    }
    if (node.unites_hebergement?.length) {
        hasChildren = true;
        childrenHtml += renderChildrenSection("Unités d'Hébergement", node.unites_hebergement);
    }
    if (node.chambres?.length) {
        hasChildren = true;
        childrenHtml += renderChildrenSection('Chambres', node.chambres);
    }
    if (node.lits?.length) {
        hasChildren = true;
        childrenHtml += renderChildrenSection('Lits', node.lits);
    }

    childrenContainer.innerHTML = hasChildren ? childrenHtml : '';
    if (hasChildren) {
        childrenContainer.classList.remove('hidden');
    } else {
        childrenContainer.classList.add('hidden');
    }
}

function renderChildrenSection(title, items) {
    return `
        <div class="mb-6 last:mb-0">
            <h4 class="text-sm font-medium text-slate-900 mb-3">${title}</h4>
            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                ${items.map(item => `
                    <div class="flex items-center justify-between p-3 rounded-lg border border-slate-200 bg-slate-50">
                        <div>
                            <p class="font-medium text-slate-900">${item.name}</p>
                            <p class="text-xs text-slate-500">${item.identifier || ''}</p>
                        </div>
                        <button type="button" data-structure-action="select-node" data-node-type="${item.type}" data-node-id="${item.id}"
                                class="text-blue-600 hover:text-blue-800">
                            Voir
                        </button>
                    </div>
                `).join('')}
            </div>
        </div>
    `;
}

// Utilitaires
function getTypeLabel(type) {
    const labels = {
        eg: 'Entité Géographique',
        pole: 'Pôle',
        service: 'Service',
        uf: 'Unité Fonctionnelle',
        uh: 'Unité d\'Hébergement',
        chambre: 'Chambre',
        lit: 'Lit'
    };
    return labels[type] || type;
}
