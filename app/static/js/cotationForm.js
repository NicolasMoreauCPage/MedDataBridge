// cotationForm.js - gestion dynamique UX/UI pour hprim_cotation_modern.html
console.log('cotationForm.js loaded successfully');

let actes = [];
let acteEnEdition = null;
let selectedDossier = null;

// Base de données des actes médicaux (simplifiée pour démonstration)
const actesMedicaux = [
  // CCAM - Imagerie
  { code: 'HBMD001', libelle: 'Échographie abdominale', tarif: 25.50, lettreCle: 'Z', type: 'imagerie' },
  { code: 'HBMD002', libelle: 'Échographie pelvienne', tarif: 23.80, lettreCle: 'Z', type: 'imagerie' },
  { code: 'HBGD001', libelle: 'Radiographie thorax', tarif: 12.30, lettreCle: 'Z', type: 'imagerie' },
  { code: 'CAQH003', libelle: 'Coloscopie totale', tarif: 89.40, lettreCle: 'K', type: 'endoscopie' },
  { code: 'CAQH001', libelle: 'Gastroscopie', tarif: 45.20, lettreCle: 'K', type: 'endoscopie' },

  // CCAM - Chirurgie
  { code: 'AAFA001', libelle: 'Ablation de calcul vésical', tarif: 156.70, lettreCle: 'K', type: 'chirurgie' },
  { code: 'EBLA001', libelle: 'Biopsie de peau', tarif: 28.90, lettreCle: 'Z', type: 'chirurgie' },

  // NGAP - Consultations
  { code: 'C', libelle: 'Consultation générale', tarif: 25.00, lettreCle: 'K', type: 'consultation' },
  { code: 'CS', libelle: 'Consultation spécialisée', tarif: 28.00, lettreCle: 'K', type: 'consultation' },
  { code: 'V', libelle: 'Visite à domicile', tarif: 22.00, lettreCle: 'K', type: 'consultation' },
  { code: 'VN', libelle: 'Visite de nuit', tarif: 35.00, lettreCle: 'K', type: 'consultation' }
];

// Coefficients régionaux (simplifiés)
const coefficientsRegionaux = {
  'ile-de-france': 1.0,
  'provence-alpes-cote-d-azur': 0.95,
  'auvergne-rhone-alpes': 0.92,
  'default': 1.0
};

// Modificateurs et leurs effets sur le tarif
const modificateursTarif = {
  'A': { label: 'Anesthésie', multiplicateur: 1.5 },
  'B': { label: 'Bilateral', multiplicateur: 2.0 },
  'C': { label: 'Complexité', multiplicateur: 1.3 },
  'D': { label: 'Diminution', multiplicateur: 0.7 },
  'U': { label: 'Urgence', multiplicateur: 1.2 }
};

// Fonction pour détecter le type d'acte médical
function detectActeType(code) {
  if (!code) return 'unknown';

  // CCAM: Lettre majuscule + 3 chiffres (ex: HBMD001, CAQH003)
  if (/^[A-Z]\d{3}$/.test(code)) {
    return 'CCAM';
  }

  // NGAP: Lettre majuscule + chiffres, optionnellement avec point décimal (ex: C, CS, V, VN)
  if (/^[A-Z]\d*\.?\d*$/.test(code)) {
    return 'NGAP';
  }

  // UCD: Lettre + chiffres pour actes dentaires
  if (/^[A-Z]\d+$/.test(code) && code.length > 1) {
    return 'UCD';
  }

  // LPP: Autres formats
  return 'LPP';
}

// Fonction pour afficher des notifications toast
function showToast(message, type = 'info') {
  const toast = document.getElementById('toast');
  if (!toast) return;

  toast.textContent = message;
  toast.className = `toast ${type}`;
  toast.classList.remove('hidden');

  // Masquer automatiquement après 3 secondes
  setTimeout(() => {
    toast.classList.add('hidden');
  }, 3000);
}

// Initialisation au chargement de la page
document.addEventListener('DOMContentLoaded', function() {
  console.log('DOM loaded, initializing cotation form...');
  // Vérifier si un dossier_id est passé dans l'URL
  const urlParams = new URLSearchParams(window.location.search);
  const dossierId = urlParams.get('dossier_id');

  if (dossierId) {
    // Charger automatiquement le dossier spécifié
    loadDossierInfo(dossierId);
    // Sélectionner le dossier dans le select (sera mis à jour quand les options seront chargées)
    document.getElementById('dossierSelect').value = dossierId;
  }

  // Configuration des event listeners
  setupEventListeners();

  // Initialiser la recherche d'actes
  initializeActeSearch();
});

function initializeActeSearch() {
  const acteSearch = document.getElementById('acteSearch');
  const acteSuggestions = document.getElementById('acteSuggestions');

  if (acteSearch) {
    acteSearch.addEventListener('input', function(e) {
      const query = e.target.value.trim().toLowerCase();
      const code = extractCodeFromQuery(query);

      // Détection automatique du type d'acte
      if (code && code.length >= 1) {
        const detectedType = detectActeType(code);
        updateActeTypeDisplay(detectedType, code);
        validateActeCode(code, detectedType);
      } else {
        hideActeTypeDisplay();
      }

      if (query.length >= 2) {
        showActeSuggestions(query);
      } else {
        acteSuggestions.classList.add('hidden');
      }
    });

    acteSearch.addEventListener('focus', function() {
      if (this.value.trim().length >= 2) {
        showActeSuggestions(this.value.trim().toLowerCase());
      }
    });

    // Fermer les suggestions en cliquant ailleurs
    document.addEventListener('click', function(e) {
      if (!acteSearch.contains(e.target) && !acteSuggestions.contains(e.target)) {
        acteSuggestions.classList.add('hidden');
      }
    });
  }
}

