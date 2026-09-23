// Modal d'affectation
function assignBed(litId, litName) {
  document.getElementById('modal-lit-id').value = litId;
  document.getElementById('modal-lit-name').textContent = litName;
  document.getElementById('assign-modal').classList.remove('hidden');
  document.getElementById('patient-search').focus();
}

function closeAssignModal() {
  document.getElementById('assign-modal').classList.add('hidden');
  document.getElementById('patient-search').value = '';
  document.getElementById('search-results').classList.add('hidden');
  document.getElementById('search-results').innerHTML = '';
}

// Recherche patient (autocomplete via API)
let searchTimeout;
const searchInput = document.getElementById('patient-search');
const searchResults = document.getElementById('search-results');
const confirmAssignBtn = document.getElementById('confirm-assign');
const assignForm = document.getElementById('assign-form');
const selectedPatientIdInput = document.getElementById('selected-patient-id');
confirmAssignBtn.disabled = true;
selectedPatientIdInput.value = '';

searchInput.addEventListener('input', (e) => {
  clearTimeout(searchTimeout);
  const query = e.target.value.trim();
  if (query.length < 2) {
    searchResults.classList.add('hidden');
    searchResults.innerHTML = '';
    confirmAssignBtn.disabled = true;
    selectedPatientIdInput.value = '';
    return;
  }
  searchTimeout = setTimeout(async () => {
    searchResults.innerHTML = `<div class=\"text-sm text-slate-500 p-3\">🔍 Recherche en cours...</div>`;
    searchResults.classList.remove('hidden');
    try {
      const { data } = await window.medbridgeHttp.get(
        `/mouvements/api/plan-lits/patient-search?q=${encodeURIComponent(query)}`,
      );
      if (data.results && data.results.length > 0) {
        searchResults.innerHTML = data.results.map(p => `
          <div class=\"p-2 hover:bg-emerald-50 rounded cursor-pointer patient-result\" data-patient-id=\"${p.id}\" data-patient-name=\"${p.family} ${p.given || ''}\">
            <div class=\"font-semibold\">${p.family} <span class=\"text-slate-700\">${p.given || ''}</span></div>
            <div class=\"text-xs text-slate-500\">${p.identifier ? 'IPP: ' + p.identifier + ' · ' : ''}${p.birth_date || ''}${p.gender ? ' · ' + p.gender : ''}</div>
          </div>
        `).join('');
        // Add click event listeners to patient results
        document.querySelectorAll('.patient-result').forEach(el => {
          el.addEventListener('click', () => {
            // Highlight selected
            document.querySelectorAll('.patient-result').forEach(r => r.classList.remove('bg-emerald-100'));
            el.classList.add('bg-emerald-100');
            // Store selected patient id in hidden input
            selectedPatientIdInput.value = el.dataset.patientId;
            // Enable confirm button
            confirmAssignBtn.disabled = false;
          });
        });
      } else {
        searchResults.innerHTML = `<div class=\"text-sm text-slate-500 p-3\">Aucun patient trouvé</div>`;
        confirmAssignBtn.disabled = true;
        selectedPatientIdInput.value = '';
      }
    } catch (err) {
      searchResults.innerHTML = `<div class=\"text-sm text-red-500 p-3\">Erreur lors de la recherche</div>`;
      confirmAssignBtn.disabled = true;
      selectedPatientIdInput.value = '';
    }
  }, 300);
});

function showPlanLitsNotification(message, type = 'info') {
  if (window.toastSystem?.show) {
    window.toastSystem.show(message, type);
  } else {
    console.info(message);
  }
}

async function confirmPlanLitsAction(message, acceptLabel = 'Confirmer') {
  if (!window.PameliaUi?.confirm) {
    showPlanLitsNotification("Le dialogue de confirmation n'est pas disponible.", 'error');
    return false;
  }
  return window.PameliaUi.confirm({
    title: 'Confirmer le transfert',
    message,
    acceptLabel,
    variant: 'primary',
  });
}

// Mutation rapide (transfert)
async function transferPatient(venueId, newLitId) {
  if (await confirmPlanLitsAction('Créer un mouvement de transfert vers ce lit ?', 'Créer le mouvement')) {
    window.location.href = `/workflow/${venueId}/view?prefill_lit=${newLitId}`;
  }
}

