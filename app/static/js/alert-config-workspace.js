// État global
let currentRules = [];

// Charger les règles au chargement de la page
document.addEventListener('DOMContentLoaded', () => {
    loadRules();
});

// Charger toutes les règles avec filtres
async function loadRules() {
    try {
        const params = new URLSearchParams();
        
        const filterType = document.getElementById('filterType').value;
        const filterSeverity = document.getElementById('filterSeverity').value;
        const filterActive = document.getElementById('filterActive').value;
        
        // Note: Le backend ne supporte pas encore tous les filtres, on filtrera côté client
        
        let { data: rules } = await window.medbridgeHttp.get('/api/alert-config/rules');
        
        // Filtrage côté client
        if (filterType) {
            rules = rules.filter(r => r.alert_type === filterType);
        }
        if (filterSeverity) {
            rules = rules.filter(r => r.severity === filterSeverity);
        }
        if (filterActive === 'true') {
            rules = rules.filter(r => r.is_active === true);
        } else if (filterActive === 'false') {
            rules = rules.filter(r => r.is_active === false);
        }
        
        currentRules = rules;
        renderRules(rules);
    } catch (error) {
        console.error('Erreur:', error);
        document.getElementById('rulesContainer').innerHTML = 
            '<div class="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">Erreur de chargement</div>';
    }
}

