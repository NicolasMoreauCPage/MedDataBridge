// forms.js - Logique des formulaires MedData Bridge

console.debug('forms.js loaded');

/**
 * Gère les champs dépendants (cascading dropdowns)
 * Charge dynamiquement les options quand un champ parent change
 */
class DependentFieldsManager {
    constructor(formElement) {
        this.form = formElement;
        this.dependencies = this.detectDependencies();
        this.setupListeners();
    }

    /**
     * Détecte les dépendances entre champs en analysant les data-depends-on
     * Utilise des attributs data-* pour la configuration flexible
     */
    detectDependencies() {
        const deps = new Map();
        
        // Parcourir tous les selects du formulaire
        const allSelects = this.form.querySelectorAll('select');
        
        allSelects.forEach(select => {
            const fieldName = select.name;
            if (!fieldName) return;
            
            // Chercher les champs qui dépendent de celui-ci
            const dependentSelects = this.form.querySelectorAll(`select[data-parent-field="${fieldName}"]`);
            
            if (dependentSelects.length > 0) {
                const dependentNames = Array.from(dependentSelects).map(s => s.name).filter(n => n);

                if (dependentNames.length > 0) {
                    deps.set(fieldName, {
                        dependents: dependentNames
                    });
                }
            }
        });
        
        // Fallback: détection automatique pour mouvements (UF -> UH -> Chambre -> Lit)
        // Si aucune dépendance n'a été détectée via data-parent-field
        if (deps.size === 0) {
            const ufField = this.form.querySelector('[name="uf_id"]');
            const uhField = this.form.querySelector('[name="uh_id"]');
            const chambreField = this.form.querySelector('[name="chambre_id"]');
            const litField = this.form.querySelector('[name="lit_id"]');
            
            if (ufField && uhField) {
                deps.set('uf_id', { dependents: ['uh_id'] });
            }
            
            if (uhField && chambreField) {
                deps.set('uh_id', { dependents: ['chambre_id'] });
            }
            
            if (chambreField && litField) {
                deps.set('chambre_id', { dependents: ['lit_id'] });
            }
        }
        
        return deps;
    }

    /**
     * Configure les listeners sur les champs parents
     */
    setupListeners() {
        this.dependencies.forEach((config, fieldName) => {
            const field = this.form.querySelector(`[name="${fieldName}"]`);
            if (field) {
                field.addEventListener('change', () => this.handleParentChange(fieldName, field.value));
            }
        });
    }

    /**
     * Gère le changement d'un champ parent
     */
    async handleParentChange(parentName, parentValue) {
        const config = this.dependencies.get(parentName);
        if (!config) return;

        console.log(`Parent ${parentName} changed to:`, parentValue);

        // Pour chaque champ dépendant
        for (const dependentName of config.dependents) {
            const dependentField = this.form.querySelector(`[name="${dependentName}"]`);
            if (!dependentField) continue;

            // Réinitialiser le champ
            this.clearField(dependentField);

            if (!parentValue || parentValue === '') {
                this.showEmptyMessage(dependentField);
                continue;
            }

            // Charger les nouvelles options
            try {
                await this.loadOptions(dependentField, parentName, parentValue);
            } catch (error) {
                console.error(`Failed to load options for ${dependentName}:`, error);
                this.showErrorMessage(dependentField, 'Erreur lors du chargement des options');
            }
        }
    }

