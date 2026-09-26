// Variable globale pour stocker le fichier
let uploadedFile = null;

function showStructureImportNotification(message, type = 'info') {
  if (window.toastSystem?.show) {
    window.toastSystem.show(message, type);
    return;
  }
  console.info(message);
}

// Configuration Dropzone
Dropzone.options.fileDropzone = {
  url: "/api/structure/import/excel",
  maxFiles: 1,
  maxFilesize: 10,
  acceptedFiles: ".xlsx,.xls",
  addRemoveLinks: true,
  dictDefaultMessage: "",
  
  init: function() {
    this.on("success", function(file, response) {
      console.log("Upload success:", response);
      uploadedFile = file; // Stocker pour la confirmation
      showPreview(response);
    });
    
    this.on("error", function(file, errorMessage) {
      console.error("Upload error:", errorMessage);
      const msg = typeof errorMessage === 'object' ? errorMessage.detail || JSON.stringify(errorMessage) : errorMessage;
      showStructureImportNotification("Erreur lors de l’upload : " + msg, 'error');
    });
  },
  
  sending: function(file, xhr, formData) {
    // Ajouter le mode d'import
    const mode = document.querySelector('input[name="import_mode"]:checked').value;
    formData.append("mode", mode);
  }
};

// Afficher la prévisualisation
function escapeHtml(value) {
  const node = document.createElement('span');
  node.textContent = String(value ?? '');
  return node.innerHTML;
}

function showPreview(data) {
  document.getElementById('previewSection').classList.remove('hidden');
  
  // Statistiques
  const stats = `${data.to_create?.length || 0} à créer, ${data.to_update?.length || 0} à modifier, ${data.errors?.length || 0} erreurs`;
  document.getElementById('previewStats').textContent = stats;
  
  // Remplir le tableau
  const tbody = document.getElementById('previewTableBody');
  tbody.innerHTML = '';
  
  // Éléments à créer
  (data.to_create || []).forEach(item => {
    const row = createPreviewRow(item, 'create', '✅ Créer', 'text-green-600');
    tbody.appendChild(row);
  });
  
  // Éléments à modifier
  (data.to_update || []).forEach(item => {
    const row = createPreviewRow(item, 'update', '🔄 Modifier', 'text-blue-600');
    tbody.appendChild(row);
  });
  
  // Erreurs
  (data.errors || []).forEach(item => {
    const row = createPreviewRow(item, 'error', '❌ Erreur', 'text-red-600');
    tbody.appendChild(row);
  });
  
  // Alertes
  const alertsSection = document.getElementById('alertsSection');
  const confirmBtn = document.getElementById('confirmImportBtn');
  
  if (data.errors && data.errors.length > 0) {
    alertsSection.innerHTML = `
      <div class="bg-red-50 border border-red-200 rounded-lg p-4">
        <div class="font-semibold text-red-900 mb-2">❌ ${data.errors.length} erreur(s) détectée(s)</div>
        <ul class="text-sm text-red-700 space-y-1">
          ${data.errors.slice(0, 5).map(e => `<li>• ${escapeHtml(e.message || e)}</li>`).join('')}
          ${data.errors.length > 5 ? `<li>• ... et ${data.errors.length - 5} autres</li>` : ''}
        </ul>
      </div>
    `;
    confirmBtn.disabled = true;
    confirmBtn.classList.add('opacity-50', 'cursor-not-allowed');
  } else if (data.warnings && data.warnings.length > 0) {
    alertsSection.innerHTML = `
      <div class="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
        <div class="font-semibold text-yellow-900 mb-2">⚠️ ${data.warnings.length} avertissement(s)</div>
        <ul class="text-sm text-yellow-700 space-y-1">
          ${data.warnings.slice(0, 5).map(w => `<li>• ${escapeHtml(w.message || w)}</li>`).join('')}
          ${data.warnings.length > 5 ? `<li>• ... et ${data.warnings.length - 5} autres</li>` : ''}
        </ul>
      </div>
    `;
    confirmBtn.disabled = false;
    confirmBtn.classList.remove('opacity-50', 'cursor-not-allowed');
  } else {
    alertsSection.innerHTML = `
      <div class="bg-green-50 border border-green-200 rounded-lg p-4">
        <div class="font-semibold text-green-900">✅ Aucune erreur détectée - Prêt à importer</div>
      </div>
    `;
    confirmBtn.disabled = false;
    confirmBtn.classList.remove('opacity-50', 'cursor-not-allowed');
  }
}

