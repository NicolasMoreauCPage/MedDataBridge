/* Saisie, recherche et modèles du workspace de cotations. */
"use strict";

const cotationWorkspace = document.querySelector("[data-cotation-entry]");
const dossierId = Number(cotationWorkspace?.dataset.dossierId);

let selectedModificateurs = [];
let currentActeType = 'ccam';
let saveAndContinue = false;
const cotationSearchControllers = new Map();
const cotationSuggestions = new Map();

function escapeHtml(value) {
    const node = document.createElement('span');
    node.textContent = String(value ?? '');
    return node.innerHTML;
}

function abortCotationSearch(type) {
    cotationSearchControllers.get(type)?.abort();
    cotationSearchControllers.delete(type);
}

async function loadCotationSuggestions(type, url) {
    abortCotationSearch(type);
    const controller = new AbortController();
    cotationSearchControllers.set(type, controller);
    try {
        const { data } = await window.medbridgeHttp.get(url, { signal: controller.signal });
        return cotationSearchControllers.get(type) === controller ? data : null;
    } finally {
        if (cotationSearchControllers.get(type) === controller) {
            cotationSearchControllers.delete(type);
        }
    }
}

function showCotationSearchLoading(type) {
    const suggestions = document.getElementById(`${type}-suggestions`);
    suggestions.innerHTML = '<div class="px-4 py-3 text-sm text-slate-500" aria-live="polite">Recherche en cours…</div>';
    suggestions.classList.remove('hidden');
}

function retryCotationSearch(type) {
    const input = document.getElementById(`${type}-code`);
    const query = input?.value?.trim();
    if (!query) return;
    ({ ccam: searchCCAM, ngap: searchNGAP, ucd: searchUCD, lpp: searchLPP }[type])?.(query);
}

function showCotationSearchError(type) {
    const suggestions = document.getElementById(`${type}-suggestions`);
    suggestions.innerHTML = `<div class="flex items-center justify-between gap-3 px-4 py-3 text-sm text-red-700" role="alert">Recherche indisponible.<button type="button" data-cotation-action="retry-search" data-acte-type="${type}" class="rounded border border-red-300 px-2 py-1 font-medium hover:bg-red-50">Réessayer</button></div>`;
    suggestions.classList.remove('hidden');
}

// Initialisation
document.addEventListener('DOMContentLoaded', function() {
    // Définir la date/heure par défaut à maintenant
    const now = new Date();
    document.getElementById('ccam-date').valueAsDate = now;
    document.getElementById('ccam-heure').value = now.toTimeString().slice(0, 5);
    document.getElementById('ngap-date').valueAsDate = now;
    document.getElementById('ngap-heure').value = now.toTimeString().slice(0, 5);
    document.getElementById('ucd-date').valueAsDate = now;
    document.getElementById('ucd-heure').value = now.toTimeString().slice(0, 5);
    document.getElementById('lpp-date').valueAsDate = now;
    document.getElementById('lpp-heure').value = now.toTimeString().slice(0, 5);

    // Raccourcis clavier
    document.addEventListener('keydown', function(e) {
        if (e.ctrlKey && e.key === 's') {
            e.preventDefault();
            document.getElementById(`${currentActeType || 'ccam'}-form`)?.requestSubmit();
        }
        if (e.ctrlKey && e.key === 'Enter') {
            e.preventDefault();
            saveContinue();
        }
        if (e.ctrlKey && e.key === 't') {
            e.preventDefault();
            showTemplates();
        }
        if (e.key === 'Escape') {
            closeAllModals();
        }
    });

    // Auto-complétion CCAM
    document.getElementById('ccam-code')?.addEventListener('input', function(e) {
        const value = e.target.value.toUpperCase();
        if (value.length >= 3) {
            searchCCAM(value);
        } else {
            abortCotationSearch('ccam');
            document.getElementById('ccam-suggestions').classList.add('hidden');
        }
    });

    // Auto-complétion NGAP
    document.getElementById('ngap-code')?.addEventListener('input', function(e) {
        const value = e.target.value.toUpperCase();
        if (value.length >= 1) {
            searchNGAP(value);
        } else {
            abortCotationSearch('ngap');
            document.getElementById('ngap-suggestions').classList.add('hidden');
        }
    });

    // Auto-complétion UCD
    document.getElementById('ucd-code')?.addEventListener('input', function(e) {
        const value = e.target.value;
        if (value.length >= 3) {
            searchUCD(value);
        } else {
            abortCotationSearch('ucd');
            document.getElementById('ucd-suggestions').classList.add('hidden');
        }
    });

    // Auto-complétion LPP
    document.getElementById('lpp-code')?.addEventListener('input', function(e) {
        const value = e.target.value;
        if (value.length >= 2) {
            searchLPP(value);
        } else {
            abortCotationSearch('lpp');
            document.getElementById('lpp-suggestions').classList.add('hidden');
        }
    });

    // Recalcul NGAP montant si on modifie coefficient / dénombrement
    ['ngap-coefficient', 'ngap-denombrement'].forEach(id => {
        document.getElementById(id)?.addEventListener('change', updateNgapMontantFromTarifBase);
    });
});

