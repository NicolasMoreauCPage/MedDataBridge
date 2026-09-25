/* Sélecteur cartographique de localisation partagé. */
"use strict";

document.addEventListener('DOMContentLoaded', async function() {
  const serviceSelect = document.getElementById('cart-service');
  const ufSelect = document.getElementById('cart-uf');
  const uhSelect = document.getElementById('cart-uh');
  const chambreSelect = document.getElementById('cart-chambre');
  const litGrid = document.getElementById('lit-grid');
  const litInput = document.getElementById('selected-lit-id');
  const breadcrumb = document.getElementById('hierarchy-breadcrumb');
  const stateAlert = document.getElementById('state-validation-alert');
  const stateMessage = document.getElementById('state-message');

  function showLitsMessage(message, isError = false) {
    litGrid.replaceChildren();
    const notice = document.createElement('div');
    notice.className = `col-span-full text-sm py-8 text-center ${isError ? 'text-red-600' : 'text-slate-500'}`;
    notice.textContent = message;
    litGrid.appendChild(notice);
  }

  // Load services on page load
  try {
    serviceSelect.disabled = true;
    const { data: services } = await window.medbridgeHttp.get('/api/location/services');
    services.forEach(s => {
      const option = document.createElement('option');
      option.value = s.id;
      option.textContent = `${s.name}${s.service_type ? ' (' + s.service_type + ')' : ''}`;
      serviceSelect.appendChild(option);
    });
    serviceSelect.disabled = false;
  } catch (e) {
    console.error('Error loading services:', e);
    showLitsMessage('Impossible de charger les services', true);
  }

  // Service change → Load UFs
  serviceSelect.addEventListener('change', async function() {
    const serviceId = this.value;
    ufSelect.disabled = true;
    ufSelect.innerHTML = '<option value="">-- Sélectionner une UF --</option>';
    showLitsMessage('Sélectionnez une UF');
    
    if (!serviceId) return;

    try {
      showLitsMessage('Chargement des UF...');
      const { data: ufs } = await window.medbridgeHttp.get(
        `/api/location/services/${serviceId}/ufs`,
      );
      ufs.forEach(uf => {
        const option = document.createElement('option');
        option.value = uf.id;
        option.textContent = uf.name;
        ufSelect.appendChild(option);
      });
      ufSelect.disabled = false;
      showLitsMessage('Sélectionnez une UF');
    } catch (e) {
      console.error('Error loading UFs:', e);
      showLitsMessage('Erreur lors du chargement des UF', true);
    }
  });

  // UF change → Load Lits directly
  ufSelect.addEventListener('change', async function() {
    const ufId = this.value;
    if (!ufId) {
      showLitsMessage('Sélectionnez une UF');
      document.getElementById('lit-container').style.display = 'none';
      return;
    }

    try {
      showLitsMessage('Chargement des lits disponibles...');
      const { data: allLits } = await window.medbridgeHttp.get(
        `/api/location/ufs/${ufId}/available-lits`,
      );

      // Render lits grid
      if (allLits.length === 0) {
        showLitsMessage('❌ Aucun lit disponible', true);
        document.getElementById('lit-container').style.display = 'none';
      } else {
        litGrid.innerHTML = '';
        allLits.forEach(lit => {
          const btn = document.createElement('button');
          btn.type = 'button';
          btn.className = 'lit-button p-3 border-2 border-green-300 bg-green-50 rounded-lg hover:bg-green-100 hover:border-green-600 transition-all cursor-pointer text-center text-sm';
          btn.dataset.litId = lit.id;
          const name = document.createElement('div');
          name.className = 'font-bold text-green-700';
          name.textContent = lit.name;
          const room = document.createElement('div');
          room.className = 'text-xs text-green-600';
          room.textContent = `Ch. ${lit.chambre.name}`;
          btn.append(name, room);
          btn.addEventListener('click', function(e) {
            e.preventDefault();
            selectLit(this, lit, ufId);
          });
          litGrid.appendChild(btn);
        });
        document.getElementById('lit-container').style.display = 'block';
      }
    } catch (e) {
      console.error('Error loading lits:', e);
      showLitsMessage('Erreur lors du chargement des lits', true);
    }
  });

  function selectLit(element, lit, ufId) {
    // Update selection UI
    document.querySelectorAll('.lit-button').forEach(b => {
      b.classList.remove('ring-2', 'ring-blue-500', 'bg-blue-50', 'border-blue-600');
      b.classList.add('border-green-300', 'bg-green-50');
    });
    element.classList.add('ring-2', 'ring-blue-500', 'bg-blue-50', 'border-blue-600');
    element.classList.remove('border-green-300', 'bg-green-50');
    
    // Set hidden input
    litInput.value = lit.id;
    
    // Update breadcrumb
    const hierarchy = document.createElement('span');
    hierarchy.className = 'inline-flex items-center gap-2 px-3 py-1 bg-white rounded border border-blue-200';
    hierarchy.textContent = `${lit.chambre.name} / ${lit.name}`;
    breadcrumb.replaceChildren(hierarchy);
    
    // Validate state (placeholder for real state validation logic)
    validateLitState(lit, ufId);
  }

  function validateLitState(lit, ufId) {
    // Placeholder: In production, this would check:
    // - Can patient be moved to this lit given current venue status?
    // - Are there any conflicting movements?
    // - Is the lit currently occupied?
    
    stateAlert.classList.add('hidden');
    
    // Example: If lit is in ICU, show warning
    if (lit.bed_type === 'ICU' || lit.name.includes('ICU')) {
      stateMessage.textContent = 'Ce lit est en unité de soins intensifs. Assurez-vous que le patient nécessite ce niveau de soins.';
      stateAlert.classList.remove('hidden');
    }
  }
});