function showActeSuggestions(query) {
  const acteSuggestions = document.getElementById('acteSuggestions');

  // Filtrer les actes correspondant à la recherche
  const suggestions = actesMedicaux.filter(acte =>
    acte.libelle.toLowerCase().includes(query) ||
    acte.code.toLowerCase().includes(query)
  ).slice(0, 8); // Limiter à 8 suggestions

  if (suggestions.length === 0) {
    acteSuggestions.classList.add('hidden');
    return;
  }

  // Générer le HTML des suggestions
  const suggestionsHtml = suggestions.map(acte => `
    <div class="p-3 hover:bg-blue-50 cursor-pointer border-b border-slate-100 last:border-b-0" onclick="selectActe('${acte.code}')">
      <div class="flex justify-between items-center">
        <div>
          <div class="font-mono font-bold text-blue-700">${acte.code}</div>
          <div class="text-sm text-slate-600">${acte.libelle}</div>
        </div>
        <div class="text-right">
          <div class="font-bold text-green-600">${acte.tarif} €</div>
          <div class="text-xs text-slate-500">${acte.type}</div>
        </div>
      </div>
    </div>
  `).join('');

  acteSuggestions.innerHTML = suggestionsHtml;
  acteSuggestions.classList.remove('hidden');
}

function selectActe(code) {
  const acte = actesMedicaux.find(a => a.code === code);
  if (!acte) return;

  // Masquer les suggestions
  document.getElementById('acteSuggestions').classList.add('hidden');

  // Remplir les champs du formulaire
  document.getElementById('acteSearch').value = `${acte.code} - ${acte.libelle}`;
  document.getElementById('codeActe').value = acte.code;
  document.getElementById('libelleActe').value = acte.libelle;

  // Détecter automatiquement le type d'acte au lieu d'utiliser acte.type
  const detectedType = detectActeType(acte.code);
  updateActeTypeDisplay(detectedType, acte.code);
  validateActeCode(acte.code, detectedType);

  // Afficher les détails de l'acte
  showActeDetails(acte);

  // Calculer le tarif
  calculateTarif(acte);
}

function showActeDetails(acte) {
  const acteDetails = document.getElementById('acteDetails');
  document.getElementById('selectedCode').textContent = acte.code;
  document.getElementById('selectedLibelle').textContent = acte.libelle;
  document.getElementById('selectedTarif').textContent = `${acte.tarif} €`;
  document.getElementById('selectedCoeff').textContent = acte.lettreCle;
  acteDetails.classList.remove('hidden');
}

function calculateTarif(acte) {
  const quantite = parseInt(document.getElementById('quantite').value) || 1;
  const modificateurs = getSelectedModificateurs();

  // Détecter le type d'acte
  const acteType = detectActeType(acte.code);

  // Tarif de base
  let tarifBase = acte.tarif * quantite;

  // Appliquer le coefficient pour les actes NGAP
  if (acteType === 'NGAP') {
    const coefficient = parseFloat(document.getElementById('coefficientNGAP').value) || 1.0;
    tarifBase *= coefficient;
  }

  // Calcul des modificateurs
  let multiplicateurTotal = 1;
  modificateurs.forEach(mod => {
    if (modificateursTarif[mod]) {
      multiplicateurTotal *= modificateursTarif[mod].multiplicateur;
    }
  });

  const tarifModificateurs = (tarifBase * multiplicateurTotal) - tarifBase;
  const tarifTotal = tarifBase * multiplicateurTotal;

  // Afficher les résultats
  const tarifCalculation = document.getElementById('tarifCalculation');
  document.getElementById('tarifBase').textContent = `${tarifBase.toFixed(2)} €`;
  document.getElementById('tarifModificateurs').textContent = `+${tarifModificateurs.toFixed(2)} €`;
  document.getElementById('tarifTotal').textContent = `${tarifTotal.toFixed(2)} €`;
  tarifCalculation.classList.remove('hidden');
}

function getSelectedModificateurs() {
  const modificateurs = [];
  ['modA', 'modB', 'modC', 'modD', 'modU'].forEach(id => {
    const checkbox = document.getElementById(id);
    if (checkbox && checkbox.checked) {
      modificateurs.push(checkbox.value);
    }
  });
  return modificateurs;
}

function updateModificateursDisplay() {
  const modificateurs = getSelectedModificateurs();
  const display = document.getElementById('modificateursActifs');

  if (modificateurs.length === 0) {
    display.textContent = 'Aucun';
  } else {
    const labels = modificateurs.map(mod => modificateursTarif[mod]?.label || mod).join(', ');
    display.textContent = labels;
  }

  // Recalculer le tarif si un acte est sélectionné
  const codeActe = document.getElementById('codeActe').value;
  if (codeActe) {
    const acte = actesMedicaux.find(a => a.code === codeActe);
    if (acte) {
      calculateTarif(acte);
    }
  }
}