    /**
     * Charge les options pour un champ dépendant
     */
    async loadOptions(field, parentName, parentValue) {
        const fieldName = field.name;
        let endpoint = '';

        // Construire l'endpoint selon le champ
        // Note: Supporte à la fois uf_id et uf_soins_id comme parent de uh_id
        if (fieldName === 'uh_id') {
            // Charger les UH pour l'UF sélectionnée
            // Le paramètre API est toujours 'uf_id' même si le parent s'appelle 'uf_soins_id'
            endpoint = `/api/mouvements/uh-options?uf_id=${encodeURIComponent(parentValue)}`;
        } else if (fieldName === 'chambre_id') {
            // Charger les chambres pour l'UH sélectionnée
            endpoint = `/api/mouvements/chambre-options?uh_id=${encodeURIComponent(parentValue)}`;
        } else if (fieldName === 'lit_id') {
            // Charger les lits pour la chambre sélectionnée
            endpoint = `/api/mouvements/lit-options?chambre_id=${encodeURIComponent(parentValue)}`;
        }

        if (!endpoint) return;

        // Afficher un loader
        this.showLoading(field);

        try {
            const { data: options } = await window.medbridgeHttp.get(endpoint);
            
            // Mettre à jour les options
            this.updateFieldOptions(field, options);
            
            // Cacher le message d'avertissement si présent
            this.hideEmptyMessage(field);
            
        } catch (error) {
            console.error(`Error loading options:`, error);
            this.showErrorMessage(field, 'Erreur de chargement');
        }
    }

    /**
     * Met à jour les options d'un champ select
     */
    updateFieldOptions(field, options) {
        // Garder l'option vide
        field.innerHTML = '<option value="">-- Sélectionner --</option>';
        
        options.forEach(opt => {
            const option = document.createElement('option');
            option.value = opt.value;
            option.textContent = opt.label;
            field.appendChild(option);
        });

        field.disabled = options.length === 0;
        this.clearFieldError(field);
    }

    /**
     * Réinitialise un champ
     */
    clearField(field) {
        field.innerHTML = '<option value="">-- Sélectionner --</option>';
        field.value = '';
        field.disabled = false;
        this.clearFieldError(field);
    }

    /**
     * Affiche un loader dans le champ
     */
    showLoading(field) {
        field.innerHTML = '<option value="">⏳ Chargement...</option>';
        field.disabled = true;
    }

    /**
     * Affiche le message d'avertissement sous le champ
     */
    showEmptyMessage(field) {
        const container = field.closest('.space-y-2');
        if (!container) return;

        const existingMsg = container.querySelector('.empty-state-message');
        if (existingMsg) {
            existingMsg.style.display = 'block';
        }
    }

    /**
     * Cache le message d'avertissement
     */
    hideEmptyMessage(field) {
        const container = field.closest('.space-y-2');
        if (!container) return;

        const existingMsg = container.querySelector('.empty-state-message');
        if (existingMsg) {
            existingMsg.style.display = 'none';
        }
    }

    /**
     * Affiche un message d'erreur
     */
    showErrorMessage(field, message) {
        console.error(message);
        field.innerHTML = `<option value="">❌ ${message}</option>`;
        field.disabled = true;
        field.setAttribute('aria-invalid', 'true');
        const errorId = `${field.id || field.name || 'dependent-field'}-load-error`;
        let error = document.getElementById(errorId);
        if (!error) {
            error = document.createElement('p');
            error.id = errorId;
            error.className = 'form-error mt-1 text-sm text-red-600';
            error.setAttribute('role', 'alert');
            field.insertAdjacentElement('afterend', error);
        }
        error.textContent = message;
        const descriptions = new Set((field.getAttribute('aria-describedby') || '').split(/\s+/).filter(Boolean));
        descriptions.add(errorId);
        field.setAttribute('aria-describedby', Array.from(descriptions).join(' '));
    }

    clearFieldError(field) {
        const errorId = `${field.id || field.name || 'dependent-field'}-load-error`;
        document.getElementById(errorId)?.remove();
        const descriptions = (field.getAttribute('aria-describedby') || '')
            .split(/\s+/)
            .filter((description) => description && description !== errorId);
        if (descriptions.length) field.setAttribute('aria-describedby', descriptions.join(' '));
        else field.removeAttribute('aria-describedby');
        field.removeAttribute('aria-invalid');
    }
}

