/* Workflow de création d'un mouvement et recherche de localisation. */
"use strict";

const movementSuccessBanner = document.getElementById('movement-success-banner');
if (movementSuccessBanner) {
  window.setTimeout(() => {
    const url = new URL(window.location);
    url.searchParams.delete('success');
    window.history.replaceState({}, '', url.toString());
    movementSuccessBanner.classList.add('hidden');
  }, 3500);
}

// UX simplifiée : sélection dropdown + affichage dynamique
(function() {
  const eventCatalog = JSON.parse(document.getElementById('workflow-event-catalog').textContent);
  
  const eventSelect = document.getElementById('event_code_field');
  const eventCards = document.querySelectorAll('.event-card');
  const locationField = document.getElementById('location-field');
  const locationSelect = document.getElementById('location-select');
  const locationPath = document.getElementById('location-path');
  const locationDisplay = document.getElementById('location-display');
  const clearLocationBtn = document.getElementById('clear-location');
  const bedSearch = document.getElementById('bed-search');
  const reasonField = document.querySelector('[name="reason"]');
  const submitButton = document.getElementById('submit-button');
  const eventDescription = document.getElementById('event-description');
  const eventDescriptionText = document.getElementById('event-description-text');
  const movementDateTime = document.getElementById('movement_datetime');
  const feedback = document.getElementById('movement-form-feedback');

  function updateCardSelection(selectedCode) {
    eventCards.forEach((card) => {
      const code = card.getAttribute('data-event-code');
      if (code === selectedCode) {
        card.classList.add('border-blue-500', 'bg-blue-50/90', 'shadow-md', 'ring-1', 'ring-blue-200');
        card.classList.remove('border-slate-200');
        card.setAttribute('aria-pressed', 'true');
      } else {
        card.classList.remove('border-blue-500', 'bg-blue-50/90', 'shadow-md', 'ring-1', 'ring-blue-200');
        card.classList.add('border-slate-200');
        card.setAttribute('aria-pressed', 'false');
      }
    });
  }

  // Service accordion toggle
  document.querySelectorAll('.service-toggle').forEach((toggle) => {
    toggle.addEventListener('click', () => {
      const content = toggle.nextElementSibling;
      const chevron = toggle.querySelector('.service-chevron');
      
      if (content.classList.contains('hidden')) {
        content.classList.remove('hidden');
        chevron.style.transform = 'rotate(90deg)';
      } else {
        content.classList.add('hidden');
        chevron.style.transform = 'rotate(0deg)';
      }
    });
  });

  // Bed selection logic
  document.querySelectorAll('.bed-option').forEach((bedBtn) => {
    bedBtn.addEventListener('click', () => {
      const bedName = bedBtn.getAttribute('data-bed-name');
      const fullPath = bedBtn.getAttribute('data-full-path');
      const bedStatus = bedBtn.getAttribute('data-bed-status');
      
      // Update hidden input
      locationSelect.value = bedName;
      
      // Update display
      locationPath.textContent = fullPath;
      locationDisplay.classList.remove('hidden');
      
      // Visual feedback on selected bed
      document.querySelectorAll('.bed-option').forEach((btn) => {
        btn.classList.remove('ring-2', 'ring-blue-500', 'ring-offset-1');
      });
      bedBtn.classList.add('ring-2', 'ring-blue-500', 'ring-offset-1');
      
      // Enable submit if all required fields are filled
      validateForm();
    });
  });

  // Clear location selection
  if (clearLocationBtn) {
    clearLocationBtn.addEventListener('click', () => {
      locationSelect.value = '';
      locationDisplay.classList.add('hidden');
      document.querySelectorAll('.bed-option').forEach((btn) => {
        btn.classList.remove('ring-2', 'ring-blue-500', 'ring-offset-1');
      });
      validateForm();
    });
  }

  // Bed search / Autocomplete functionality (debounced server lookup, fallback to local filter)
  if (bedSearch) {
    const suggestionsBox = document.getElementById('bed-suggestions');
    const litIdInput = document.getElementById('lit-id-input');
    let locationSearchController = null;

    function debounce(fn, delay) {
      let t;
      return (...args) => {
        clearTimeout(t);
        t = setTimeout(() => fn(...args), delay);
      };
    }

    async function fetchSuggestions(term) {
      locationSearchController?.abort();
      const controller = new AbortController();
      locationSearchController = controller;
      try {
        const { data } = await window.medbridgeHttp.get(
          `/api/mouvements/location-search?q=${encodeURIComponent(term)}&limit=10`,
          { signal: controller.signal },
        );
        if (locationSearchController !== controller) return null;
        return data;
      } catch (e) {
        if (controller.signal.aborted) return null;
        console.warn('Autocomplete fetch failed', e);
        suggestionsBox.innerHTML = '<div class="flex items-center justify-between gap-3 px-3 py-2 text-sm text-red-600" role="alert">Recherche indisponible.<button type="button" data-retry-location-search class="rounded border border-red-300 px-2 py-1 font-medium hover:bg-red-50">Réessayer</button></div>';
        suggestionsBox.classList.remove('hidden');
        return null;
      } finally {
        if (locationSearchController === controller) locationSearchController = null;
      }
    }

    function renderSuggestions(items) {
      suggestionsBox.innerHTML = '';
      if (!items || items.length === 0) {
        suggestionsBox.classList.add('hidden');
        return;
      }
      items.forEach((it) => {
        const el = document.createElement('div');
        el.className = 'px-3 py-2 hover:bg-slate-50 cursor-pointer';
        el.textContent = `${it.full_path}`;
        el.dataset.type = it.type || '';
        el.dataset.id = it.id || '';
        el.dataset.label = it.label || '';
        el.addEventListener('click', () => {
          // When a suggestion is clicked, set hidden inputs and display
          const full = it.full_path || it.label;
          document.getElementById('location-select').value = full;
          if (it.type === 'lit' && it.id) {
            litIdInput.value = it.id;
            document.getElementById('location-path').textContent = full;
          } else {
            litIdInput.value = '';
            document.getElementById('location-path').textContent = full;
          }
          locationDisplay.classList.remove('hidden');
          // highlight corresponding bed if present in DOM
          document.querySelectorAll('.bed-option').forEach((btn) => btn.classList.remove('ring-2','ring-blue-500','ring-offset-1'));
          // close suggestions
          suggestionsBox.classList.add('hidden');
          validateForm();
        });
        suggestionsBox.appendChild(el);
      });
      suggestionsBox.classList.remove('hidden');
    }

    const doSearch = debounce(async (e) => {
      const term = e.target.value.trim();
      if (!term) {
        locationSearchController?.abort();
        locationSearchController = null;
        // restore full list
        document.querySelectorAll('.service-group').forEach(sg => { sg.style.display = ''; sg.querySelectorAll('.chambre-group, .uf-group').forEach(n => n.style.display=''); });
        suggestionsBox.classList.add('hidden');
        return;
      }

      if (term.length < 3) {
        locationSearchController?.abort();
        locationSearchController = null;
        // fallback to local DOM filter for short terms
        document.querySelectorAll('.service-group').forEach((serviceGroup) => {
          let serviceHasMatch = false;
          const serviceName = serviceGroup.getAttribute('data-service-name').toLowerCase();
          
          serviceGroup.querySelectorAll('.uf-group').forEach((ufGroup) => {
            let ufHasMatch = false;
            const ufName = ufGroup.getAttribute('data-uf-name').toLowerCase();
            
            ufGroup.querySelectorAll('.chambre-group').forEach((chambreGroup) => {
              let chambreHasMatch = false;
              const chambreName = chambreGroup.getAttribute('data-chambre-name').toLowerCase();
              
              chambreGroup.querySelectorAll('.bed-option').forEach((bedBtn) => {
                const bedName = bedBtn.getAttribute('data-bed-name').toLowerCase();
                const matches = serviceName.includes(term) || 
                              ufName.includes(term) || 
                              chambreName.includes(term) || 
                              bedName.includes(term);
                
                if (matches) {
                  bedBtn.style.display = '';
                  chambreHasMatch = true;
                  ufHasMatch = true;
                  serviceHasMatch = true;
                } else {
                  bedBtn.style.display = 'none';
                }
              });
              
              chambreGroup.style.display = chambreHasMatch ? '' : 'none';
            });
            
            ufGroup.style.display = ufHasMatch ? '' : 'none';
          });
          
          serviceGroup.style.display = serviceHasMatch ? '' : 'none';
        });
        suggestionsBox.classList.add('hidden');
        return;
      }

      // remote lookup
      suggestionsBox.innerHTML = '<div class="px-3 py-2 text-sm text-slate-500" aria-live="polite">Recherche en cours…</div>';
      suggestionsBox.classList.remove('hidden');
      const items = await fetchSuggestions(term);
      if (items === null) return;
      renderSuggestions(items);
    }, 250);

    bedSearch.addEventListener('input', doSearch);
    suggestionsBox.addEventListener('click', (event) => {
      if (event.target.closest('[data-retry-location-search]')) {
        doSearch({ target: bedSearch });
      }
    });
  }
  
  // Validation function
  function validateForm() {
    const eventCode = eventSelect.value;
    if (!eventCode) {
      submitButton.disabled = true;
      return;
    }
    
    const metadata = eventCatalog[eventCode];
    if (metadata && metadata.requires_location) {
      const location = locationSelect.value;
      submitButton.disabled = !location;
    } else {
      submitButton.disabled = false;
    }
  }
  
  // Sélection via les cartes d'événements
  if (eventCards && eventCards.length) {
    eventCards.forEach((card) => {
      card.addEventListener('click', () => {
        const code = card.getAttribute('data-event-code');
        if (!code) return;
        eventSelect.value = code;
        updateCardSelection(code);
        eventSelect.dispatchEvent(new Event('change', { bubbles: true }));
      });
    });
  }
  
  // Quand on change l'événement
  eventSelect.addEventListener('change', function() {
    const eventCode = this.value;
    
    if (!eventCode) {
      // Réinitialiser
      locationField.classList.add('hidden');
      eventDescription.classList.add('hidden');
      submitButton.disabled = true;
      return;
    }
    
    const metadata = eventCatalog[eventCode];
    if (!metadata) {
      console.warn('Métadonnées introuvables pour', eventCode);
      return;
    }
    
    // Mettre à jour la sélection visuelle des cartes
    updateCardSelection(eventCode);

    // Afficher la description
    eventDescription.classList.remove('hidden');
    eventDescriptionText.textContent = metadata.description;
    
    // Afficher/masquer le champ localisation
    if (metadata.requires_location) {
      locationField.classList.remove('hidden');
      locationSelect.required = true;
    } else {
      locationField.classList.add('hidden');
      locationSelect.required = false;
      locationSelect.value = '';
      if (locationDisplay) locationDisplay.classList.add('hidden');
    }
    
    // Placeholder du commentaire
    reasonField.placeholder = metadata.description;
    
    // Activer le bouton
    validateForm();
  });
  
  // Validation avant soumission
  document.getElementById('movement-form').addEventListener('submit', function(e) {
    const dateValue = movementDateTime.value;
    if (!dateValue) {
      e.preventDefault();
      if (feedback) {
        feedback.textContent = 'Veuillez saisir une date et heure pour le mouvement.';
      }
      if (window.toastSystem?.show) {
        window.toastSystem.show('Veuillez saisir une date et heure pour le mouvement.', 'error');
      }
      movementDateTime.focus();
      return false;
    }

    if (feedback) {
      feedback.textContent = 'Enregistrement du mouvement en cours.';
    }
  });
  
  // Raccourcis clavier globaux
  document.addEventListener('keydown', (e) => {
    // Alt+1/2/3 pour sélection rapide événements
    if (e.altKey && !e.ctrlKey && !e.shiftKey) {
      const cards = Array.from(document.querySelectorAll('.event-card'));
      const index = parseInt(e.key) - 1;
      if (index >= 0 && index < cards.length && !e.target.matches('input, textarea, select')) {
        e.preventDefault();
        cards[index].click();
        cards[index].scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    }
    
    // Ctrl+L pour accéder au plan de lits
    if ((e.ctrlKey || e.metaKey) && e.key === 'l' && !e.target.matches('input, textarea, select')) {
      e.preventDefault();
      window.location.href = '/mouvements/plan-lits';
    }
  });
})();