function setupEventListeners() {
  console.log('Setting up event listeners...');

  // Recherche de dossiers
  const dossierSearch = document.getElementById('dossierSearch');
  if (dossierSearch) {
    dossierSearch.addEventListener('input', function(e) {
      searchDossiers(e.target.value);
    });
  }

  // Changement de dossier sélectionné
  const dossierSelect = document.getElementById('dossierSelect');
  if (dossierSelect) {
    dossierSelect.addEventListener('change', function(e) {
      loadDossierInfo(e.target.value);
    });
  }

  // Soumission du formulaire d'acte
  const acteForm = document.getElementById('acteForm');
  if (acteForm) {
    acteForm.addEventListener('submit', function(e) {
      e.preventDefault();
      saveActe();
    });
  }
  const ajouterActeBtn = document.getElementById('ajouterActeBtn');
  console.log('ajouterActeBtn element:', ajouterActeBtn);
  if (ajouterActeBtn) {
    ajouterActeBtn.addEventListener('click', (e) => {
      console.log('Ajouter acte button clicked');

      showModal();
    });
  } else {
    console.error('ajouterActeBtn not found!');
  }

  const annulerActeBtn = document.getElementById('annulerActeBtn');
  if (annulerActeBtn) {
    annulerActeBtn.addEventListener('click', hideModal);
  }

  // Bouton de fermeture de la modal (X)
  const closeModalBtn = document.getElementById('closeModalBtn');
  if (closeModalBtn) {
    closeModalBtn.addEventListener('click', hideModal);
  }

  // Event listeners pour les modificateurs
  ['modA', 'modB', 'modC', 'modD', 'modU'].forEach(id => {
    const checkbox = document.getElementById(id);
    if (checkbox) {
      checkbox.addEventListener('change', updateModificateursDisplay);
    }
  });

  // Event listener pour le coefficient NGAP
  const coefficientNGAP = document.getElementById('coefficientNGAP');
  if (coefficientNGAP) {
    coefficientNGAP.addEventListener('input', function() {
      const codeActe = document.getElementById('codeActe').value;
      if (codeActe) {
        const acte = actesMedicaux.find(a => a.code === codeActe);
        if (acte) {
          calculateTarif(acte);
        }
      }
    });
  }

  // Event listener pour la quantité
  const quantiteInput = document.getElementById('quantite');
  if (quantiteInput) {
    quantiteInput.addEventListener('input', function() {
      const codeActe = document.getElementById('codeActe').value;
      if (codeActe) {
        const acte = actesMedicaux.find(a => a.code === codeActe);
        if (acte) {
          calculateTarif(acte);
        }
      }
    });
  }

  // Recherche d'actes médicaux
  const acteSearch = document.getElementById('acteSearch');
  if (acteSearch) {
    acteSearch.addEventListener('input', function(e) {
      showActeSuggestions(e.target.value);
    });
  }

  // Clic en dehors des suggestions pour les masquer
  document.addEventListener('click', function(e) {
    const acteSearch = document.getElementById('acteSearch');
    const acteSuggestions = document.getElementById('acteSuggestions');
    if (acteSearch && acteSuggestions && !acteSearch.contains(e.target) && !acteSuggestions.contains(e.target)) {
      acteSuggestions.classList.add('hidden');
    }
  });

  // Bouton reset
  const resetBtn = document.getElementById('resetBtn');
  if (resetBtn) {
    resetBtn.addEventListener('click', () => {
      if (confirm('Réinitialiser le formulaire et les actes ?')) {
        actes = [];
        renderActes();
        document.getElementById('cotationForm').reset();
        document.getElementById('xmlPreview').textContent = 'XML généré apparaîtra ici…';
      }
    });
  }

  console.log('Event listeners setup complete');
}

// Gestion des dossiers
async function searchDossiers(query) {
  if (!query || query.length < 2) return;

  try {
    const response = await fetch(`/dossiers/api/search?q=${encodeURIComponent(query)}`);
    if (!response.ok) throw new Error('Erreur de recherche');

    const dossiers = await response.json();
    updateDossierSelect(dossiers);
  } catch (error) {
    console.error('Erreur recherche dossiers:', error);
    showToast('Erreur lors de la recherche de dossiers', true);
  }
}

function updateDossierSelect(dossiers) {
  const select = document.getElementById('dossierSelect');
  select.innerHTML = '<option value="">-- Sélectionnez un dossier --</option>';

  dossiers.forEach(dossier => {
    const option = document.createElement('option');
    option.value = dossier.id;
    option.textContent = `Dossier ${dossier.dossier_seq} - ${dossier.patient.family} ${dossier.patient.given || ''}`;
    select.appendChild(option);
  });
}

async function loadDossierInfo(dossierId) {
  if (!dossierId) {
    document.getElementById('dossierInfo').classList.add('hidden');
    selectedDossier = null;
    return;
  }

  try {
    const response = await fetch(`/dossiers/api/${dossierId}`);
    if (!response.ok) throw new Error('Erreur chargement dossier');

    const dossier = await response.json();
    selectedDossier = dossier;
    displayDossierInfo(dossier);
  } catch (error) {
    console.error('Erreur chargement dossier:', error);
    showToast('Erreur lors du chargement du dossier', true);
  }
}

function displayDossierInfo(dossier) {
  const infoDiv = document.getElementById('dossierInfo');
  document.getElementById('dossierPatient').textContent = `${dossier.patient.family} ${dossier.patient.given || ''}`;
  document.getElementById('dossierAdmission').textContent = new Date(dossier.admit_time).toLocaleDateString('fr-FR');
  document.getElementById('dossierMedecin').textContent = dossier.medecin_responsable ?
    `${dossier.medecin_responsable.nom} ${dossier.medecin_responsable.prenom || ''}` : 'Non défini';
  document.getElementById('dossierEtat').textContent = dossier.current_state || 'Actif';

  infoDiv.classList.remove('hidden');
}

function updateResume() {
  document.getElementById('nbActes').textContent = actes.length;
  const total = actes.reduce((sum, a) => sum + (a.montant || 0) * (a.quantite || 1), 0);
  document.getElementById('montantTotal').textContent = total.toLocaleString('fr-FR', {minimumFractionDigits: 2, maximumFractionDigits: 2}) + ' €';
}