// Fermer modal avec Escape
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    closeAssignModal();
  }
  
  // Ctrl+F pour focus barre de recherche filtres
  if ((e.ctrlKey || e.metaKey) && e.key === 'f' && !e.target.matches('input, textarea, select')) {
    e.preventDefault();
    const firstFilter = document.querySelector('select[name="uf_filter"]');
    if (firstFilter) {
      firstFilter.focus();
      firstFilter.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }
});

// Drag & drop de mutation de lit
let draggedVenueId = null;
let draggedPatientName = null;

function initDragAndDropMutations() {
  const occupants = document.querySelectorAll('.occupant-draggable');
  occupants.forEach((el) => {
    el.addEventListener('dragstart', (e) => {
      draggedVenueId = el.dataset.venueId;
      draggedPatientName = el.dataset.patientName || '';
      e.dataTransfer.effectAllowed = 'move';
      e.dataTransfer.setData('text/plain', draggedVenueId);
      document.body.classList.add('dragging-patient');
    });
    el.addEventListener('dragend', () => {
      draggedVenueId = null;
      draggedPatientName = null;
      document.body.classList.remove('dragging-patient');
      document.querySelectorAll('.bed-card-drop-target').forEach((card) => {
        card.classList.remove('ring-4', 'ring-amber-400', 'ring-offset-2');
      });
    });
  });

  const bedCards = document.querySelectorAll('.bed-card-drop-target');
  bedCards.forEach((card) => {
    card.addEventListener('dragover', (e) => {
      if (!draggedVenueId) {
        return;
      }
      const status = card.dataset.status;
      const hasConflict = card.dataset.hasConflict === 'true';
      if (status !== 'free' || hasConflict) {
        return;
      }
      e.preventDefault();
      e.dataTransfer.dropEffect = 'move';
      card.classList.add('ring-4', 'ring-amber-400', 'ring-offset-2');
    });

    card.addEventListener('dragleave', () => {
      card.classList.remove('ring-4', 'ring-amber-400', 'ring-offset-2');
    });

    card.addEventListener('drop', async (e) => {
      e.preventDefault();
      card.classList.remove('ring-4', 'ring-amber-400', 'ring-offset-2');
      if (!draggedVenueId) {
        return;
      }
      const status = card.dataset.status;
      const hasConflict = card.dataset.hasConflict === 'true';
      if (status !== 'free' || hasConflict) {
        showPlanLitsNotification("La mutation par glisser-déposer n'est possible que vers un lit libre sans conflit.", 'warning');
        return;
      }
      const targetLitId = card.dataset.litId;
      const litName = card.dataset.litName;
      if (!targetLitId || !litName) {
        return;
      }
      const message = draggedPatientName
        ? `Muter ${draggedPatientName} vers le lit ${litName} ?`
        : `Créer un mouvement de transfert vers le lit ${litName} ?`;
      if (!await confirmPlanLitsAction(message, 'Muter')) {
        return;
      }
      executeDragDropMutation(draggedVenueId, targetLitId, litName);
    });
  });
}

async function executeDragDropMutation(venueId, targetLitId, litName) {
  const params = new URLSearchParams();
  params.append('event_code', 'A02');
  params.append('location', litName);
  params.append('lit_id', targetLitId);
  params.append('reason', 'Mutation via plan de lits (drag&drop)');

  try {
    await window.medbridgeHttp.request(`/workflow/${venueId}/mouvement`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
        'X-Requested-With': 'XMLHttpRequest',
      },
      body: params.toString(),
    });

    // Recharger le plan de lits pour refléter le nouveau placement
    window.location.reload();
  } catch (error) {
    console.error(error);
    showPlanLitsNotification(
      error.data?.detail || error.message || "Erreur réseau lors de la mutation.",
      'error',
    );
  }
}

document.addEventListener('DOMContentLoaded', initDragAndDropMutations);


document.addEventListener('click', (event) => {
  const actionButton = event.target.closest('[data-plan-lits-action]');
  const action = actionButton?.dataset.planLitsAction;

  if (action === 'assign') {
    assignBed(actionButton.dataset.litId, actionButton.dataset.litName);
  } else if (action === 'transfer') {
    transferPatient(actionButton.dataset.venueId, actionButton.dataset.litId);
  } else if (action === 'close-assignment') {
    closeAssignModal();
  }
});
