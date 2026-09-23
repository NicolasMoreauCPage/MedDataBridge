/* Workspace de la vue structure historique.
 * Les données restent dans le DOM/Jinja ; toute l'interaction vit ici afin
 * d'éviter de maintenir un second bloc JavaScript dans le template.
 */
(() => {
    let currentStructure = null;
    let selectedNode = null;

    const byId = (id) => document.getElementById(id);

    function escapeHtml(value) {
        return String(value ?? "").replace(/[&<>'"]/g, (character) => ({
            "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;",
        }[character]));
    }

    async function loadStructureTree() {
        const filteredEgsInput = byId('filtered_egs');
        let url = '/api/structure/tree';
        if (filteredEgsInput) {
            try {
                const filteredEgs = JSON.parse(filteredEgsInput.value);
                if (Array.isArray(filteredEgs) && filteredEgs.length > 0) {
                    url += `?eg_ids=${filteredEgs.join(',')}`;
                }
            } catch (_) {
                showTreeError('Le filtre établissement est invalide.');
                return;
            }
        }

        try {
            const { data } = await window.medbridgeHttp.get(url);
            currentStructure = data;
            renderTree();
        } catch (_) {
            showTreeError("Impossible de charger l'arborescence.");
        }
    }

    function showTreeError(message) {
        const treeView = byId('treeView');
        if (treeView) treeView.innerHTML = `<p class="text-red-700">${escapeHtml(message)}</p>`;
    }

    function renderTree() {
        const treeView = byId('treeView');
        if (!treeView || !currentStructure) return;
        treeView.innerHTML = renderNode(currentStructure);
    }

    function renderNode(node, level = 0) {
        if (!node || !node.type || node.id === undefined) return '';
        let html = `<button type="button" class="block w-full cursor-pointer p-2 text-left hover:bg-gray-100 dark:hover:bg-slate-700" style="padding-left: ${level * 16}px" data-structure-action="select" data-type="${escapeHtml(node.type)}" data-id="${Number(node.id)}">${escapeHtml(node.name)}</button>`;
        for (const children of [node.poles, node.services]) {
            if (Array.isArray(children)) html += children.map((child) => renderNode(child, level + 1)).join('');
        }
        return html;
    }

    async function selectNode(type, id) {
        if (!type || !Number.isInteger(id)) return;
        selectedNode = { type, id };
        const detailView = byId('detailView');
        if (!detailView) return;
        detailView.setAttribute('aria-busy', 'true');
        try {
            const { data } = await window.medbridgeHttp.get(`/api/structure/${encodeURIComponent(type)}/${id}`);
            renderDetails(data);
        } catch (error) {
            const detail = error?.status ? `Erreur API (${error.status}) : ${error.message}` : 'Impossible de charger les détails.';
            detailView.innerHTML = `<p class="text-red-700 font-bold">${escapeHtml(detail)}</p>`;
        } finally {
            detailView.removeAttribute('aria-busy');
            detailView.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
    }

    function renderDetails(details) {
        const detailView = byId('detailView');
        if (!detailView) return;
        detailView.innerHTML = `
            <div class="space-y-4">
                <h2 class="text-xl font-semibold">${escapeHtml(details.name)}</h2>
                <div class="grid grid-cols-2 gap-4">
                    <div><p class="text-sm text-gray-500">Identifiant</p><p>${escapeHtml(details.identifier)}</p></div>
                    <div><p class="text-sm text-gray-500">Type</p><p>${escapeHtml(details.type)}</p></div>
                </div>
                <div><p class="text-sm text-gray-500">Description</p><p>${escapeHtml(details.description || 'Aucune description')}</p></div>
                <div class="flex justify-end space-x-4 mt-4">
                    <button type="button" data-structure-action="edit" class="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700">Modifier</button>
                </div>
            </div>`;
    }

    function startEdit() {
        if (!selectedNode) return;
        const form = byId('editForm');
        if (!form) return;
        form.classList.remove('hidden');
        loadTypeSpecificFields(selectedNode.type);
        form.querySelector('[name="identifier"]')?.focus();
    }

    function loadTypeSpecificFields(type) {
        const additionalFields = byId('additionalFields');
        if (!additionalFields) return;
        const fields = {
            service: '<label class="block text-sm font-medium text-gray-700">Type de service<select name="service_type" class="mt-1 block w-full rounded-md border-gray-300 shadow-sm"><option value="mco">MCO</option><option value="ssr">SSR</option><option value="psy">PSY</option><option value="had">HAD</option><option value="ehpad">EHPAD</option><option value="usld">USLD</option></select></label>',
            chambre: '<label class="block text-sm font-medium text-gray-700">Type de chambre<select name="type_chambre" class="mt-1 block w-full rounded-md border-gray-300 shadow-sm"><option value="simple">Simple</option><option value="double">Double</option></select></label><label class="block text-sm font-medium text-gray-700">Usage<select name="gender_usage" class="mt-1 block w-full rounded-md border-gray-300 shadow-sm"><option value="mixed">Mixte</option><option value="male">Homme</option><option value="female">Femme</option></select></label>',
            lit: '<label class="block text-sm font-medium text-gray-700">Statut opérationnel<select name="operationalStatus" class="mt-1 block w-full rounded-md border-gray-300 shadow-sm"><option value="libre">Libre</option><option value="occupe">Occupé</option><option value="maintenance">En maintenance</option></select></label>',
        };
        additionalFields.innerHTML = fields[type] || '';
    }

    function cancelEdit() {
        byId('editForm')?.classList.add('hidden');
    }

    async function updateBedGrid() {
        const bedGrid = byId('bedGrid');
        if (!bedGrid) return;
        const values = {
            service_type: byId('serviceFilter')?.value || '',
            uf_id: byId('ufFilter')?.value || '',
            status: byId('statusFilter')?.value || '',
        };
        bedGrid.setAttribute('aria-busy', 'true');
        try {
            const { data: beds } = await window.medbridgeHttp.get(`/api/structure/search/lits-disponibles?${new URLSearchParams(values)}`);
            bedGrid.innerHTML = beds.map((bed) => `<div class="p-4 border rounded-lg ${getStatusClass(bed.operationalStatus)}"><p class="font-medium">${escapeHtml(bed.name)}</p><p class="text-sm text-gray-600">${escapeHtml(bed.chambre?.name)}</p><p class="text-sm">${escapeHtml(bed.operationalStatus)}</p></div>`).join('') || '<p class="col-span-full text-gray-500">Aucun lit ne correspond aux filtres.</p>';
        } catch (_) {
            bedGrid.innerHTML = '<p class="col-span-full text-red-700">Impossible de charger les lits.</p>';
        } finally {
            bedGrid.removeAttribute('aria-busy');
        }
    }

    function getStatusClass(status) {
        return { libre: 'bg-green-50', occupe: 'bg-red-50', maintenance: 'bg-yellow-50' }[status] || '';
    }

    function initialize() {
        const workspace = document.querySelector('[data-structure-legacy-workspace]');
        if (!workspace || workspace.dataset.initialized === 'true') return;
        workspace.dataset.initialized = 'true';
        workspace.addEventListener('click', (event) => {
            const action = event.target.closest('[data-structure-action]')?.dataset.structureAction;
            if (action === 'select') {
                const button = event.target.closest('[data-structure-action]');
                selectNode(button.dataset.type, Number(button.dataset.id));
            } else if (action === 'edit') startEdit();
            else if (action === 'cancel-edit') cancelEdit();
        });
        ['serviceFilter', 'ufFilter', 'statusFilter'].forEach((id) => byId(id)?.addEventListener('change', updateBedGrid));
        loadStructureTree();
        updateBedGrid();
    }

    document.addEventListener('DOMContentLoaded', initialize);
})();