function renderActes() {
  const list = document.getElementById('actesList');
  list.innerHTML = '';

  if (actes.length === 0) {
    list.innerHTML = `
      <div class="text-center py-8 text-slate-500">
        <i class="fas fa-plus-circle text-4xl mb-4 text-slate-300"></i>
        <p>Aucun acte ajouté pour le moment</p>
        <p class="text-sm">Cliquez sur "Ajouter un acte" pour commencer</p>
      </div>
    `;
    updateResume();
    return;
  }

  actes.forEach((a, i) => {
    const card = document.createElement('div');
    card.className = 'card acte-card p-4 rounded-xl shadow-md border border-slate-200 bg-white hover:shadow-lg transition-shadow';

    // Formatage de la date
    const dateFormatted = a.dateActe ? new Date(a.dateActe).toLocaleDateString('fr-FR') : '';

    // Badge d'urgence
    const urgenceBadge = a.urgence === 'urgent' ? '<span class="badge badge-warning">Urgent</span>' :
                        a.urgence === 'tres-urgent' ? '<span class="badge badge-error">Très urgent</span>' : '';

    card.innerHTML = `
      <div class="flex items-start justify-between mb-3">
        <div class="flex-1">
          <div class="flex items-center gap-2 mb-1">
            <span class="font-bold text-lg text-indigo-700">${a.code}</span>
            ${urgenceBadge}
            <span class="text-xs text-slate-500">${dateFormatted}</span>
          </div>
          <div class="text-sm text-slate-700 font-medium">${a.libelleActe || 'Acte médical'}</div>
        </div>
        <div class="flex gap-1 ml-4">
          <button class="btn-icon hover:bg-blue-50 p-2 rounded" aria-label="Éditer" onclick="editActe(${i})">
            <i class="fas fa-edit text-blue-600"></i>
          </button>
          <button class="btn-icon hover:bg-red-50 p-2 rounded" aria-label="Supprimer" onclick="deleteActe(${i})">
            <i class="fas fa-trash text-red-600"></i>
          </button>
        </div>
      </div>

      <div class="grid grid-cols-2 gap-4 mb-3 text-sm">
        <div>
          <span class="text-slate-600">Type:</span>
          <span class="font-medium ml-1">${a.typeActe ? a.typeActe.charAt(0).toUpperCase() + a.typeActe.slice(1) : 'Non spécifié'}</span>
        </div>
        <div>
          <span class="text-slate-600">Exécutant:</span>
          <span class="font-medium ml-1">${a.executant || 'Non spécifié'}</span>
        </div>
        <div>
          <span class="text-slate-600">Lieu:</span>
          <span class="font-medium ml-1">${a.lieuRealisation ? a.lieuRealisation.charAt(0).toUpperCase() + a.lieuRealisation.slice(1) : 'Non spécifié'}</span>
        </div>
        <div>
          <span class="text-slate-600">Durée:</span>
          <span class="font-medium ml-1">${a.dureeEstimee ? a.dureeEstimee + ' min' : 'Non spécifiée'}</span>
        </div>
      </div>

      <div class="flex flex-wrap gap-2 mb-3">
        <span class="badge badge-info">${a.quantite || 1}x</span>
        ${a.montant ? `<span class="badge badge-success">${a.montant} €</span>` : ''}
        ${(a.modificateurs || []).map(m => `<span class="badge">${m}</span>`).join('')}
      </div>

      ${a.diagnostic ? `<div class="text-sm text-slate-600 mb-2"><span class="font-medium">Diagnostic:</span> ${a.diagnostic}</div>` : ''}
      ${a.motif ? `<div class="text-sm text-slate-600 mb-2"><span class="font-medium">Motif:</span> ${a.motif}</div>` : ''}
      ${a.commentaire ? `<div class="text-sm text-slate-600"><span class="font-medium">Note:</span> ${a.commentaire}</div>` : ''}
    `;

    list.appendChild(card);
  });

  updateResume();
}

function updateResume() {
  const totalActes = actes.length;
  const totalMontant = actes.reduce((sum, acte) => sum + (acte.montant || 0), 0);
  
  document.getElementById('totalActes').textContent = totalActes;
  document.getElementById('totalTarif').textContent = totalMontant.toFixed(2) + ' €';
  
  // Afficher/masquer le résumé
  const resumeSection = document.getElementById('resumeSection');
  if (totalActes > 0) {
    resumeSection.classList.remove('hidden');
  } else {
    resumeSection.classList.add('hidden');
  }
}

function showModal(editIdx = null) {
  console.log('showModal called with editIdx:', editIdx);
  acteEnEdition = editIdx;
  const modal = document.getElementById('modalBg');
  console.log('modal element:', modal);
  if (modal) {
    modal.classList.remove('hidden');
    console.log('Modal should now be visible');
  } else {
    console.error('Modal element not found!');
  }

  if (editIdx !== null) {
    const a = actes[editIdx];
    // Informations générales
    document.getElementById('codeActe').value = a.code || '';
    document.getElementById('libelleActe').value = a.libelleActe || '';
    document.getElementById('typeActe').value = a.typeActe || '';
    document.getElementById('urgence').value = a.urgence || 'normal';

    // Date et heure
    document.getElementById('dateActe').value = a.dateActe || '';
    document.getElementById('heureDebut').value = a.heureDebut || '';
    document.getElementById('dureeEstimee').value = a.dureeEstimee || '';

    // Professionnels de santé
    document.getElementById('prescripteur').value = a.prescripteur || '';
    document.getElementById('executant').value = a.executant || '';
    document.getElementById('specialite').value = a.specialite || '';
    document.getElementById('lieuRealisation').value = a.lieuRealisation || '';

    // Aspects techniques et financiers
    document.getElementById('quantite').value = a.quantite || 1;

    // Cocher les modificateurs
    ['modA', 'modB', 'modC', 'modD', 'modU'].forEach(id => {
      const checkbox = document.getElementById(id);
      if (checkbox) {
        checkbox.checked = (a.modificateurs || []).includes(checkbox.value);
      }
    });

    // Mettre à jour l'affichage des modificateurs
    updateModificateursDisplay();

    // Diagnostic et contexte médical
    document.getElementById('diagnostic').value = a.diagnostic || '';
    document.getElementById('motif').value = a.motif || '';
    document.getElementById('materiel').value = a.materiel || '';

    // Commentaires
    document.getElementById('commentaire').value = a.commentaire || '';

    // Si c'est un acte existant, afficher les détails et calculer le tarif
    if (a.code) {
      const acteBase = actesMedicaux.find(act => act.code === a.code);
      if (acteBase) {
        showActeDetails(acteBase);
        calculateTarif(acteBase);
      }
    }
  } else {
    // Réinitialiser le formulaire pour un nouvel acte
    document.getElementById('acteForm').reset();
    // Valeurs par défaut
    document.getElementById('urgence').value = 'normal';
    document.getElementById('quantite').value = 1;
    // Date par défaut : aujourd'hui
    const today = new Date().toISOString().split('T')[0];
    document.getElementById('dateActe').value = today;
    
    // Réinitialiser la recherche d'acte
    document.getElementById('acteSearch').value = '';
    document.getElementById('acteSuggestions').innerHTML = '';
    document.getElementById('acteSuggestions').classList.add('hidden');
    
    // Masquer les détails d'acte
    document.getElementById('acteDetails').classList.add('hidden');
    
    // Réinitialiser l'affichage du tarif
    document.getElementById('tarifDisplay').classList.add('hidden');
    document.getElementById('totalTarif').textContent = '0.00 €';
  }
}