function selectActeType(type) {
    currentActeType = type;
    
    // Reset tous les boutons
    document.querySelectorAll('.acte-type-btn').forEach(btn => {
        btn.className = 'acte-type-btn p-4 border-2 border-slate-200 rounded-lg hover:shadow-md transition-all';
    });
    
    // Activer le bouton sélectionné
    const colors = {
        'ccam': 'border-emerald-500 bg-emerald-50 text-emerald-900 shadow-md',
        'ngap': 'border-blue-500 bg-blue-50 text-blue-900 shadow-md',
        'ucd': 'border-amber-500 bg-amber-50 text-amber-900 shadow-md',
        'lpp': 'border-purple-500 bg-purple-50 text-purple-900 shadow-md'
    };
    document.getElementById(`btn-type-${type}`).className += ` ${colors[type]}`;
    
    // Cacher tous les formulaires
    ['ccam', 'ngap', 'ucd', 'lpp'].forEach(t => {
        document.getElementById(`form-${t}`).classList.add('hidden');
    });
    
    // Afficher le formulaire sélectionné
    document.getElementById(`form-${type}`).classList.remove('hidden');
    
    // Focus sur le premier champ
    setTimeout(() => {
        document.querySelector(`#form-${type} input`)?.focus();
    }, 100);
}

function toggleModificateur(mod, btn) {
    const index = selectedModificateurs.indexOf(mod);
    
    if (index > -1) {
        selectedModificateurs.splice(index, 1);
        btn.classList.remove('border-emerald-500', 'bg-emerald-500', 'text-white');
        btn.classList.add('border-slate-200');
    } else {
        selectedModificateurs.push(mod);
        btn.classList.add('border-emerald-500', 'bg-emerald-500', 'text-white');
        btn.classList.remove('border-slate-200');
    }
    
    document.getElementById('ccam-modificateurs').value = selectedModificateurs.join(',');
}

async function searchCCAM(query) {
    showCotationSearchLoading('ccam');
    try {
        const suggestions = await loadCotationSuggestions('ccam',
            `/cotations/api/search/ccam?query=${encodeURIComponent(query)}&limit=10`,
        );
        if (suggestions === null) return;
        
        const suggestionsDiv = document.getElementById('ccam-suggestions');
        if (suggestions.length > 0) {
            cotationSuggestions.set('ccam', suggestions);
            suggestionsDiv.innerHTML = suggestions.map((s, index) => `
                <button type="button" data-cotation-action="select-suggestion" data-acte-type="ccam" data-suggestion-index="${index}"
                        class="w-full px-4 py-3 text-left hover:bg-emerald-50 transition-colors border-b border-slate-100 last:border-0">
                    <div class="flex justify-between items-start">
                        <div>
                            <div class="font-mono font-bold text-emerald-700">${escapeHtml(s.code)}</div>
                            <div class="text-sm text-slate-600">${escapeHtml(s.libelle)}</div>
                        </div>
                        <div class="text-right ml-4">
                            <div class="text-sm font-bold text-emerald-900">${s.tarif_base.toFixed(2)} €</div>
                        </div>
                    </div>
                </button>
            `).join('');
            suggestionsDiv.classList.remove('hidden');
        } else {
            suggestionsDiv.innerHTML = '<div class="px-4 py-3 text-sm text-slate-500">Aucun résultat</div>';
            suggestionsDiv.classList.remove('hidden');
        }
    } catch (error) {
        if (error.name === 'AbortError') return;
        console.error('Erreur recherche CCAM:', error);
        showCotationSearchError('ccam');
    }
}