class FormManager {
    constructor(formElement, options = {}) {
        this.form = formElement;
        this.options = {
            showToasts: true,
            validateOnType: true,
            scrollToError: true,
            autoFocus: true,
            ...options
        };

        this.setupResponsiveLayout();
        
        // Ensure family field gets focus
        this.setupInitialFocus();
        
        // Initialiser la gestion des champs dépendants
        this.dependentFieldsManager = new DependentFieldsManager(formElement);
        
        this.validators = {
            required: (value) => value && value.trim() !== '',
            email: (value) => !value || /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value),
            // Plus permissif pour les téléphones - accepte espaces, tirets, points, parenthèses
            phone: (value) => !value || /^[\d\s\-\.\+\(\)]+$/.test(value.trim()),
            numeric: (value) => !value || !isNaN(value),
            date: (value) => !value || !isNaN(Date.parse(value)),
            ...options.validators
        };

        this.setupEventListeners();
    }

    setupEventListeners() {
        if (this.options.validateOnType) {
            this.form.querySelectorAll('input, select, textarea').forEach(field => {
                field.addEventListener('input', () => {
                    this.validateField(field);
                    this.updateErrorSummary();
                });
                field.addEventListener('blur', () => {
                    this.validateField(field);
                    this.updateErrorSummary();
                });
            });
        }

        // Ensure family field gets focus
        const familyField = this.form.querySelector('input[name="family"]');
        if (familyField) {
            setTimeout(() => familyField.focus(), 0);
        }

        if (this.form.hasAttribute('data-guard-unsaved')) {
            this.setupUnsavedChangesGuard();
        }

        this.form.addEventListener('submit', (e) => this.handleSubmit(e));
    }

    setupUnsavedChangesGuard() {
        this.isDirty = false;
        this.dirtyStatus = this.form.querySelector('[data-form-dirty-status]');
        if (!this.dirtyStatus) {
            this.dirtyStatus = document.createElement('p');
            this.dirtyStatus.dataset.formDirtyStatus = 'true';
            this.dirtyStatus.className = 'form-dirty-status text-sm font-medium text-amber-700 dark:text-amber-300';
            this.dirtyStatus.setAttribute('role', 'status');
            this.dirtyStatus.setAttribute('aria-live', 'polite');
            this.dirtyStatus.hidden = true;
            this.form.prepend(this.dirtyStatus);
        }
        const markDirty = (event) => {
            const field = event.target;
            if (!(field instanceof HTMLInputElement || field instanceof HTMLSelectElement || field instanceof HTMLTextAreaElement)) return;
            if (field.disabled || field.type === 'hidden') return;
            this.setDirty(true);
        };
        this.form.addEventListener('input', markDirty);
        this.form.addEventListener('change', markDirty);
        this.form.addEventListener('reset', () => window.requestAnimationFrame(() => this.setDirty(false)));
        this.form.querySelectorAll('[data-form-cancel]').forEach((link) => {
            link.addEventListener('click', (event) => {
                if (!this.isDirty || window.confirm('Quitter sans enregistrer les modifications ?')) return;
                event.preventDefault();
            });
        });
        window.addEventListener('beforeunload', (event) => {
            if (!this.isDirty) return;
            event.preventDefault();
            event.returnValue = '';
        });
    }

    setDirty(isDirty) {
        if (!this.dirtyStatus) return;
        this.isDirty = isDirty;
        this.dirtyStatus.hidden = !isDirty;
        this.dirtyStatus.textContent = isDirty ? 'Modifications non enregistrées.' : 'Toutes les modifications sont enregistrées.';
    }

    markClean() {
        if (this.isDirty) this.setDirty(false);
    }

    ensureFieldId(field) {
        if (field.id) return field.id;
        const formIndex = Math.max(0, Array.from(document.forms).indexOf(this.form));
        const name = (field.name || 'champ').replace(/[^a-zA-Z0-9_-]/g, '-');
        field.id = `form-${formIndex}-${name}`;
        return field.id;
    }

    ensureErrorSummary() {
        let summary = this.form.querySelector('[data-form-error-summary]');
        if (summary) return summary;
        summary = document.createElement('section');
        summary.dataset.formErrorSummary = 'true';
        summary.className = 'form-error-summary rounded-xl border border-red-200 bg-red-50 p-4 text-red-900 dark:border-red-900 dark:bg-red-950/30 dark:text-red-100';
        summary.setAttribute('role', 'alert');
        summary.setAttribute('tabindex', '-1');
        summary.hidden = true;
        this.form.prepend(summary);
        return summary;
    }

    updateErrorSummary() {
        const invalidFields = Array.from(this.form.querySelectorAll('[aria-invalid="true"]'));
        const summary = this.ensureErrorSummary();
        if (!invalidFields.length) {
            summary.hidden = true;
            summary.replaceChildren();
            return;
        }
        const title = document.createElement('h2');
        title.className = 'font-semibold';
        title.textContent = 'Corrigez les champs signalés avant de continuer.';
        const list = document.createElement('ul');
        list.className = 'mt-2 list-disc space-y-1 pl-5 text-sm';
        invalidFields.forEach((field) => {
            const item = document.createElement('li');
            const link = document.createElement('a');
            link.href = `#${this.ensureFieldId(field)}`;
            link.className = 'underline underline-offset-2 hover:no-underline';
            link.textContent = field.labels?.[0]?.textContent?.trim() || field.name || 'Champ invalide';
            link.addEventListener('click', (event) => {
                event.preventDefault();
                field.focus();
                field.scrollIntoView({ behavior: 'smooth', block: 'center' });
            });
            item.append(link);
            list.append(item);
        });
        summary.replaceChildren(title, list);
        summary.hidden = false;
    }

    setupInitialFocus() {
        if (this.options.autoFocus) {
            const doFocus = () => {
                const familyField = this.form.querySelector('input[name="family"]');
                if (familyField) {
                    // Use requestAnimationFrame to ensure focus happens after layout
                    requestAnimationFrame(() => {
                        familyField.focus();
                        console.debug('FormManager: focused family field');
                    });
                }
            };
            
            // If DOM is already loaded, focus immediately
            if (document.readyState === 'complete' || document.readyState === 'interactive') {
                doFocus();
            } else {
                // Otherwise wait for DOMContentLoaded
                document.addEventListener('DOMContentLoaded', doFocus);
            }
        }
    }

    setupResponsiveLayout() {
        const formGrid = this.form.querySelector('.form-grid');
        if (!formGrid) return;

        // Initial layout
        this.updateGridLayout(formGrid);

        // Update on window resize
        const handleResize = () => this.updateGridLayout(formGrid);
        window.addEventListener('resize', handleResize);
    }

    updateGridLayout(grid) {
        // Set explicit grid template columns for test consistency
        const mediaQuery = window.matchMedia('(min-width: 768px)');
        const updateColumns = (e) => {
            grid.style.gridTemplateColumns = e.matches ? 
                'repeat(2, minmax(0, 1fr))' : 
                'repeat(1, minmax(0, 1fr))';
        };
        
        // Initial setup
        updateColumns(mediaQuery);
        
        // Listen for changes
        mediaQuery.addListener(updateColumns);
    }

    // Write a small DOM-visible debug marker so tests can assert on it even
    // when console messages are not captured. Keeps a short JSON with
    // events like submit-start and submit-end along with timestamps.
    writeTestDebug(eventName, details = {}) {
        try {
            let el = document.getElementById('__test_debug');
            if (!el) {
                el = document.createElement('div');
                el.id = '__test_debug';
                el.style.display = 'none';
                document.body.appendChild(el);
            }
            const previous = el.dataset.events ? JSON.parse(el.dataset.events) : [];
            previous.push({ event: eventName, at: new Date().toISOString(), details });
            // keep only last 10
            const sliced = previous.slice(-10);
            el.dataset.events = JSON.stringify(sliced);
            // also set textContent for easy page.evaluate readout
            el.textContent = JSON.stringify(sliced);
        } catch (e) {
            // non-fatal
            console.debug('writeTestDebug failed', e);
        }
    }

    validateField(field) {
        this.clearFieldError(field);
        const validations = this.getFieldValidations(field);
        
        // Treat "None" string as empty (Jinja2 sometimes renders None as "None")
        const value = field.value === 'None' ? '' : field.value;
        const isEmpty = !value || value.trim() === '';
        
        // If the field is empty and required, show required error
        if (isEmpty && validations.required) {
            this.showFieldError(field, validations.required);
            return false;
        }
        
        // If field has value, check type-specific validations
        if (!isEmpty) {
            for (const [validationType, message] of Object.entries(validations)) {
                if (validationType === 'required') continue;
                const validator = this.validators[validationType];
                if (validator && !validator(value)) {
                    this.showFieldError(field, message);
                    return false;
                }
            }
        }
        
        return true;
    }

    getFieldValidations(field) {
        const validations = {};
        const type = field.getAttribute('type');
        
        // Add type-specific validations first
        const fieldLabel = field.labels?.[0]?.textContent?.trim() || field.name;
        
        if (type === 'email') {
            validations.email = `L'adresse email '${fieldLabel}' est invalide`;
        } else if (type === 'tel') {
            validations.phone = `Le numéro de téléphone '${fieldLabel}' est invalide`;
        } else if (type === 'number') {
            validations.numeric = `La valeur numérique '${fieldLabel}' est invalide`;
        } else if (type === 'date') {
            validations.date = `La date '${fieldLabel}' est invalide`;
        }
        
        // Add required validation last so it takes precedence if field is empty
        if (field.hasAttribute('required')) {
            validations.required = 'Ce champ est obligatoire';
        }

        // Custom data-validate attributes
        const customValidation = field.dataset.validate;
        if (customValidation) {
            try {
                const rules = JSON.parse(customValidation);
                Object.assign(validations, rules);
            } catch (e) {
                console.error('Invalid data-validate format:', e);
            }
        }

        return validations;
    }

    showFieldError(field, message) {
        // Use the same container structure and classes as the server-side
        // templates to keep client and tests consistent. The template uses
        // a wrapper with classes like 'space-y-2' and renders errors with
        // the class 'error-message'. We add Tailwind-like classes to the
        // field to visually mark it as invalid.
        let container = null;
        try {
            container = field.closest ? field.closest('.space-y-2') : null;
        } catch (e) {
            container = null;
        }
        if (!container) container = field.parentElement || document.body;

        // Look for existing error for THIS specific field using data-for
        const selector = `.error-message[data-for="${field.name}"]`;
        const existing = container.querySelector ? container.querySelector(selector) : null;
        const errorId = existing?.id || field.dataset.errorId || (
            (field.id || `field-${field.name || "input"}`).replace(/[^a-zA-Z0-9_-]/g, "-") + "-error"
        );
        if (!existing) {
            const error = document.createElement('p');
            error.id = errorId;
            error.className = 'error-message form-error text-sm text-red-600 flex items-center gap-1 mt-1';
            error.setAttribute('data-for', field.name || '');
            error.setAttribute('role', 'alert');
            error.textContent = message;
            container.appendChild(error);
        } else {
            // Update existing error message
            const textNode = existing.lastChild;
            if (textNode) textNode.textContent = message;
        }
        if (field.classList) field.classList.add('border-red-500', 'ring-red-500');
        field.setAttribute('aria-invalid', 'true');
        field.dataset.errorId = errorId;
        const descriptions = new Set((field.getAttribute('aria-describedby') || '').split(/\s+/).filter(Boolean));
        descriptions.add(errorId);
        field.setAttribute('aria-describedby', Array.from(descriptions).join(' '));
    }

    clearFieldError(field) {
        let container = null;
        try {
            container = field.closest ? field.closest('.space-y-2') : null;
        } catch (e) {
            container = null;
        }
        if (!container) container = field.parentElement || document.body;
        // Remove error for THIS specific field using data-for
        const selector = `.error-message[data-for="${field.name}"]`;
        const error = container && container.querySelector ? container.querySelector(selector) : null;
        if (error) error.remove();
        if (field.classList) field.classList.remove('border-red-500', 'ring-red-500');
        field.removeAttribute('aria-invalid');
        const errorId = field.dataset.errorId;
        if (errorId) {
            const descriptions = (field.getAttribute('aria-describedby') || '')
                .split(/\s+/)
                .filter((value) => value && value !== errorId);
            if (descriptions.length) field.setAttribute('aria-describedby', descriptions.join(' '));
            else field.removeAttribute('aria-describedby');
            delete field.dataset.errorId;
        }
    }

    async handleSubmit(event) {
        // Skip forms with data-no-ajax - let them submit normally
        if (this.form.hasAttribute('data-no-ajax')) {
            console.debug('Form has data-no-ajax, allowing normal submission');
            return; // Don't prevent default, let browser submit normally
        }

        // GET forms (typically filters/search) can't carry a fetch() body — the Fetch
        // API throws on GET/HEAD requests with a body. Let the browser submit these
        // normally instead of intercepting them for the AJAX/toast/JSON flow below.
        if (this.form.method && this.form.method.toLowerCase() === 'get') {
            console.debug('Form uses GET, allowing normal submission');
            return; // Don't prevent default, let browser submit normally
        }

        event.preventDefault();
        console.debug('FormManager.handleSubmit called for', this.form.action, this.form.method);
        
        const isDownload = (this.form.dataset && this.form.dataset.download === '1');
        // Validate and collect errors unless this is a download form
        let hasError = false;
        const allFields = Array.from(this.form.querySelectorAll('input, select, textarea'));
        
        if (!isDownload) {
            // Clear all previous errors
            allFields.forEach(field => this.clearFieldError(field));
            
            // Validate each field and collect errors
            allFields.forEach(field => {
                // Check if field is required and empty
                if (field.hasAttribute('required') && (!field.value || field.value.trim() === '')) {
                    this.showFieldError(field, 'Ce champ est obligatoire');
                    hasError = true;
                }
                // Then check other validations if the field has a value
                else if (field.value && field.value.trim() !== '') {
                    if (!this.validateField(field)) {
                        hasError = true;
                    }
                }
            });
        }

        if (hasError) {
            // Ensure all empty required fields have their error node created
            allFields.forEach(field => {
                if (field.hasAttribute('required') && (!field.value || field.value.trim() === '')) {
                    // Check if an error element for this field already exists; if not, create it
                    let container = null;
                    try { container = field.closest ? field.closest('.space-y-2') : null; } catch (e) { container = null; }
                    if (!container) container = field.parentElement || document.body;
                    const selector = `.error-message[data-for="${field.name}"]`;
                    const existing = container.querySelector ? container.querySelector(selector) : null;
                    if (!existing) {
                        this.showFieldError(field, 'Ce champ est obligatoire');
                    }
                }
            });

            if (this.options.scrollToError) {
                this.updateErrorSummary();
                const firstError = this.form.querySelector('.form-error');
                if (firstError) {
                    firstError.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    this.form.querySelector('[aria-invalid="true"]')?.focus();
                }
            }
            return;
        }

        // Désactiver le formulaire pendant la soumission
        const submitBtn = this.form.querySelector('button[type="submit"]');
        console.debug('Attempting to disable submit button', submitBtn);
        const originalBtnContent = submitBtn.innerHTML;
        // set both property and attribute for robustness
        try { submitBtn.disabled = true; } catch(e) {}
        try { submitBtn.setAttribute('disabled', ''); } catch(e) {}
        submitBtn.innerHTML = this.getLoadingButtonContent();
        console.debug('Submit button disabled attribute present?', submitBtn.hasAttribute && submitBtn.hasAttribute('disabled'));

        try {
            const formData = new FormData(this.form);
            console.debug('Submitting form via shared HTTP client to', this.form.action);
            // Mark submit-start in a DOM-readable debug element for tests
            this.writeTestDebug('submit-start', { action: this.form.action, download: isDownload });

            if (isDownload) {
                const { response, data: blob } = await window.medbridgeHttp.request(this.form.action, {
                    method: this.form.method,
                    body: formData,
                    responseType: 'blob',
                });
                const disposition = response.headers.get('content-disposition') || '';
                let filename = 'download';
                const match = /filename\*=UTF-8''([^;]+)|filename="?([^";]+)"?/i.exec(disposition);
                if (match) {
                    filename = decodeURIComponent(match[1] || match[2]);
                }
                const contentType = response.headers.get('content-type') || 'application/octet-stream';
                const url = window.URL.createObjectURL(new Blob([blob], { type: contentType }));
                const a = document.createElement('a');
                a.href = url;
                a.setAttribute('download', filename);
                document.body.appendChild(a);
                a.click();
                a.remove();
                window.URL.revokeObjectURL(url);
                this.showToast('success', 'Téléchargement démarré');
                return;
            } else {
                const { response, data } = await window.medbridgeHttp.request(this.form.action, {
                    method: this.form.method,
                    body: formData,
                    headers: {
                        'Accept': 'application/json'
                    }
                });
                
                console.debug('Fetch response', response.status, data);

                // Use exact same success message as the one expected by the test
                this.showToast('success', 'Enregistrement réussi');
                this.markClean();

                // Delay redirect to ensure toast is visible
                if (data && typeof data === 'object' && data.redirect) {
                    setTimeout(() => {
                        window.location.href = data.redirect;
                    }, 1000); // Longer delay for test stability
                }
            }
        } catch (error) {
            console.error('Erreur de soumission:', error);
            const details = error?.data;
            if (!isDownload && details && typeof details === 'object' && details.errors) {
                this.handleServerErrors(details.errors);
            }
            this.showToast(
                'error',
                details?.message || details?.detail || (isDownload
                    ? 'Échec du téléchargement'
                    : 'Erreur technique lors de l\'enregistrement'),
            );
        } finally {
            try { submitBtn.disabled = false; } catch(e) {}
            try { submitBtn.removeAttribute('disabled'); } catch(e) {}
            submitBtn.innerHTML = originalBtnContent;
            // Mark submit-end for tests
            this.writeTestDebug('submit-end', { action: this.form.action, download: isDownload });
            console.debug('Submit button re-enabled, disabled attribute present?', submitBtn.hasAttribute && submitBtn.hasAttribute('disabled'));
        }
    }

    handleServerErrors(errors) {
        Object.entries(errors).forEach(([fieldName, message]) => {
            const field = this.form.querySelector(`[name="${fieldName}"]`);
            if (field) {
                this.showFieldError(field, message);
            }
        });
        this.updateErrorSummary();
    }

    showToast(type, message) {
        if (!this.options.showToasts || !window.toastSystem) return;
        window.toastSystem.show(message, type);
    }

    getLoadingButtonContent() {
        return `
            <svg class="animate-spin h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            <span>Enregistrement...</span>
        `;
    }
}