// Rendre les règles dans le DOM
function renderRules(rules) {
    const container = document.getElementById('rulesContainer');
    
    if (rules.length === 0) {
        container.innerHTML = `
            <div class="bg-yellow-50 border border-yellow-200 text-yellow-700 px-4 py-3 rounded">
                Aucune règle configurée. Cliquez sur "Initialiser règles par défaut" pour commencer.
            </div>
        `;
        return;
    }
    
    container.innerHTML = rules.map(rule => `
        <div class="alert-config-rule ${rule.severity} bg-white p-4 rounded-lg shadow">
            <div class="flex justify-between items-start">
                <div class="flex-1">
                    <div class="flex items-center space-x-2 mb-2">
                        <h3 class="text-lg font-semibold">${formatAlertType(rule.alert_type)}</h3>
                        <span class="${rule.is_active ? 'alert-config-badge-active' : 'alert-config-badge-inactive'}">
                            ${rule.is_active ? 'Active' : 'Inactive'}
                        </span>
                        <span class="text-sm text-gray-500">
                            ${formatSeverity(rule.severity)}
                        </span>
                    </div>
                    
                    <div class="text-gray-600 mb-2">
                        <strong>Seuil:</strong> ${rule.threshold_value}% 
                        ${rule.um_code ? `| <strong>UM:</strong> ${rule.um_code}` : ''}
                        ${rule.service_id ? `| <strong>Service:</strong> #${rule.service_id}` : ''}
                    </div>
                    
                    ${rule.description ? `<p class="text-sm text-gray-500">${rule.description}</p>` : ''}
                </div>
                
                <div class="flex space-x-2">
                    <button type="button" data-alert-action="edit" data-rule-id="${rule.id}"
                            class="px-3 py-1 bg-blue-100 text-blue-700 rounded hover:bg-blue-200">
                        ✏️ Modifier
                    </button>
                    <button type="button" data-alert-action="toggle" data-rule-id="${rule.id}" data-next-active="${!rule.is_active}"
                            class="px-3 py-1 bg-gray-100 text-gray-700 rounded hover:bg-gray-200">
                        ${rule.is_active ? '⏸️ Désactiver' : '▶️ Activer'}
                    </button>
                    <button type="button" data-alert-action="delete" data-rule-id="${rule.id}"
                            class="px-3 py-1 bg-red-100 text-red-700 rounded hover:bg-red-200">
                        🗑️ Supprimer
                    </button>
                </div>
            </div>
        </div>
    `).join('');
}

// Formatage des types d'alertes
function formatAlertType(type) {
    const types = {
        'suroccupation': '🚨 Suroccupation',
        'tension': '⚠️ Tension Capacitaire',
        'sous_utilisation': '💤 Sous-utilisation',
        'dms_anormale': '⏰ DMS Anormale'
    };
    return types[type] || type;
}

// Formatage des sévérités
function formatSeverity(severity) {
    const severities = {
        'high': '🔴 Haute',
        'medium': '🟡 Moyenne',
        'low': '🔵 Faible'
    };
    return severities[severity] || severity;
}

// Initialiser les règles par défaut
async function initDefaultRules() {
    if (!window.PameliaUi?.confirm) {
        showAlertConfigNotification("Le dialogue de confirmation n'est pas disponible.", 'error');
        return;
    }
    const confirmed = await window.PameliaUi.confirm({
        title: 'Initialiser les règles',
        message: "Initialiser les règles par défaut pour l'EG 1 ?",
        acceptLabel: 'Initialiser',
        variant: 'primary',
    });
    if (!confirmed) return;
    
    try {
        const { data: result } = await window.medbridgeHttp.request(
            '/api/alert-config/rules/init-defaults?eg_id=1',
            { method: 'POST' },
        );
        showAlertConfigNotification(result.message, 'success');
        loadRules();
    } catch (error) {
        console.error('Erreur:', error);
        showAlertConfigNotification("Erreur lors de l'initialisation.", 'error');
    }
}

// Ouvrir modal création
function openCreateModal() {
    document.getElementById('modalTitle').textContent = 'Nouvelle règle d\'alerte';
    document.getElementById('ruleForm').reset();
    document.getElementById('ruleId').value = '';
    document.getElementById('egId').value = '1';
    document.getElementById('isActive').checked = true;
    document.getElementById('ruleModal').classList.remove('hidden');
}

// Modifier une règle
function editRule(ruleId) {
    const rule = currentRules.find(r => r.id === ruleId);
    if (!rule) return;
    
    document.getElementById('modalTitle').textContent = 'Modifier la règle';
    document.getElementById('ruleId').value = rule.id;
    document.getElementById('alertType').value = rule.alert_type;
    document.getElementById('thresholdValue').value = rule.threshold_value;
    document.getElementById('severity').value = rule.severity;
    document.getElementById('egId').value = rule.eg_id;
    document.getElementById('umCode').value = rule.um_code || '';
    document.getElementById('serviceId').value = rule.service_id || '';
    document.getElementById('description').value = rule.description || '';
    document.getElementById('isActive').checked = rule.is_active;
    
    document.getElementById('ruleModal').classList.remove('hidden');
}

// Fermer modal
function closeModal() {
    document.getElementById('ruleModal').classList.add('hidden');
}

// Sauvegarder règle (créer ou modifier)
async function saveRule() {
    const ruleId = document.getElementById('ruleId').value;
    const isEdit = !!ruleId;
    
    const data = {
        alert_type: document.getElementById('alertType').value,
        threshold_value: parseFloat(document.getElementById('thresholdValue').value),
        severity: document.getElementById('severity').value,
        eg_id: parseInt(document.getElementById('egId').value),
        um_code: document.getElementById('umCode').value || null,
        service_id: document.getElementById('serviceId').value ? parseInt(document.getElementById('serviceId').value) : null,
        description: document.getElementById('description').value || null,
        is_active: document.getElementById('isActive').checked
    };
    
    try {
        if (isEdit) {
            // Mise à jour
            const params = new URLSearchParams();
            Object.entries(data).forEach(([key, value]) => {
                if (value !== null) params.append(key, value);
            });
            await window.medbridgeHttp.request(
                `/api/alert-config/rules/${ruleId}?${params}`,
                { method: 'PUT' },
            );
        } else {
            // Création
            const params = new URLSearchParams();
            Object.entries(data).forEach(([key, value]) => {
                if (value !== null) params.append(key, value);
            });
            await window.medbridgeHttp.request(
                `/api/alert-config/rules?${params}`,
                { method: 'POST' },
            );
        }
        
        closeModal();
        showAlertConfigNotification(isEdit ? 'Règle mise à jour.' : 'Règle créée.', 'success');
        loadRules();
    } catch (error) {
        console.error('Erreur:', error);
        showAlertConfigNotification('Erreur lors de la sauvegarde.', 'error');
    }
}

// Activer/Désactiver règle
async function toggleRuleActive(ruleId, newState) {
    try {
        await window.medbridgeHttp.request(
            `/api/alert-config/rules/${ruleId}?is_active=${newState}`,
            { method: 'PUT' },
        );
        
        showAlertConfigNotification(newState ? 'Règle activée.' : 'Règle désactivée.', 'success');
        loadRules();
    } catch (error) {
        console.error('Erreur:', error);
        showAlertConfigNotification('Erreur lors de la mise à jour.', 'error');
    }
}

// Supprimer règle
async function deleteRule(ruleId) {
    if (!window.PameliaUi?.confirm) {
        showAlertConfigNotification("Le dialogue de confirmation n'est pas disponible.", 'error');
        return;
    }
    const confirmed = await window.PameliaUi.confirm({
        title: 'Supprimer la règle',
        message: 'Supprimer cette règle ?',
        acceptLabel: 'Supprimer',
        variant: 'danger',
    });
    if (!confirmed) return;
    
    try {
        await window.medbridgeHttp.request(`/api/alert-config/rules/${ruleId}`, {
            method: 'DELETE',
        });
        
        showAlertConfigNotification('Règle supprimée.', 'success');
        loadRules();
    } catch (error) {
        console.error('Erreur:', error);
        showAlertConfigNotification('Erreur lors de la suppression.', 'error');
    }
}

function showAlertConfigNotification(message, type = 'info') {
    if (window.toastSystem?.show) {
        window.toastSystem.show(message, type);
        return;
    }
    console.info(message);
}


const workspace = document.querySelector('[data-alert-config]');
workspace?.querySelectorAll('[data-alert-filter]').forEach((filter) => {
    filter.addEventListener('change', loadRules);
});
workspace?.querySelector('[data-alert-action="init-defaults"]')?.addEventListener('click', initDefaultRules);
workspace?.querySelector('[data-alert-action="create"]')?.addEventListener('click', openCreateModal);
workspace?.addEventListener('click', (event) => {
    const actionButton = event.target.closest('[data-alert-action]');
    const action = actionButton?.dataset.alertAction;
    const ruleId = Number.parseInt(actionButton?.dataset.ruleId || '', 10);

    if (!Number.isInteger(ruleId)) return;
    if (action === 'edit') editRule(ruleId);
    if (action === 'toggle') toggleRuleActive(ruleId, actionButton.dataset.nextActive === 'true');
    if (action === 'delete') deleteRule(ruleId);
});
document.querySelector('[data-alert-action="close"]')?.addEventListener('click', closeModal);
document.querySelector('[data-alert-action="save"]')?.addEventListener('click', saveRule);