// Rendre les fonctions globales pour l'accès depuis HTML
window.showModal = showModal;
window.hideModal = hideModal;
window.editActe = editActe;
window.deleteActe = deleteActe;

function hideModal() {
  document.getElementById('modalBg').classList.add('hidden');
  acteEnEdition = null;
}

function saveActe(e) {
  e.preventDefault();

  // Récupération des données du formulaire
  const code = document.getElementById('codeActe').value.trim();
  const libelleActe = document.getElementById('libelleActe').value.trim();

  // Détection automatique du type d'acte
  const typeActe = detectActeType(code);

  const urgence = document.getElementById('urgence').value;

  // Date et heure
  const dateActe = document.getElementById('dateActe').value;
  const heureDebut = document.getElementById('heureDebut').value;
  const dureeEstimee = parseInt(document.getElementById('dureeEstimee').value) || 0;

  // Professionnels de santé
  const prescripteur = document.getElementById('prescripteur').value.trim();
  const executant = document.getElementById('executant').value.trim();
  const specialite = document.getElementById('specialite').value;
  const lieuRealisation = document.getElementById('lieuRealisation').value;

  // Aspects techniques et financiers
  const quantite = parseInt(document.getElementById('quantite').value) || 1;
  const modificateurs = getSelectedModificateurs();

  // Calcul automatique du montant
  const acteBase = actesMedicaux.find(a => a.code === code);
  let montant = 0;
  if (acteBase) {
    montant = acteBase.tarif * quantite;
    // Appliquer les modificateurs
    modificateurs.forEach(mod => {
      if (modificateursTarif[mod]) {
        montant *= modificateursTarif[mod].multiplicateur;
      }
    });
  }

  // Diagnostic et contexte médical
  const diagnostic = document.getElementById('diagnostic').value.trim();
  const motif = document.getElementById('motif').value.trim();
  const materiel = document.getElementById('materiel').value.trim();

  // Commentaires
  const commentaire = document.getElementById('commentaire').value.trim();

  // Validation des champs requis
  if (!code) {
    showToast('Le code CCAM/NGAP est requis', true);
    return;
  }
  if (!dateActe) {
    showToast('La date de l\'acte est requise', true);
    return;
  }
  if (!executant) {
    showToast('L\'exécutant est requis', true);
    return;
  }

  // Récupération des champs spécifiques selon le type d'acte
  const acteSpecificFields = getActeSpecificFields(typeActe);

  // Création de l'objet acte avec tous les champs
  const acte = {
    code,
    libelleActe,
    typeActe,
    urgence,
    dateActe,
    heureDebut,
    dureeEstimee,
    prescripteur,
    executant,
    specialite,
    lieuRealisation,
    quantite,
    montant: parseFloat(montant.toFixed(2)),
    modificateurs,
    diagnostic,
    motif,
    materiel,
    commentaire,
    dateCreation: new Date().toISOString(),
    ...acteSpecificFields
  };

  // Sauvegarde de l'acte
  if (acteEnEdition !== null) {
    actes[acteEnEdition] = acte;
    showToast('Acte modifié avec succès');
  } else {
    actes.push(acte);
    showToast('Acte ajouté avec succès');
  }

  hideModal();
  renderActes();
}

function editActe(i) { showModal(i); }
function deleteActe(i) { actes.splice(i,1); renderActes(); }

function showToast(msg, error=false) {
  const toast = document.getElementById('toast');
  toast.textContent = msg;
  toast.className = 'toast' + (error ? ' border-red-400 text-red-700' : ' border-green-400 text-green-700');
  toast.classList.remove('hidden');
  setTimeout(() => toast.classList.add('hidden'), 2500);
}

// Gestion des événements de recherche de dossiers
document.getElementById('dossierSearch').addEventListener('input', (e) => {
  const query = e.target.value.trim();
  if (query.length >= 2) {
    // Debounce la recherche
    clearTimeout(window.searchTimeout);
    window.searchTimeout = setTimeout(() => searchDossiers(query), 300);
  }
});

document.getElementById('dossierSelect').addEventListener('change', (e) => {
  loadDossierInfo(e.target.value);
});

// Gestion des boutons d'action
document.getElementById('validerBtn').onclick = async () => {
  if (!selectedDossier) {
    showToast('Veuillez sélectionner un dossier', true);
    return;
  }

  if (actes.length === 0) {
    showToast('Veuillez ajouter au moins un acte', true);
    return;
  }

  try {
    const actesToSave = actes.map(acte => ({
      code: acte.code,
      type: detectActeType(acte.code),
      quantite: acte.quantite || 1,
      montant: acte.montant,
      modificateurs: acte.modificateurs ? acte.modificateurs.join(',') : null,
      commentaire: acte.commentaire,
      execute_date: new Date().toISOString()
    }));

    const response = await fetch('/cotation-modern/save', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        dossier_id: selectedDossier.id,
        actes: actesToSave
      })
    });

    if (!response.ok) throw new Error('Erreur sauvegarde');

    const result = await response.json();
    showToast(result.message);
    actes = []; // Vider la liste après sauvegarde
    renderActes();

  } catch (error) {
    console.error('Erreur sauvegarde:', error);
    showToast('Erreur lors de la sauvegarde des actes', true);
  }
};