// Transitions d'état spécifiques à l'application
const StateTransitionManager = {
    validTransitions: {
        "Pas de venue courante": ["A05", "A38"],
        "Pré-admis consult.ext.": ["A04", "A11"],
        "Pré-admis hospit.": ["A01", "A11"],
        "Hospitalisé": ["A03", "A13", "A21", "A52", "A53"],
        "Absence temporaire": ["A22", "A52"],
        "Consultant externe": ["A06", "A07"]
    },

    isValidTransition(currentState, newState) {
        return this.validTransitions[currentState]?.includes(newState);
    },

    setupTransitionValidation(form) {
        const currentStateField = form.querySelector('[name="current_state"]');
        const eventCodeField = form.querySelector('[name="event_code"]');
        
        if (currentStateField && eventCodeField) {
            // Clear any previous error when changing current state
            currentStateField.addEventListener('change', () => {
                if (form.manager) {
                    form.manager.clearFieldError(eventCodeField);
                }
            });

            // Validate transition when changing event code
            eventCodeField.addEventListener('change', () => {
                const isValid = this.isValidTransition(
                    currentStateField.value,
                    eventCodeField.value
                );
                
                if (!isValid) {
                    form.manager.showFieldError(
                        eventCodeField,
                        `Transition invalide depuis l'état "${currentStateField.value}"`
                    );
                    // Add form-error class for test
                    const errorElement = eventCodeField.closest('.space-y-2').querySelector('.error-message');
                    if (errorElement) {
                        errorElement.classList.add('form-error');
                    }
                }
            });
        }
    }
};