async function searchNGAP(query) {
    showCotationSearchLoading('ngap');
    try {
        const suggestions = await loadCotationSuggestions('ngap',
            `/cotations/api/search/ngap?query=${encodeURIComponent(query)}&limit=10`,
        );
        if (suggestions === null) return;

        const suggestionsDiv = document.getElementById('ngap-suggestions');
        if (suggestions.length > 0) {
            cotationSuggestions.set('ngap', suggestions);
            suggestionsDiv.innerHTML = suggestions.map((s, index) => `
                <button type="button" data-cotation-action="select-suggestion" data-acte-type="ngap" data-suggestion-index="${index}"
                        class="w-full px-4 py-3 text-left hover:bg-blue-50 transition-colors border-b border-slate-100 last:border-0">
                    <div class="flex justify-between items-start">
                        <div>
                            <div class="font-mono font-bold text-blue-700">${escapeHtml(s.lettre_cle)}</div>
                            <div class="text-sm text-slate-600">${escapeHtml(s.libelle)}</div>
                        </div>
                        <div class="text-right ml-4">
                            <div class="text-sm font-bold text-blue-900">${s.tarif_base.toFixed(2)} €</div>
                        </div>
                    </div>
                </button>
            `).join('');
            suggestionsDiv.classList.remove('hidden');
        } else {
            suggestionsDiv.innerHTML = '<div class="px-4 py-3 text-sm text-slate-500">Aucun résultat</div>';
            suggestionsDiv.classList.remove('hidden');
        }
    } catch (error) {
        if (error.name === 'AbortError') return;
        console.error('Erreur recherche NGAP:', error);
        showCotationSearchError('ngap');
    }
}

function selectNGAP(lettre_cle, libelle, coefficient = 1.0, tarif_base = null) {
    document.getElementById('ngap-code').value = lettre_cle;
    document.getElementById('ngap-libelle-text').textContent = libelle;
    document.getElementById('ngap-libelle').classList.remove('hidden');
    document.getElementById('ngap-suggestions').classList.add('hidden');

    if (coefficient) {
        document.getElementById('ngap-coefficient').value = coefficient;
    }

    if (tarif_base) {
        document.getElementById('ngap-tarif-base').value = tarif_base.toString();
        updateNgapMontantFromTarifBase();
    }

    document.getElementById('ngap-coefficient').focus();
}

function updateNgapMontantFromTarifBase() {
    const tarifBaseStr = document.getElementById('ngap-tarif-base')?.value;
    if (!tarifBaseStr) return;
    const coef = parseFloat(document.getElementById('ngap-coefficient').value || '1');
    const den = parseInt(document.getElementById('ngap-denombrement').value || '1', 10);
    const tarifBase = parseFloat(tarifBaseStr);
    if (isNaN(tarifBase)) return;
    const montant = tarifBase * coef * den;
    document.getElementById('ngap-montant').value = montant.toFixed(2);
}

async function searchUCD(query) {
    showCotationSearchLoading('ucd');
    try {
        const suggestions = await loadCotationSuggestions('ucd',
            `/cotations/api/search/ucd?query=${encodeURIComponent(query)}&limit=10`,
        );
        if (suggestions === null) return;

        const suggestionsDiv = document.getElementById('ucd-suggestions');
        if (suggestions.length > 0) {
            cotationSuggestions.set('ucd', suggestions);
            suggestionsDiv.innerHTML = suggestions.map((s, index) => `
                <button type="button" data-cotation-action="select-suggestion" data-acte-type="ucd" data-suggestion-index="${index}"
                        class="w-full px-4 py-3 text-left hover:bg-amber-50 transition-colors border-b border-slate-100 last:border-0">
                    <div class="flex justify-between items-start">
                        <div>
                            <div class="font-mono font-bold text-amber-700">${escapeHtml(s.code_ucd)}</div>
                            <div class="text-sm text-slate-600">${s.denomination}</div>
                            <div class="text-xs text-slate-500">${s.dosage || ''} ${s.forme || ''}</div>
                        </div>
                        <div class="text-right ml-4">
                            <div class="text-sm font-bold text-amber-900">${s.prix.toFixed(2)} €</div>
                        </div>
                    </div>
                </button>
            `).join('');
            suggestionsDiv.classList.remove('hidden');
        } else {
            suggestionsDiv.innerHTML = '<div class="px-4 py-3 text-sm text-slate-500">Aucun résultat</div>';
            suggestionsDiv.classList.remove('hidden');
        }
    } catch (error) {
        if (error.name === 'AbortError') return;
        console.error('Erreur recherche UCD:', error);
        showCotationSearchError('ucd');
    }
}