document.getElementById('emettreBtn').onclick = () => {
  if (actes.length === 0) {
    showToast('Veuillez ajouter au moins un acte', true);
    return;
  }
  // Générer et afficher l'XML HPRIM
  generateHprimXML();
};

function detectActeType(code) {
  // Logique simple de détection du type d'acte
  if (code.match(/^[A-Z]\d{3}$/)) return 'CCAM'; // Lettre + 3 chiffres
  if (code.match(/^[A-Z]\d+\.?\d*$/)) return 'NGAP'; // Lettre + nombre
  if (code.match(/^\d{13}$/)) return 'UCD'; // 13 chiffres
  if (code.match(/^\d{7,13}$/)) return 'LPP'; // 7-13 chiffres
  return 'CCAM'; // Par défaut
}

// Fonctions pour l'interface adaptative et la validation en temps réel

function extractCodeFromQuery(query) {
  // Extraire le code de la requête (premier élément avant un tiret ou espace)
  const parts = query.split(/[-\s]/);
  return parts[0].toUpperCase();
}

function updateActeTypeDisplay(type, code) {
  // Créer ou mettre à jour l'affichage du type d'acte détecté
  let typeIndicator = document.getElementById('acteTypeIndicator');

  if (!typeIndicator) {
    // Créer l'indicateur s'il n'existe pas
    typeIndicator = document.createElement('div');
    typeIndicator.id = 'acteTypeIndicator';
    typeIndicator.className = 'mt-2 text-sm';

    const acteSearch = document.getElementById('acteSearch');
    acteSearch.parentNode.appendChild(typeIndicator);
  }

  // Définir les couleurs et labels selon le type
  const typeConfig = {
    'CCAM': { color: 'bg-blue-100 text-blue-800', label: 'CCAM - Classification Commune des Actes Médicaux' },
    'NGAP': { color: 'bg-green-100 text-green-800', label: 'NGAP - Nomenclature Générale des Actes Professionnels' },
    'UCD': { color: 'bg-purple-100 text-purple-800', label: 'UCD - Unité Commune de Dispensation' },
    'LPP': { color: 'bg-orange-100 text-orange-800', label: 'LPP - Liste des Produits et Prestations' }
  };

  const config = typeConfig[type] || typeConfig['CCAM'];

  typeIndicator.innerHTML = `
    <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${config.color}">
      <i class="fas fa-check-circle mr-1"></i>
      ${config.label}
    </span>
  `;

  typeIndicator.classList.remove('hidden');

  // Adapter l'interface selon le type d'acte
  adaptInterfaceForActeType(type);
}

function hideActeTypeDisplay() {
  const typeIndicator = document.getElementById('acteTypeIndicator');
  if (typeIndicator) {
    typeIndicator.classList.add('hidden');
  }
}

function validateActeCode(code, type) {
  let isValid = false;
  let errorMessage = '';

  switch (type) {
    case 'CCAM':
      isValid = /^[A-Z]\d{3}$/.test(code);
      errorMessage = 'Format CCAM invalide (doit être une lettre suivie de 3 chiffres, ex: HBMD001)';
      break;
    case 'NGAP':
      isValid = /^[A-Z]\d+\.?\d*$/.test(code);
      errorMessage = 'Format NGAP invalide (doit être une lettre suivie d\'un nombre, ex: C25.5)';
      break;
    case 'UCD':
      isValid = /^\d{13}$/.test(code);
      errorMessage = 'Format UCD invalide (doit être exactement 13 chiffres)';
      break;
    case 'LPP':
      isValid = /^\d{7,13}$/.test(code);
      errorMessage = 'Format LPP invalide (doit être entre 7 et 13 chiffres)';
      break;
  }

  // Afficher/masquer le message d'erreur
  updateValidationFeedback(isValid, errorMessage, type);
}

function updateValidationFeedback(isValid, errorMessage, type) {
  let validationFeedback = document.getElementById('acteValidationFeedback');

  if (!validationFeedback) {
    validationFeedback = document.createElement('div');
    validationFeedback.id = 'acteValidationFeedback';
    validationFeedback.className = 'mt-1 text-sm';

    const acteSearch = document.getElementById('acteSearch');
    acteSearch.parentNode.appendChild(validationFeedback);
  }

  if (isValid) {
    validationFeedback.innerHTML = `
      <span class="text-green-600">
        <i class="fas fa-check-circle mr-1"></i>
        Code ${type} valide
      </span>
    `;
  } else if (errorMessage) {
    validationFeedback.innerHTML = `
      <span class="text-red-600">
        <i class="fas fa-exclamation-triangle mr-1"></i>
        ${errorMessage}
      </span>
    `;
  } else {
    validationFeedback.innerHTML = '';
  }
}

function adaptInterfaceForActeType(type) {
  // Masquer tous les champs spécifiques
  hideAllTypeSpecificFields();

  // Afficher les champs spécifiques selon le type
  switch (type) {
    case 'CCAM':
      showCCAMFields();
      break;
    case 'NGAP':
      showNGAPFields();
      break;
    case 'UCD':
      showUCDFields();
      break;
    case 'LPP':
      showLPPFields();
      break;
  }
}

function hideAllTypeSpecificFields() {
  // Masquer tous les groupes de champs spécifiques
  const fieldGroups = [
    'ccamFields', 'ngapFields', 'ucdFields', 'lppFields',
    'modificateursSection', 'coefficientsSection'
  ];

  fieldGroups.forEach(groupId => {
    const element = document.getElementById(groupId);
    if (element) {
      element.classList.add('hidden');
    }
  });
}

function showCCAMFields() {
  // Afficher les champs spécifiques CCAM
  const ccamFields = document.getElementById('ccamFields');
  if (!ccamFields) {
    createCCAMFields();
  } else {
    ccamFields.classList.remove('hidden');
  }

  // Afficher la section modificateurs pour CCAM
  const modificateursSection = document.getElementById('modificateursSection');
  if (modificateursSection) {
    modificateursSection.classList.remove('hidden');
  }
}