function initializeGenericForm(form) {
    if (!form.matches('[data-generic-form]') || form.dataset.genericFormReady === 'true') return;
    form.dataset.genericFormReady = 'true';

    form.querySelectorAll('select[data-select-single-option]').forEach((select) => {
        if (!select.value && select.options.length === 2) select.selectedIndex = 1;
    });

    const protocol = form.querySelector('[name="kind"]');
    const protocolFields = {
        MLLP: [['host', true], ['port', true]],
        FILE: [['inbox_path', true], ['outbox_path', true], ['archive_path', false], ['error_path', false], ['file_extensions', false]],
        FHIR: [['base_url', true], ['auth_kind', false], ['auth_token', false]],
    };
    const allProtocolFieldNames = new Set(Object.values(protocolFields).flat().map(([name]) => name));
    const updateProtocolFields = () => {
        if (!protocol) return;
        const visibleFields = new Map(protocolFields[protocol.value] || []);
        allProtocolFieldNames.forEach((name) => {
            const field = form.querySelector(`[name="${name}"]`);
            if (!field) return;
            field.closest('.space-y-2')?.toggleAttribute('hidden', !visibleFields.has(name));
            field.required = visibleFields.get(name) === true;
        });
    };
    protocol?.addEventListener('change', updateProtocolFields);
    updateProtocolFields();

    form.addEventListener('click', (event) => {
        if (event.target.closest('button[type="submit"], input[type="submit"]')) {
            form.dataset.submitAttempted = 'true';
        }
    });
    form.addEventListener('keydown', (event) => {
        if (!(event.ctrlKey || event.metaKey) || event.key.toLowerCase() !== 's') return;
        event.preventDefault();
        const submit = form.querySelector('button[type="submit"], input[type="submit"]');
        if (submit && !submit.disabled) form.requestSubmit(submit);
    });
}