function selectUCD(code_ucd, libelle, dosage, forme, prix) {
    document.getElementById('ucd-code').value = code_ucd;
    const libelleText = `${libelle}`;
    const extra = [dosage, forme].filter(Boolean).join(' • ');
    document.getElementById('ucd-libelle-text').textContent = libelleText;
    document.getElementById('ucd-libelle-extra').textContent = extra;
    document.getElementById('ucd-libelle').classList.remove('hidden');
    document.getElementById('ucd-suggestions').classList.add('hidden');

    if (prix) {
        document.getElementById('ucd-prix-unitaire').value = prix.toFixed(2);
    }

    document.getElementById('ucd-quantite').focus();
}

async function searchLPP(query) {
    showCotationSearchLoading('lpp');
    try {
        const suggestions = await loadCotationSuggestions('lpp',
            `/cotations/api/search/lpp?query=${encodeURIComponent(query)}&limit=10`,
        );
        if (suggestions === null) return;

        const suggestionsDiv = document.getElementById('lpp-suggestions');
        if (suggestions.length > 0) {
            cotationSuggestions.set('lpp', suggestions);
            suggestionsDiv.innerHTML = suggestions.map((s, index) => `
                <button type="button" data-cotation-action="select-suggestion" data-acte-type="lpp" data-suggestion-index="${index}"
                        class="w-full px-4 py-3 text-left hover:bg-purple-50 transition-colors border-b border-slate-100 last:border-0">
                    <div class="flex justify-between items-start">
                        <div>
                            <div class="font-mono font-bold text-purple-700">${escapeHtml(s.code_lpp)}</div>
                            <div class="text-sm text-slate-600">${s.denomination}</div>
                        </div>
                        <div class="text-right ml-4">
                            <div class="text-sm font-bold text-purple-900">${s.prix.toFixed(2)} €</div>
                        </div>
                    </div>
                </button>
            `).join('');
            suggestionsDiv.classList.remove('hidden');
        } else {
            suggestionsDiv.innerHTML = '<div class="px-4 py-3 text-sm text-slate-500">Aucun résultat</div>';
            suggestionsDiv.classList.remove('hidden');
        }
    } catch (error) {
        if (error.name === 'AbortError') return;
        console.error('Erreur recherche LPP:', error);
        showCotationSearchError('lpp');
    }
}

function selectLPP(code_lpp, libelle, prix) {
    document.getElementById('lpp-code').value = code_lpp;
    document.getElementById('lpp-libelle').value = libelle;
    if (prix) {
        document.getElementById('lpp-prix-unitaire').value = prix.toFixed(2);
    }
    document.getElementById('lpp-suggestions').classList.add('hidden');
    document.getElementById('lpp-quantite').focus();
}

function selectCCAM(code, libelle, tarif = null) {
    document.getElementById('ccam-code').value = code;
    document.getElementById('ccam-libelle-text').textContent = libelle;
    document.getElementById('ccam-libelle').classList.remove('hidden');
    document.getElementById('ccam-suggestions').classList.add('hidden');
    
    // Pré-remplir le montant si disponible
    if (tarif) {
        document.getElementById('ccam-montant').value = tarif.toFixed(2);
    }
    
    // Focus sur le champ suivant
    document.getElementById('ccam-activite').focus();
}

function selectSuggestion(type, index) {
    const suggestion = cotationSuggestions.get(type)?.[index];
    if (!suggestion) return;
    if (type === 'ccam') {
        selectCCAM(suggestion.code, suggestion.libelle, suggestion.tarif_base);
    } else if (type === 'ngap') {
        selectNGAP(suggestion.lettre_cle, suggestion.libelle, suggestion.coefficient, suggestion.tarif_base);
    } else if (type === 'ucd') {
        selectUCD(suggestion.code_ucd, suggestion.denomination, suggestion.dosage || '', suggestion.forme || '', suggestion.prix);
    } else if (type === 'lpp') {
        selectLPP(suggestion.code_lpp, suggestion.denomination, suggestion.prix);
    }
}

