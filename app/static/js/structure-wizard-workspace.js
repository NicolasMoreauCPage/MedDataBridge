  document.addEventListener('DOMContentLoaded', () => {
    const steps = Array.from(document.querySelectorAll('[data-step]'));
    const contents = Array.from(document.querySelectorAll('[data-step-content]'));
    const prevBtn = document.getElementById('wizardPrev');
    const nextBtn = document.getElementById('wizardNext');
    const templateCards = document.getElementById('templateCards');
    const targetEgId = document.getElementById('targetEgId');
    const progressStatus = document.getElementById('wizardProgressStatus');
    const wizardContent = document.getElementById('wizardContent');
    const dirtyStatus = document.getElementById('wizardDirtyStatus');
    let selectedTemplate = null;
    let templatePayload = null; // Stocke le payload JSON du template sélectionné
    let isTemplateLoading = false;
    let templateRequestToken = 0;
    let currentStep = 1;
    let isDirty = false;

    function escapeHtml(value) {
      const node = document.createElement('span');
      node.textContent = String(value ?? '');
      return node.innerHTML;
    }

    function notify(message, type = 'info') {
      if (window.toastSystem) window.toastSystem.show(message, type);
    }

    function markDirty() {
      if (isDirty) return;
      isDirty = true;
      if (dirtyStatus) dirtyStatus.textContent = 'Modifications non enregistrées.';
    }

    function clearDirty() {
      isDirty = false;
      if (dirtyStatus) dirtyStatus.textContent = 'Toutes les modifications sont enregistrées.';
    }

    window.addEventListener('beforeunload', (event) => {
      if (!isDirty) return;
      event.preventDefault();
      event.returnValue = '';
    });
    targetEgId?.addEventListener('change', markDirty);
    wizardContent?.addEventListener('input', markDirty);
    wizardContent?.addEventListener('change', markDirty);

    function confirmAction(options) {
      if (!window.PameliaUi?.confirm) {
        notify("Le dialogue de confirmation n'est pas disponible.", 'error');
        return Promise.resolve(false);
      }
      return window.PameliaUi.confirm(options);
    }

    function openInputDialog({ title, description, acceptLabel = 'Ajouter', fields }) {
      const dialog = document.getElementById('structure-wizard-input-dialog');
      const form = document.getElementById('structure-wizard-input-form');
      const fieldContainer = document.getElementById('structure-wizard-input-fields');
      const titleElement = document.getElementById('structure-wizard-input-title');
      const descriptionElement = document.getElementById('structure-wizard-input-description');
      const accept = document.getElementById('structure-wizard-input-accept');
      if (!dialog || !form || !fieldContainer || !titleElement || !descriptionElement || !accept) {
        notify('Le formulaire de saisie n’est pas disponible.', 'error');
        return Promise.resolve(null);
      }
      titleElement.textContent = title;
      descriptionElement.textContent = description || '';
      accept.textContent = acceptLabel;
      fieldContainer.replaceChildren();
      fields.forEach((definition) => {
        const label = document.createElement('label');
        label.className = 'block text-sm font-medium';
        label.textContent = definition.label;
        const input = document.createElement(definition.type === 'select' ? 'select' : 'input');
        input.name = definition.name;
        input.required = Boolean(definition.required);
        input.className = 'mt-1 w-full rounded-lg border-slate-300 px-3 py-2 dark:border-slate-600 dark:bg-slate-900';
        if (definition.type === 'select') {
          const placeholder = document.createElement('option');
          placeholder.value = '';
          placeholder.textContent = definition.placeholder || 'Sélectionner';
          input.append(placeholder);
          (definition.options || []).forEach((option) => {
            const choice = document.createElement('option');
            choice.value = option.value;
            choice.textContent = option.label;
            input.append(choice);
          });
        } else {
          input.type = definition.type || 'text';
          input.value = definition.value || '';
          input.placeholder = definition.placeholder || '';
          if (definition.min !== undefined) input.min = String(definition.min);
        }
        label.append(input);
        fieldContainer.append(label);
      });
      dialog.returnValue = '';
      return new Promise((resolve) => {
        dialog.addEventListener('close', () => {
          const values = dialog.returnValue === 'confirm' ? Object.fromEntries(new FormData(form).entries()) : null;
          resolve(values);
        }, { once: true });
        dialog.showModal();
        fieldContainer.querySelector('input, select')?.focus();
      });
    }

    function updateStepDisplay() {
      steps.forEach(stepEl => {
        const step = Number(stepEl.dataset.step);
        if (step === currentStep) {
          stepEl.setAttribute('aria-current', 'step');
          stepEl.classList.remove('opacity-60');
          const badge = stepEl.querySelector('span');
          badge.classList.remove('bg-slate-200', 'text-slate-700');
          badge.classList.add('bg-indigo-600', 'text-white');
        } else {
          stepEl.removeAttribute('aria-current');
          stepEl.classList.add('opacity-60');
          const badge = stepEl.querySelector('span');
          badge.classList.remove('bg-indigo-600', 'text-white');
          badge.classList.add('bg-slate-200', 'text-slate-700');
        }
      });
      contents.forEach(contentEl => {
        const step = Number(contentEl.dataset.stepContent);
        contentEl.classList.toggle('hidden', step !== currentStep);
      });
      const activeHeading = contents.find(
        (contentEl) => Number(contentEl.dataset.stepContent) === currentStep,
      )?.querySelector('h2')?.textContent?.trim();
      if (progressStatus && activeHeading) {
        progressStatus.textContent = `Étape ${currentStep} sur ${steps.length} : ${activeHeading}`;
      }
      prevBtn.disabled = currentStep === 1;
      nextBtn.disabled = currentStep === 1 && isTemplateLoading;
      nextBtn.textContent = currentStep === 5
        ? 'Terminer'
        : isTemplateLoading
          ? 'Chargement du modèle…'
          : 'Suivant →';
    }

    function getStructureValidationError({ includeUfs = true } = {}) {
      if (!Array.isArray(templatePayload?.poles) || templatePayload.poles.length === 0) {
        return { step: 2, selector: '#addPoleBtn', message: 'Ajoutez et nommez au moins un pôle avant de poursuivre.' };
      }
      for (const [poleIndex, pole] of templatePayload.poles.entries()) {
        if (typeof pole?.name !== 'string' || !pole.name.trim()) {
          return { step: 2, selector: `[data-structure-field="pole:${poleIndex}"]`, message: `Nommez le pôle ${poleIndex + 1} avant de poursuivre.` };
        }
        if (!Array.isArray(pole.services)) continue;
        for (const [serviceIndex, service] of pole.services.entries()) {
          if (typeof service?.name !== 'string' || !service.name.trim()) {
            return { step: 2, selector: `[data-structure-field="service:${poleIndex}:${serviceIndex}"]`, message: `Nommez le service ${serviceIndex + 1} du pôle ${poleIndex + 1}.` };
          }
          if (!includeUfs || !Array.isArray(service.ufs)) continue;
          for (const [ufIndex, uf] of service.ufs.entries()) {
            if (typeof uf?.name !== 'string' || !uf.name.trim()) {
              return { step: 3, selector: `[data-structure-field="uf:${poleIndex}:${serviceIndex}:${ufIndex}"]`, message: `Nommez l’UF ${ufIndex + 1} du service ${serviceIndex + 1}.` };
            }
          }
        }
      }
      return null;
    }

    function focusValidationError(validationError) {
      document.querySelector(validationError.selector)?.focus();
    }

    prevBtn.addEventListener('click', () => {
      if (currentStep > 1) {
        currentStep -= 1;
        updateStepDisplay();
        if (currentStep === 2) {
          loadStep2Content();
        }
        if (currentStep === 3) {
          loadStep3Content();
        }
        if (currentStep === 4) {
          loadStep4Content();
        }
        if (currentStep === 5) {
          loadStep5Content();
        }
      }
    });

    nextBtn.addEventListener('click', () => {
      if (currentStep < 5) {
        if (currentStep === 1 && !targetEgId?.value) {
          notify('Sélectionnez d’abord l’entité géographique cible.', 'warning');
          targetEgId?.focus();
          return;
        }
        if (currentStep === 1 && !selectedTemplate) {
          notify('Sélectionnez d’abord un modèle de structure.', 'warning');
          return;
        }
        if (currentStep === 1 && isTemplateLoading) {
          notify('Le modèle sélectionné est en cours de chargement.', 'info');
          return;
        }
        if (currentStep === 1 && !templatePayload) {
          notify('Le modèle n’a pas pu être chargé. Sélectionnez-en un autre.', 'warning');
          return;
        }
        const validationError = currentStep === 2
          ? getStructureValidationError({ includeUfs: false })
          : currentStep === 3
            ? getStructureValidationError()
            : null;
        if (validationError) {
          notify(validationError.message, 'warning');
          focusValidationError(validationError);
          return;
        }
        currentStep += 1;
        updateStepDisplay();
        if (currentStep === 2) {
          loadStep2Content();
        }
        if (currentStep === 3) {
          loadStep3Content();
        }
        if (currentStep === 4) {
          loadStep4Content();
        }
        if (currentStep === 5) {
          loadStep5Content();
        }
      } else {
        // Le bouton "Suivant" au step 5 ne fait rien, on utilise le bouton "Générer la structure"
      }
    });

    async function loadTemplates() {
      if (!templateCards) return;
      templateCards.innerHTML = '<div class="col-span-1 text-sm text-slate-500">Chargement des templates…</div>';
      try {
        const { data } = await window.medbridgeHttp.get('/api/structure/templates');
        if (!Array.isArray(data) || data.length === 0) {
          templateCards.innerHTML = '<div class="col-span-1 text-sm text-slate-500">Aucun template disponible pour le moment.</div>';
          return;
        }
        templateCards.innerHTML = '';
        for (const tpl of data) {
          const btn = document.createElement('button');
          btn.type = 'button';
          btn.dataset.template = tpl.key;
          btn.dataset.templateId = tpl.id;
          btn.className = 'border rounded-xl p-3 text-left bg-white hover:bg-slate-50 hover:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 transition-all duration-150 shadow-sm hover:shadow-md transform hover:-translate-y-0.5 flex flex-col gap-1';
          const emoji = tpl.key === 'chu' ? '🏥' : tpl.key === 'ch' ? '🏨' : tpl.key === 'clinique' ? '🏪' : '🏥';
          btn.innerHTML = `
            <div class="text-sm font-semibold text-slate-900 mb-1">${emoji} ${escapeHtml(tpl.name)}</div>
            <p class="text-xs text-slate-600 mb-1">${escapeHtml(tpl.description || 'Template de structure hospitalière.')}</p>
            <p class="text-[11px] text-slate-600 dark:text-slate-300">ID template : ${escapeHtml(tpl.key)}</p>
          `;
          templateCards.appendChild(btn);
        }

        templateCards.addEventListener('click', async (event) => {
          const card = event.target.closest('[data-template]');
          if (!card) return;
          templateCards.querySelectorAll('[data-template]').forEach(el => {
            el.classList.remove('ring-2', 'ring-indigo-500', 'border-indigo-500');
          });
          card.classList.add('ring-2', 'ring-indigo-500', 'border-indigo-500');
          selectedTemplate = {
            id: card.dataset.templateId,
            key: card.dataset.template,
          };
          markDirty();
          // Charger le payload du template sélectionné
          const requestToken = ++templateRequestToken;
          isTemplateLoading = true;
          templatePayload = null;
          updateStepDisplay();
          card.setAttribute('aria-busy', 'true');
          await loadTemplatePayload(selectedTemplate.id, requestToken);
          if (requestToken === templateRequestToken) {
            card.removeAttribute('aria-busy');
          }
          console.log('Template sélectionné :', selectedTemplate);
        });
      } catch (err) {
        console.error('Erreur chargement templates', err);
        templateCards.innerHTML = '<div class="col-span-1 text-sm text-red-600">Erreur lors du chargement des templates.</div>';
      }
    }

    async function loadTemplatePayload(templateId, requestToken) {
      try {
        const { data } = await window.medbridgeHttp.get(
          `/api/structure/templates/${templateId}`,
        );
        if (requestToken !== templateRequestToken) return;
        templatePayload = data.payload ? JSON.parse(data.payload) : null;
        console.log('Payload du template chargé:', templatePayload);
        notify('Modèle chargé. Vous pouvez poursuivre la configuration.', 'success');
      } catch (err) {
        if (requestToken !== templateRequestToken) return;
        console.error('Erreur chargement payload template', err);
        templatePayload = null;
        selectedTemplate = null;
        notify('Impossible de charger ce modèle de structure.', 'error');
      } finally {
        if (requestToken === templateRequestToken) {
          isTemplateLoading = false;
          updateStepDisplay();
        }
      }
    }

    function loadStep2Content() {
      const noTemplateMsg = document.getElementById('noTemplateMsg');
      const polesContainer = document.getElementById('polesContainer');
      const addPoleBtn = document.getElementById('addPoleBtn');
      const selectedTemplateName = document.getElementById('selectedTemplateName');

      if (!selectedTemplate || !templatePayload) {
        noTemplateMsg.classList.remove('hidden');
        polesContainer.classList.add('hidden');
        addPoleBtn.classList.add('hidden');
        return;
      }

      noTemplateMsg.classList.add('hidden');
      polesContainer.classList.remove('hidden');
      addPoleBtn.classList.remove('hidden');

      // Afficher le nom du template
      const templates = {chu: 'CHU', ch: 'Centre Hospitalier', clinique: 'Clinique'};
      selectedTemplateName.textContent = templates[selectedTemplate.key] || selectedTemplate.key;

      // Rendre les pôles
      polesContainer.innerHTML = '';
      if (templatePayload.poles && Array.isArray(templatePayload.poles)) {
        templatePayload.poles.forEach((pole, poleIndex) => {
          const poleCard = document.createElement('div');
          poleCard.className = 'bg-slate-50 border border-slate-200 rounded-lg p-3';
          poleCard.innerHTML = `
            <div class="flex items-center justify-between mb-2">
              <div class="flex items-center gap-2 flex-1">
                <span class="text-lg">🏢</span>
                <div class="flex-1">
                  <div class="flex items-center gap-2">
                    <input type="text" 
                           value="${escapeHtml(pole.name)}"
                           data-structure-field="pole:${poleIndex}"
                           class="text-sm font-semibold text-slate-900 border-0 bg-transparent hover:bg-white hover:border hover:border-slate-300 focus:bg-white focus:border focus:border-blue-500 rounded px-2 py-0.5 transition-all"
                           data-wizard-action="update-pole-name" data-pole-index="${poleIndex}" />
                  </div>
                  <div class="text-xs text-slate-500 mt-0.5">
                    <input type="text" 
                           value="${escapeHtml(pole.short_name || '')}"
                           placeholder="Code court"
                           class="w-24 border-0 bg-transparent hover:bg-white hover:border hover:border-slate-300 focus:bg-white focus:border focus:border-blue-500 rounded px-1 py-0.5 text-xs transition-all"
                           data-wizard-action="update-pole-short-name" data-pole-index="${poleIndex}" />
                    • ${pole.services?.length || 0} service(s)
                  </div>
                </div>
              </div>
              <button type="button" class="text-xs text-red-600 hover:text-red-800" data-wizard-action="remove-pole" data-pole-index="${poleIndex}">
                🗑️ Supprimer
              </button>
            </div>
            <div class="ml-8 space-y-1">
              ${(pole.services || []).map((svc, svcIndex) => `
                <div class="flex items-center gap-2 text-xs text-slate-600">
                  <span>•</span>
                  <input type="text" 
                         value="${escapeHtml(svc.name)}"
                         data-structure-field="service:${poleIndex}:${svcIndex}"
                         class="flex-1 border-0 bg-transparent hover:bg-white hover:border hover:border-slate-300 focus:bg-white focus:border focus:border-blue-500 rounded px-2 py-0.5 text-xs transition-all"
                         data-wizard-action="update-service-name" data-pole-index="${poleIndex}" data-service-index="${svcIndex}" />
                  <span class="text-slate-400">(${svc.ufs?.length || 0} UF)</span>
                  <button type="button" class="text-red-500 hover:text-red-700" data-wizard-action="remove-service" data-pole-index="${poleIndex}" data-service-index="${svcIndex}">
                    🗑️
                  </button>
                </div>
              `).join('')}
              <button type="button" 
                      class="ml-4 mt-2 text-xs text-blue-600 hover:text-blue-800 flex items-center gap-1"
                      data-wizard-action="add-service" data-pole-index="${poleIndex}">
                <span>➕</span> Ajouter un service
              </button>
            </div>
          `;
          polesContainer.appendChild(poleCard);
        });
      }
    }

    window.updatePoleName = function(poleIndex, newName) {
      if (templatePayload?.poles?.[poleIndex]) {
        templatePayload.poles[poleIndex].name = newName;
      }
    };

    window.updatePoleShortName = function(poleIndex, newShortName) {
      if (templatePayload?.poles?.[poleIndex]) {
        templatePayload.poles[poleIndex].short_name = newShortName;
      }
    };

    window.updateServiceName = function(poleIndex, serviceIndex, newName) {
      if (templatePayload?.poles?.[poleIndex]?.services?.[serviceIndex]) {
        templatePayload.poles[poleIndex].services[serviceIndex].name = newName;
      }
    };

    window.removePole = async function(poleIndex) {
      if (templatePayload?.poles) {
        const confirmed = await confirmAction({
          title: 'Supprimer le pôle',
          acceptLabel: 'Supprimer',
          variant: 'danger',
          message: 'Supprimer ce pôle et tous ses services du modèle en cours ?',
        });
        if (!confirmed) return;
        templatePayload.poles.splice(poleIndex, 1);
        loadStep2Content();
      }
    };

    window.removeService = async function(poleIndex, serviceIndex) {
      if (templatePayload?.poles?.[poleIndex]?.services) {
        const confirmed = await confirmAction({
          title: 'Supprimer le service',
          acceptLabel: 'Supprimer',
          variant: 'danger',
          message: 'Supprimer ce service du modèle en cours ?',
        });
        if (!confirmed) return;
        templatePayload.poles[poleIndex].services.splice(serviceIndex, 1);
        loadStep2Content();
      }
    };

    window.addServiceToPole = async function(poleIndex) {
      const values = await openInputDialog({
        title: 'Ajouter un service',
        description: 'Le service sera ajouté au pôle sélectionné.',
        fields: [{ name: 'name', label: 'Nom du service', required: true, placeholder: 'Ex. Cardiologie' }],
      });
      const serviceName = values?.name?.trim();
      if (serviceName && templatePayload?.poles?.[poleIndex]) {
        if (!templatePayload.poles[poleIndex].services) {
          templatePayload.poles[poleIndex].services = [];
        }
        templatePayload.poles[poleIndex].services.push({
          name: serviceName,
          short_name: '',
          type: 'service',
          ufs: []
        });
        loadStep2Content();
      }
    };

    // Gestionnaire du bouton "Ajouter un pôle"
    const addPoleBtn = document.getElementById('addPoleBtn');
    addPoleBtn?.addEventListener('click', async () => {
      const values = await openInputDialog({
        title: 'Ajouter un pôle',
        description: 'Vous pourrez compléter ses services à l’étape suivante.',
        fields: [
          { name: 'name', label: 'Nom du pôle', required: true, placeholder: 'Ex. Pôle médecine' },
          { name: 'short_name', label: 'Code court', placeholder: 'Ex. MED' },
        ],
      });
      const poleName = values?.name?.trim();
      if (!poleName) return;
      
      if (!templatePayload) {
        templatePayload = { poles: [] };
      }
      if (!templatePayload.poles) {
        templatePayload.poles = [];
      }
      
      templatePayload.poles.push({
        name: poleName,
        short_name: values.short_name?.trim() || '',
        type: 'pole',
        services: []
      });
      
      loadStep2Content();
    });

    // ============ STEP 3: UF & Codes UM ============
    function loadStep3Content() {
      const ufsContainer = document.getElementById('ufsContainer');
      if (!ufsContainer || !templatePayload?.poles) return;

      ufsContainer.innerHTML = '';
      
      templatePayload.poles.forEach((pole, poleIndex) => {
        pole.services?.forEach((service, serviceIndex) => {
          const ufs = service.ufs || [];
          
          const serviceCard = document.createElement('div');
          serviceCard.className = 'border border-slate-200 rounded-lg p-3 bg-white';
          serviceCard.innerHTML = `
            <div class="flex items-center justify-between mb-2">
              <div>
                <span class="text-sm font-semibold text-slate-900">${escapeHtml(pole.name)} › ${escapeHtml(service.name)}</span>
                <span class="ml-2 text-xs text-slate-500">(${ufs.length} UF)</span>
              </div>
              <button type="button" class="text-xs text-indigo-600 hover:text-indigo-800" data-wizard-action="add-uf" data-pole-index="${poleIndex}" data-service-index="${serviceIndex}">
                + Ajouter UF
              </button>
            </div>
            <div class="space-y-2 ml-4">
              ${ufs.map((uf, ufIndex) => `
                <div class="flex items-center gap-2 text-xs">
                  <span class="text-slate-600">•</span>
                  <input type="text" value="${escapeHtml(uf.name || '')}" placeholder="Nom UF"
                         data-structure-field="uf:${poleIndex}:${serviceIndex}:${ufIndex}"
                         class="flex-1 border border-slate-300 rounded px-2 py-1 text-xs"
                         data-wizard-action="update-uf-name" data-pole-index="${poleIndex}" data-service-index="${serviceIndex}" data-uf-index="${ufIndex}" />
                  <input type="text" value="${escapeHtml(uf.code_um || '')}" placeholder="Code UM"
                         class="w-24 border border-slate-300 rounded px-2 py-1 text-xs"
                         data-wizard-action="update-uf-code" data-pole-index="${poleIndex}" data-service-index="${serviceIndex}" data-uf-index="${ufIndex}" />
                  <select class="border border-slate-300 rounded px-2 py-1 text-xs"
                          data-wizard-action="update-uf-type" data-pole-index="${poleIndex}" data-service-index="${serviceIndex}" data-uf-index="${ufIndex}">
                    <option value="mco" ${uf.type === 'mco' ? 'selected' : ''}>MCO</option>
                    <option value="ssr" ${uf.type === 'ssr' ? 'selected' : ''}>SSR</option>
                    <option value="psy" ${uf.type === 'psy' ? 'selected' : ''}>PSY</option>
                    <option value="had" ${uf.type === 'had' ? 'selected' : ''}>HAD</option>
                  </select>
                  <button type="button" class="text-red-500 hover:text-red-700" data-wizard-action="remove-uf" data-pole-index="${poleIndex}" data-service-index="${serviceIndex}" data-uf-index="${ufIndex}">🗑️</button>
                </div>
              `).join('')}
            </div>
          `;
          ufsContainer.appendChild(serviceCard);
        });
      });
    }

    window.addUfToService = function(poleIndex, serviceIndex) {
      if (!templatePayload?.poles?.[poleIndex]?.services?.[serviceIndex]) return;
      const service = templatePayload.poles[poleIndex].services[serviceIndex];
      if (!service.ufs) service.ufs = [];
      
      service.ufs.push({
        name: `UF ${service.ufs.length + 1}`,
        code_um: '',
        type: 'mco'
      });
      loadStep3Content();
    };

    window.updateUfName = function(poleIndex, serviceIndex, ufIndex, newName) {
      if (templatePayload?.poles?.[poleIndex]?.services?.[serviceIndex]?.ufs?.[ufIndex]) {
        templatePayload.poles[poleIndex].services[serviceIndex].ufs[ufIndex].name = newName;
      }
    };

    window.updateUfCodeUm = function(poleIndex, serviceIndex, ufIndex, newCode) {
      if (templatePayload?.poles?.[poleIndex]?.services?.[serviceIndex]?.ufs?.[ufIndex]) {
        templatePayload.poles[poleIndex].services[serviceIndex].ufs[ufIndex].code_um = newCode;
      }
    };

    window.updateUfType = function(poleIndex, serviceIndex, ufIndex, newType) {
      if (templatePayload?.poles?.[poleIndex]?.services?.[serviceIndex]?.ufs?.[ufIndex]) {
        templatePayload.poles[poleIndex].services[serviceIndex].ufs[ufIndex].type = newType;
      }
    };

    window.removeUf = async function(poleIndex, serviceIndex, ufIndex) {
      if (templatePayload?.poles?.[poleIndex]?.services?.[serviceIndex]?.ufs) {
        const confirmed = await confirmAction({
          title: 'Supprimer l’UF',
          acceptLabel: 'Supprimer',
          variant: 'danger',
          message: 'Supprimer cette unité fonctionnelle du modèle en cours ?',
        });
        if (!confirmed) return;
        templatePayload.poles[poleIndex].services[serviceIndex].ufs.splice(ufIndex, 1);
        loadStep3Content();
      }
    };

    // ============ STEP 4: Hébergement (UH optionnel) ============
    let uhList = [];

    function availableUfOptions() {
      const options = [];
      templatePayload?.poles?.forEach((pole, poleIndex) => {
        pole.services?.forEach((service, serviceIndex) => {
          service.ufs?.forEach((uf, ufIndex) => {
            options.push({
              value: `${poleIndex}:${serviceIndex}:${ufIndex}`,
              label: `${pole.name || 'Pôle'} › ${service.name || 'Service'} › ${uf.name || `UF ${ufIndex + 1}`}`,
            });
          });
        });
      });
      return options;
    }

    function loadStep4Content() {
      const uhsContainer = document.getElementById('uhsContainer');
      if (!uhsContainer) return;

      if (uhList.length === 0) {
        uhsContainer.innerHTML = '<p class="text-sm text-slate-500 italic">Aucune UH définie. Les UH permettent d\'organiser les chambres et lits par secteur.</p>';
        return;
      }

      uhsContainer.innerHTML = '';
      uhList.forEach((uh, index) => {
        const uhCard = document.createElement('div');
        uhCard.className = 'border border-slate-200 rounded-lg p-3 bg-slate-50';
        uhCard.innerHTML = `
          <div class="flex items-center justify-between">
            <div>
              <span class="text-sm font-semibold text-slate-900">${escapeHtml(uh.name)}</span>
              <span class="ml-2 text-xs text-slate-500">(${uh.chambres || 0} chambres, ${uh.lits || 0} lits)</span>
            </div>
            <button type="button" class="text-xs text-red-600 hover:text-red-800" data-wizard-action="remove-uh" data-uh-index="${index}">🗑️</button>
          </div>
        `;
        uhsContainer.appendChild(uhCard);
      });
    }

    const addUhBtn = document.getElementById('addUhBtn');
    addUhBtn?.addEventListener('click', async () => {
      const ufOptions = availableUfOptions();
      if (!ufOptions.length) {
        notify('Créez d’abord une UF avant d’ajouter une unité d’hébergement.', 'warning');
        return;
      }
      const values = await openInputDialog({
        title: 'Ajouter une unité d’hébergement',
        description: 'Les chambres et lits peuvent être complétés ultérieurement.',
        fields: [
          { name: 'name', label: 'Nom de l’unité d’hébergement', required: true, placeholder: 'Ex. UH Cardiologie' },
          { name: 'uf_ref', label: 'Unité fonctionnelle de rattachement', type: 'select', required: true, options: ufOptions },
          { name: 'chambres', label: 'Nombre de chambres', type: 'number', value: '0', min: 0 },
          { name: 'lits', label: 'Nombre de lits', type: 'number', value: '0', min: 0 },
        ],
      });
      const uhName = values?.name?.trim();
      if (!uhName) return;
      const chambresCount = Number.parseInt(values.chambres || '0', 10) || 0;
      const litsCount = Number.parseInt(values.lits || '0', 10) || 0;
      
      uhList.push({
        name: uhName,
        uf_ref: values.uf_ref,
        chambres: chambresCount,
        lits: litsCount
      });
      loadStep4Content();
    });

    window.removeUh = async function(index) {
      const confirmed = await confirmAction({
        title: 'Supprimer l’unité d’hébergement',
        acceptLabel: 'Supprimer',
        variant: 'danger',
        message: 'Supprimer cette unité d’hébergement du modèle en cours ?',
      });
      if (!confirmed) return;
      uhList.splice(index, 1);
      loadStep4Content();
    };

    // ============ STEP 5: Synthèse ============
    function loadStep5Content() {
      const summaryContainer = document.getElementById('summaryContainer');
      if (!summaryContainer) return;

      let totalServices = 0;
      let totalUfs = 0;
      
      if (templatePayload?.poles) {
        templatePayload.poles.forEach(pole => {
          totalServices += pole.services?.length || 0;
          pole.services?.forEach(service => {
            totalUfs += service.ufs?.length || 0;
          });
        });
      }

      summaryContainer.innerHTML = `
        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div class="bg-indigo-50 border border-indigo-200 rounded-lg p-4 text-center">
            <div class="text-3xl font-bold text-indigo-600">${templatePayload?.poles?.length || 0}</div>
            <div class="text-sm text-indigo-800 mt-1">Pôles</div>
          </div>
          <div class="bg-blue-50 border border-blue-200 rounded-lg p-4 text-center">
            <div class="text-3xl font-bold text-blue-600">${totalServices}</div>
            <div class="text-sm text-blue-800 mt-1">Services</div>
          </div>
          <div class="bg-green-50 border border-green-200 rounded-lg p-4 text-center">
            <div class="text-3xl font-bold text-green-600">${totalUfs}</div>
            <div class="text-sm text-green-800 mt-1">Unités Fonctionnelles</div>
          </div>
        </div>

        <div class="mt-4 space-y-3">
          ${(templatePayload?.poles || []).map(pole => `
            <div class="border border-slate-200 rounded-lg p-3 bg-white">
              <div class="font-semibold text-slate-900 mb-2">🏢 ${escapeHtml(pole.name)}</div>
              <div class="ml-4 space-y-1">
                ${(pole.services || []).map(service => `
                  <div class="text-sm text-slate-700">
                    • ${escapeHtml(service.name)}
                    <span class="text-xs text-slate-500">(${service.ufs?.length || 0} UF)</span>
                  </div>
                `).join('')}
              </div>
            </div>
          `).join('')}
        </div>

        ${uhList.length > 0 ? `
          <div class="mt-4 p-3 bg-amber-50 border border-amber-200 rounded-lg">
            <div class="text-sm font-semibold text-amber-900 mb-2">Hébergement</div>
            <div class="text-xs text-amber-800">
              ${uhList.length} UH définies, ${uhList.reduce((sum, uh) => sum + (uh.chambres || 0), 0)} chambres, 
              ${uhList.reduce((sum, uh) => sum + (uh.lits || 0), 0)} lits
            </div>
          </div>
        ` : ''}
      `;
    }

    const generateStructureBtn = document.getElementById('generateStructureBtn');
    generateStructureBtn?.addEventListener('click', async () => {
      const validationError = getStructureValidationError();
      if (validationError) {
        notify(validationError.message, 'warning');
        currentStep = validationError.step;
        updateStepDisplay();
        if (currentStep === 2) {
          loadStep2Content();
          focusValidationError(validationError);
        } else {
          loadStep3Content();
          focusValidationError(validationError);
        }
        return;
      }

      const egId = Number(targetEgId?.value);
      if (!Number.isInteger(egId) || egId <= 0) {
        notify('Sélectionnez une entité géographique cible valide.', 'warning');
        targetEgId?.focus();
        return;
      }

      const totalPoles = templatePayload.poles?.length || 0;
      const totalServices = templatePayload.poles?.reduce((sum, p) => sum + (p.services?.length || 0), 0) || 0;
      const totalUfs = templatePayload.poles?.reduce((sum, p) => sum + p.services?.reduce((s2, svc) => s2 + (svc.ufs?.length || 0), 0), 0) || 0;

      const confirmation = await confirmAction({
        title: 'Générer la structure',
        acceptLabel: 'Générer',
        variant: 'danger',
        message:
          `Créer cette structure dans l’EG sélectionnée ?\n\n` +
          `Pôles : ${totalPoles}\n` +
          `Services : ${totalServices}\n` +
          `UF : ${totalUfs}\n` +
          `UH : ${uhList.length}`,
      });

      if (!confirmation) return;

      try {
        generateStructureBtn.disabled = true;
        generateStructureBtn.textContent = '⏳ Génération en cours...';

        const { data: result } = await window.medbridgeHttp.post(
          '/api/structure/apply-template',
          {
            eg_id: egId,
            payload: templatePayload,
            uhs: uhList,
          },
        );
        
        notify(
          `${result.message} — ${result.created_entities.poles} pôle(s), ` +
          `${result.created_entities.services} service(s), ${result.created_entities.ufs} UF, ` +
          `${result.created_entities.uhs} UH.`,
          'success'
        );

        // Rediriger vers le dashboard structure
        clearDirty();
        window.location.href = '/structure';

      } catch (error) {
        console.error('Erreur:', error);
        notify(`Erreur lors de la génération : ${error.message}`, 'error');
        generateStructureBtn.disabled = false;
        generateStructureBtn.textContent = '🚀 Générer la structure';
      }
    });

    wizardContent?.addEventListener('change', (event) => {
      const field = event.target.closest('[data-wizard-action]');
      const action = field?.dataset.wizardAction;
      const poleIndex = Number.parseInt(field?.dataset.poleIndex || '', 10);
      const serviceIndex = Number.parseInt(field?.dataset.serviceIndex || '', 10);
      const ufIndex = Number.parseInt(field?.dataset.ufIndex || '', 10);

      if (action === 'update-pole-name') window.updatePoleName(poleIndex, field.value);
      if (action === 'update-pole-short-name') window.updatePoleShortName(poleIndex, field.value);
      if (action === 'update-service-name') window.updateServiceName(poleIndex, serviceIndex, field.value);
      if (action === 'update-uf-name') window.updateUfName(poleIndex, serviceIndex, ufIndex, field.value);
      if (action === 'update-uf-code') window.updateUfCodeUm(poleIndex, serviceIndex, ufIndex, field.value);
      if (action === 'update-uf-type') window.updateUfType(poleIndex, serviceIndex, ufIndex, field.value);
    });

    wizardContent?.addEventListener('click', (event) => {
      const actionButton = event.target.closest('[data-wizard-action]');
      const action = actionButton?.dataset.wizardAction;
      const poleIndex = Number.parseInt(actionButton?.dataset.poleIndex || '', 10);
      const serviceIndex = Number.parseInt(actionButton?.dataset.serviceIndex || '', 10);
      const ufIndex = Number.parseInt(actionButton?.dataset.ufIndex || '', 10);
      const uhIndex = Number.parseInt(actionButton?.dataset.uhIndex || '', 10);

      if (action === 'remove-pole') window.removePole(poleIndex);
      if (action === 'remove-service') window.removeService(poleIndex, serviceIndex);
      if (action === 'add-service') window.addServiceToPole(poleIndex);
      if (action === 'add-uf') window.addUfToService(poleIndex, serviceIndex);
      if (action === 'remove-uf') window.removeUf(poleIndex, serviceIndex, ufIndex);
      if (action === 'remove-uh') window.removeUh(uhIndex);
    });

    updateStepDisplay();
    loadTemplates();
  });