// Initialisation automatique
function initializeForms() {
    document.querySelectorAll('form').forEach(form => {
        // Skip forms with data-no-ajax attribute (e.g., filter forms that should use GET)
        if (form.hasAttribute('data-no-ajax')) {
            return; // Don't initialize FormManager for these forms
        }
        
        initializeGenericForm(form);

        // Créer une instance de FormManager pour chaque formulaire
        const manager = new FormManager(form);
        form.manager = manager; // Stocker la référence pour un accès facile
        try { form.setAttribute('data-forms-manager', '1'); } catch(e) {}

        // Setup transition validation si nécessaire
        if (form.classList.contains('has-state-transitions')) {
            StateTransitionManager.setupTransitionValidation(form);
        }
    });
}

// If the script is injected after DOMContentLoaded (cache-busting or deferred
// loading), ensure we still initialize forms immediately.
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeForms);
} else {
    // DOM already ready — initialize right away
    try {
        initializeForms();
    } catch (e) {
        console.error('Failed to initialize forms:', e);
    }
}

// Fallback: capture submit events early and ensure a FormManager exists.
// This prevents a race where the form is submitted before the script
// attached handlers (e.g., due to deferred/dynamic script loading).
document.addEventListener('submit', function (e) {
    const form = e.target;
    if (!form) return;
    
    // Skip forms with data-no-ajax attribute (e.g., filter forms that should use GET)
    if (form.hasAttribute('data-no-ajax')) {
        return; // Let the form submit normally
    }
    
    // If a manager already exists, let it handle the event
    if (form.manager) return;

    // Prevent the native submit and create a manager to handle it
    try {
        e.preventDefault();
    } catch (err) {
        // ignore
    }
    try {
    const mgr = new FormManager(form);
    form.manager = mgr;
    try { form.setAttribute('data-forms-manager', '1'); } catch(e) {}
        // Call handleSubmit with the original event where possible
        if (typeof mgr.handleSubmit === 'function') {
            mgr.handleSubmit(e);
        } else {
            // Fallback: submit the form normally if handler missing
            form.submit();
        }
    } catch (err) {
        console.error('Fallback form submission failed:', err);
        try { form.submit(); } catch (e) {}
    }
}, true);