function showNGAPFields() {
  // Afficher les champs spécifiques NGAP
  const ngapFields = document.getElementById('ngapFields');
  if (!ngapFields) {
    createNGAPFields();
  } else {
    ngapFields.classList.remove('hidden');
  }

  // Afficher la section coefficients pour NGAP
  const coefficientsSection = document.getElementById('coefficientsSection');
  if (coefficientsSection) {
    coefficientsSection.classList.remove('hidden');
  }
}

function showUCDFields() {
  // Afficher les champs spécifiques UCD
  const ucdFields = document.getElementById('ucdFields');
  if (!ucdFields) {
    createUCDFields();
  } else {
    ucdFields.classList.remove('hidden');
  }
}

function showLPPFields() {
  // Afficher les champs spécifiques LPP
  const lppFields = document.getElementById('lppFields');
  if (!lppFields) {
    createLPPFields();
  } else {
    lppFields.classList.remove('hidden');
  }
}

// Fonctions de création des champs spécifiques par type d'acte

function createCCAMFields() {
  const container = document.createElement('div');
  container.id = 'ccamFields';
  container.className = 'mt-4 p-4 bg-blue-50 rounded-lg border-l-4 border-blue-400';
  container.innerHTML = `
    <h4 class="text-sm font-semibold text-blue-800 mb-3 flex items-center">
      <i class="fas fa-stethoscope mr-2"></i>
      Champs spécifiques CCAM
    </h4>
    <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
      <div>
        <label class="block text-sm font-medium text-blue-700 mb-1">Code Activité</label>
        <input type="text" id="codeActivite" name="codeActivite" maxlength="2"
               class="block w-full rounded-lg border-2 border-blue-300 px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
               placeholder="Ex: 01">
      </div>
      <div>
        <label class="block text-sm font-medium text-blue-700 mb-1">Code Phase</label>
        <input type="text" id="codePhase" name="codePhase" maxlength="2"
               class="block w-full rounded-lg border-2 border-blue-300 px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
               placeholder="Ex: 00">
      </div>
      <div>
        <label class="block text-sm font-medium text-blue-700 mb-1">Extension</label>
        <input type="text" id="extensionCCAM" name="extensionCCAM"
               class="block w-full rounded-lg border-2 border-blue-300 px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
               placeholder="Code extension">
      </div>
    </div>
  `;

  // Insérer après la section de calcul du tarif
  const tarifSection = document.getElementById('tarifCalculation');
  if (tarifSection) {
    tarifSection.parentNode.insertBefore(container, tarifSection.nextSibling);
  }
}

function createNGAPFields() {
  const container = document.createElement('div');
  container.id = 'ngapFields';
  container.className = 'mt-4 p-4 bg-green-50 rounded-lg border-l-4 border-green-400';
  container.innerHTML = `
    <h4 class="text-sm font-semibold text-green-800 mb-3 flex items-center">
      <i class="fas fa-tooth mr-2"></i>
      Champs spécifiques NGAP
    </h4>
    <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
      <div>
        <label class="block text-sm font-medium text-green-700 mb-1">Position Dentaire</label>
        <input type="text" id="positionDentaire" name="positionDentaire"
               class="block w-full rounded-lg border-2 border-green-300 px-3 py-2 focus:ring-2 focus:ring-green-500 focus:border-green-500"
               placeholder="Ex: 11, 12, 13...">
      </div>
      <div>
        <label class="block text-sm font-medium text-green-700 mb-1">Numéro de Séance</label>
        <input type="number" id="numeroSeance" name="numeroSeance" min="1"
               class="block w-full rounded-lg border-2 border-green-300 px-3 py-2 focus:ring-2 focus:ring-green-500 focus:border-green-500"
               placeholder="1">
      </div>
      <div>
        <label class="block text-sm font-medium text-green-700 mb-1">Coefficient</label>
        <input type="number" id="coefficientNGAP" name="coefficientNGAP" step="0.01" min="0"
               class="block w-full rounded-lg border-2 border-green-300 px-3 py-2 focus:ring-2 focus:ring-green-500 focus:border-green-500"
               placeholder="1.00">
      </div>
    </div>
  `;

  // Insérer après la section de calcul du tarif
  const tarifSection = document.getElementById('tarifCalculation');
  if (tarifSection) {
    tarifSection.parentNode.insertBefore(container, tarifSection.nextSibling);
  }
}

function createUCDFields() {
  const container = document.createElement('div');
  container.id = 'ucdFields';
  container.className = 'mt-4 p-4 bg-purple-50 rounded-lg border-l-4 border-purple-400';
  container.innerHTML = `
    <h4 class="text-sm font-semibold text-purple-800 mb-3 flex items-center">
      <i class="fas fa-pills mr-2"></i>
      Champs spécifiques UCD
    </h4>
    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
      <div>
        <label class="block text-sm font-medium text-purple-700 mb-1">Prix Unitaire (€)</label>
        <input type="number" id="prixUnitaireUCD" name="prixUnitaireUCD" step="0.01" min="0"
               class="block w-full rounded-lg border-2 border-purple-300 px-3 py-2 focus:ring-2 focus:ring-purple-500 focus:border-purple-500"
               placeholder="0.00">
      </div>
      <div>
        <label class="block text-sm font-medium text-purple-700 mb-1">Quantité Dispensée</label>
        <input type="number" id="quantiteUCD" name="quantiteUCD" min="1"
               class="block w-full rounded-lg border-2 border-purple-300 px-3 py-2 focus:ring-2 focus:ring-purple-500 focus:border-purple-500"
               placeholder="1">
      </div>
    </div>
    <div class="mt-3">
      <label class="block text-sm font-medium text-purple-700 mb-1">Désignation du Médicament</label>
      <input type="text" id="designationUCD" name="designationUCD"
             class="block w-full rounded-lg border-2 border-purple-300 px-3 py-2 focus:ring-2 focus:ring-purple-500 focus:border-purple-500"
             placeholder="Nom du médicament">
    </div>
  `;

  // Insérer après la section de calcul du tarif
  const tarifSection = document.getElementById('tarifCalculation');
  if (tarifSection) {
    tarifSection.parentNode.insertBefore(container, tarifSection.nextSibling);
  }
}