function createPreviewRow(item, type, actionText, actionClass) {
  const row = document.createElement('tr');
  row.className = 'border-t hover:bg-slate-50';
  row.innerHTML = `
    <td class="px-4 py-3">${getTypeIcon(item.entity_type)} ${escapeHtml(item.entity_type || 'N/A')}</td>
    <td class="px-4 py-3 font-mono text-sm">${escapeHtml(item.code || item.entity_code || 'N/A')}</td>
    <td class="px-4 py-3">${escapeHtml(item.nom || item.name || 'N/A')}</td>
    <td class="px-4 py-3 ${actionClass} font-medium">${actionText}</td>
    <td class="px-4 py-3 text-xs text-slate-500">${escapeHtml(item.message || '-')}</td>
  `;
  return row;
}

function getTypeIcon(type) {
  const icons = {
    'eg': '🏥',
    'pole': '🏢',
    'service': '🏛️',
    'uf': '🔹',
    'uh': '🏠',
    'chambre': '🚪',
    'lit': '🛏️'
  };
  return icons[type] || '📦';
}

function cancelImport() {
  document.getElementById('previewSection').classList.add('hidden');
  Dropzone.forElement("#fileDropzone").removeAllFiles();
  uploadedFile = null;
}

async function confirmImport() {
  if (!window.PameliaUi?.confirm) {
    showStructureImportNotification("Le dialogue de confirmation n'est pas disponible.", 'error');
    return;
  }
  const confirmed = await window.PameliaUi.confirm({
    title: 'Importer la structure',
    message: 'Cette opération peut créer ou modifier la structure en base. Continuer ?',
    acceptLabel: 'Importer',
    variant: 'primary',
  });
  if (!confirmed) {
    return;
  }
  
  if (!uploadedFile) {
    showStructureImportNotification('Aucun fichier sélectionné.', 'error');
    return;
  }
  
  const confirmBtn = document.getElementById('confirmImportBtn');
  const originalText = confirmBtn.innerHTML;
  
  try {
    // Afficher l'indicateur de chargement
    confirmBtn.disabled = true;
    confirmBtn.innerHTML = '⏳ Import en cours...';
    
    // Préparer les données
    const mode = document.querySelector('input[name="import_mode"]:checked').value;
    const formData = new FormData();
    formData.append('file', uploadedFile);
    formData.append('mode', mode);
    
    // Appeler l'endpoint de confirmation
    const { data: result } = await window.medbridgeHttp.request('/api/structure/import/confirm', {
      method: 'POST',
      body: formData
    });
    
    if (result.success) {
      // Succès
      showStructureImportNotification(
        `Import réussi : ${result.created_count} entité(s) créée(s), ${result.updated_count} modifiée(s) en ${result.duration_seconds}s.`,
        'success'
      );
      
      // Rediriger vers la page structure
      setTimeout(() => {
        window.location.href = '/structure';
      }, 700);
    } else {
      // Échec avec détails
      const errorMsg = result.messages?.filter(m => m.severity === 'error')
        .map(m => m.message)
        .join(' — ') || 'Import échoué';
      showStructureImportNotification(`Import échoué : ${errorMsg}`, 'error');
      confirmBtn.disabled = false;
      confirmBtn.innerHTML = originalText;
    }
    
  } catch (error) {
    console.error('Import error:', error);
    showStructureImportNotification('Erreur lors de l’import : ' + error.message, 'error');
    confirmBtn.disabled = false;
    confirmBtn.innerHTML = originalText;
  }
}


document.getElementById('cancelImportBtn')?.addEventListener('click', cancelImport);
document.getElementById('confirmImportBtn')?.addEventListener('click', confirmImport);