function resetForm(type = currentActeType) {
    if (type) {
        document.getElementById(`${type}-form`).reset();
        selectedModificateurs = [];
        document.querySelectorAll('.modificateur-btn').forEach(btn => {
            btn.classList.remove('border-emerald-500', 'bg-emerald-500', 'text-white');
            btn.classList.add('border-slate-200');
        });
        document.getElementById('ccam-libelle').classList.add('hidden');
    }
}

function saveContinue() {
    const type = currentActeType || 'ccam';
    const form = document.getElementById(`${type}-form`);
    if (!form) {
        showNotification('Sélectionnez un type d’acte avant l’enregistrement.', 'error');
        return;
    }
    saveAndContinue = true;
    form.requestSubmit();
}

function finishSaved(type, message) {
    showNotification(message, 'success');
    resetForm(type);
    if (saveAndContinue) {
        saveAndContinue = false;
        document.getElementById(`${type}-code`)?.focus();
        return;
    }
    window.location.reload();
}

function showTemplates() {
    document.getElementById('modal-templates').classList.remove('hidden');
}

function showHistory() {
    const history = document.getElementById('cotations-history');
    history?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    history?.focus({ preventScroll: true });
}

async function useTemplate(templateId) {
    try {
        const { data: templates } = await window.medbridgeHttp.get('/cotations/api/templates');
        
        // Trouver le template dans tous les types
        let template = null;
        let templateType = null;
        
        for (const [type, items] of Object.entries(templates)) {
            const found = items.find(t => t.id === templateId);
            if (found) {
                template = found;
                templateType = type;
                break;
            }
        }
        
        if (template) {
            // Sélectionner le type d'acte
            selectActeType(templateType);
            
            // Remplir le formulaire selon le type
            if (templateType === 'ccam') {
                document.getElementById('ccam-code').value = template.code_acte;
                document.getElementById('ccam-activite').value = template.code_activite;
                document.getElementById('ccam-phase').value = template.code_phase;
                document.getElementById('ccam-quantite').value = template.quantite;
                
                // Déclencher la recherche pour afficher le libellé
                await searchCCAM(template.code_acte);
                selectCCAM(template.code_acte, template.nom);
            }
            if (templateType === 'ngap') {
                document.getElementById('ngap-code').value = template.lettre_cle;
                document.getElementById('ngap-coefficient').value = template.coefficient || 1;
                document.getElementById('ngap-denombrement').value = template.denombrement || 1;
                document.getElementById('ngap-libelle-text').textContent = template.nom;
                document.getElementById('ngap-libelle').classList.remove('hidden');
            }
            if (templateType === 'ucd') {
                document.getElementById('ucd-code').value = template.code_ucd;
                document.getElementById('ucd-quantite').value = template.quantite || 1;
                document.getElementById('ucd-libelle-text').textContent = template.nom;
                document.getElementById('ucd-libelle-extra').textContent = '';
                document.getElementById('ucd-libelle').classList.remove('hidden');
            }
            if (templateType === 'lpp') {
                document.getElementById('lpp-code').value = template.code_lpp;
                document.getElementById('lpp-quantite').value = template.quantite || 1;
                document.getElementById('lpp-libelle').value = template.nom;
            }
            
            closeModal('modal-templates');
            showNotification(`Template "${template.nom}" chargé`, 'success');
        }
    } catch (error) {
        console.error('Erreur chargement template:', error);
        showNotification('Erreur lors du chargement du template', 'error');
    }
}

function closeModal(modalId) {
    document.getElementById(modalId).classList.add('hidden');
}

function closeAllModals() {
    document.querySelectorAll('[id^="modal-"]').forEach(modal => {
        modal.classList.add('hidden');
    });
}

function showNotification(message, type) {
    const normalizedType = ['success', 'error', 'warning', 'info'].includes(type)
        ? type
        : 'info';
    window.toastSystem?.show(message, normalizedType);
}

document.addEventListener('click', function(event) {
    const button = event.target.closest('[data-cotation-action]');
    if (!(button instanceof HTMLElement)) return;

    const action = button.dataset.cotationAction;
    if (action === 'show-templates') showTemplates();
    else if (action === 'show-history') showHistory();
    else if (action === 'select-type') selectActeType(button.dataset.acteType);
    else if (action === 'reset-form') resetForm();
    else if (action === 'toggle-modifier') toggleModificateur(button.dataset.modifier, button);
    else if (action === 'save-continue') saveContinue();
    else if (action === 'close-templates') closeModal('modal-templates');
    else if (action === 'use-template') void useTemplate(button.dataset.templateId);
    else if (action === 'retry-search') retryCotationSearch(button.dataset.acteType);
    else if (action === 'select-suggestion') {
        selectSuggestion(button.dataset.acteType, Number(button.dataset.suggestionIndex));
    }
});