function createLPPFields() {
  const container = document.createElement('div');
  container.id = 'lppFields';
  container.className = 'mt-4 p-4 bg-orange-50 rounded-lg border-l-4 border-orange-400';
  container.innerHTML = `
    <h4 class="text-sm font-semibold text-orange-800 mb-3 flex items-center">
      <i class="fas fa-prosthetic-hand mr-2"></i>
      Champs spécifiques LPP
    </h4>
    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
      <div>
        <label class="block text-sm font-medium text-orange-700 mb-1">Prix Unitaire (€)</label>
        <input type="number" id="prixUnitaireLPP" name="prixUnitaireLPP" step="0.01" min="0"
               class="block w-full rounded-lg border-2 border-orange-300 px-3 py-2 focus:ring-2 focus:ring-orange-500 focus:border-orange-500"
               placeholder="0.00">
      </div>
      <div>
        <label class="block text-sm font-medium text-orange-700 mb-1">Quantité Implantée</label>
        <input type="number" id="quantiteLPP" name="quantiteLPP" min="1"
               class="block w-full rounded-lg border-2 border-orange-300 px-3 py-2 focus:ring-2 focus:ring-orange-500 focus:border-orange-500"
               placeholder="1">
      </div>
    </div>
    <div class="mt-3">
      <label class="block text-sm font-medium text-orange-700 mb-1">Libellé de la Prothèse</label>
      <input type="text" id="libelleLPP" name="libelleLPP"
             class="block w-full rounded-lg border-2 border-orange-300 px-3 py-2 focus:ring-2 focus:ring-orange-500 focus:border-orange-500"
             placeholder="Description de la prothèse">
    </div>
  `;

  // Insérer après la section de calcul du tarif
  const tarifSection = document.getElementById('tarifCalculation');
  if (tarifSection) {
    tarifSection.parentNode.insertBefore(container, tarifSection.nextSibling);
  }
}

function getActeSpecificFields(type) {
  const fields = {};

  switch (type) {
    case 'CCAM':
      fields.codeActivite = document.getElementById('codeActivite')?.value || '';
      fields.codePhase = document.getElementById('codePhase')?.value || '';
      fields.extension = document.getElementById('extensionCCAM')?.value || '';
      break;

    case 'NGAP':
      fields.positionDentaire = document.getElementById('positionDentaire')?.value || '';
      fields.numeroSeance = parseInt(document.getElementById('numeroSeance')?.value) || null;
      fields.coefficient = parseFloat(document.getElementById('coefficientNGAP')?.value) || 1.0;
      break;

    case 'UCD':
      fields.prixUnitaire = parseFloat(document.getElementById('prixUnitaireUCD')?.value) || 0;
      fields.quantite = parseInt(document.getElementById('quantiteUCD')?.value) || 1;
      fields.designation = document.getElementById('designationUCD')?.value || '';
      break;

    case 'LPP':
      fields.prixUnitaire = parseFloat(document.getElementById('prixUnitaireLPP')?.value) || 0;
      fields.quantite = parseInt(document.getElementById('quantiteLPP')?.value) || 1;
      fields.libelle = document.getElementById('libelleLPP')?.value || '';
      break;
  }

  return fields;
}

function generateHprimXML() {
  // TODO: Implémenter la génération XML HPRIM
  document.getElementById('xmlPreview').textContent = 'Génération XML HPRIM à implémenter...';
  showToast('Fonctionnalité d\'émission à implémenter');
}

function saveActe() {
  const codeActe = document.getElementById('codeActe').value;
  if (!codeActe) {
    showToast('Veuillez sélectionner un acte', 'error');
    return;
  }

  const acte = actesMedicaux.find(a => a.code === codeActe);
  if (!acte) {
    showToast('Acte non trouvé', 'error');
    return;
  }

  // Détecter le type d'acte
  const acteType = detectActeType(acte.code);

  // Collecter les données communes
  const acteData = {
    code: acte.code,
    libelle: acte.libelle,
    tarif: acte.tarif,
    lettreCle: acte.lettreCle,
    type: acteType,
    quantite: parseInt(document.getElementById('quantite').value) || 1,
    modificateurs: getSelectedModificateurs(),
    dossierId: selectedDossier?.id || null
  };

  // Ajouter les champs spécifiques au type d'acte
  const specificFields = getActeSpecificFields(acteType);
  Object.assign(acteData, specificFields);

  // Calculer le tarif total
  const quantite = acteData.quantite;
  let tarifBase = acte.tarif * quantite;

  if (acteType === 'NGAP') {
    tarifBase *= acteData.coefficient || 1.0;
  }

  let multiplicateurTotal = 1;
  acteData.modificateurs.forEach(mod => {
    if (modificateursTarif[mod]) {
      multiplicateurTotal *= modificateursTarif[mod].multiplicateur;
    }
  });

  acteData.tarifTotal = tarifBase * multiplicateurTotal;

  console.log('Données de l\'acte à sauvegarder:', acteData);

  // TODO: Envoyer les données au backend
  // fetch('/api/cotations', {
  //   method: 'POST',
  //   headers: { 'Content-Type': 'application/json' },
  //   body: JSON.stringify(acteData)
  // })
  // .then(response => response.json())
  // .then(data => {
  //   showToast('Acte sauvegardé avec succès', 'success');
  //   // Réinitialiser le formulaire ou rediriger
  // })
  // .catch(error => {
  //   console.error('Erreur lors de la sauvegarde:', error);
  //   showToast('Erreur lors de la sauvegarde', 'error');
  // });

  showToast('Acte sauvegardé avec succès (simulation)', 'success');
}

// TODO: Ajout recherche d'actes, validation temps réel, feedback API, drag & drop, loader, etc.

renderActes();
setupEventListeners();