// Soumission formulaire CCAM
document.getElementById('ccam-form')?.addEventListener('submit', async function(e) {
    e.preventDefault();
    
    const formData = {
        code_acte: document.getElementById('ccam-code').value,
        code_activite: document.getElementById('ccam-activite').value,
        code_phase: document.getElementById('ccam-phase').value,
        execute_date: `${document.getElementById('ccam-date').value}T${document.getElementById('ccam-heure').value}`,
        modificateurs: document.getElementById('ccam-modificateurs').value,
        quantite: document.getElementById('ccam-quantite').value || 1,
        montant_total: document.getElementById('ccam-montant').value || null,
        commentaire: document.getElementById('ccam-commentaire').value || null,
        dossier_id: dossierId
    };
    
    try {
        await window.medbridgeHttp.post('/cotations/api/ccam', formData);
        finishSaved('ccam', 'Acte CCAM enregistré avec succès !');
    } catch (error) {
        showNotification('Erreur: ' + error.message, 'error');
    }
});

// Soumission formulaire NGAP
document.getElementById('ngap-form')?.addEventListener('submit', async function(e) {
    e.preventDefault();

    const formData = {
        lettre_cle: document.getElementById('ngap-code').value,
        coefficient: parseFloat(document.getElementById('ngap-coefficient').value || '1'),
        denombrement: parseInt(document.getElementById('ngap-denombrement').value || '1', 10),
        execute_date: `${document.getElementById('ngap-date').value}T${document.getElementById('ngap-heure').value}`,
        montant_total: document.getElementById('ngap-montant').value || null,
        commentaire: document.getElementById('ngap-commentaire').value || null,
        dossier_id: dossierId
    };

    try {
        await window.medbridgeHttp.post('/cotations/api/ngap', formData);
        finishSaved('ngap', 'Acte NGAP enregistré avec succès !');
    } catch (error) {
        showNotification('Erreur: ' + error.message, 'error');
    }
});

// Soumission formulaire UCD
document.getElementById('ucd-form')?.addEventListener('submit', async function(e) {
    e.preventDefault();

    const formData = {
        code_ucd: document.getElementById('ucd-code').value,
        denomination_libelle: document.getElementById('ucd-libelle-text').textContent || document.getElementById('ucd-code').value,
        denomination_dosage: document.getElementById('ucd-libelle-extra').textContent || null,
        execute_date: `${document.getElementById('ucd-date').value}T${document.getElementById('ucd-heure').value}`,
        quantite: parseFloat(document.getElementById('ucd-quantite').value || '1'),
        montant_unitaire_facture_ttc: document.getElementById('ucd-prix-unitaire').value ? parseFloat(document.getElementById('ucd-prix-unitaire').value) : null,
        commentaire: document.getElementById('ucd-commentaire').value || null,
        dossier_id: dossierId
    };

    try {
        await window.medbridgeHttp.post('/cotations/api/ucd', formData);
        finishSaved('ucd', 'Acte UCD enregistré avec succès !');
    } catch (error) {
        showNotification('Erreur: ' + error.message, 'error');
    }
});

// Soumission formulaire LPP
document.getElementById('lpp-form')?.addEventListener('submit', async function(e) {
    e.preventDefault();

    const formData = {
        code_lpp: document.getElementById('lpp-code').value || null,
        denomination_libelle: document.getElementById('lpp-libelle').value,
        execute_date: `${document.getElementById('lpp-date').value}T${document.getElementById('lpp-heure').value}`,
        quantite: parseInt(document.getElementById('lpp-quantite').value || '1', 10),
        montant_unitaire_facture_ttc: parseFloat(document.getElementById('lpp-prix-unitaire').value),
        commentaire: document.getElementById('lpp-commentaire').value || null,
        dossier_id: dossierId
    };

    try {
        await window.medbridgeHttp.post('/cotations/api/lpp', formData);
        finishSaved('lpp', 'Acte LPP enregistré avec succès !');
    } catch (error) {
        showNotification('Erreur: ' + error.message, 'error');
    }
});
