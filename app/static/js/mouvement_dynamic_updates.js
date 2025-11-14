/**
 * mouvement_dynamic_updates.js
 * Gère les mises à jour dynamiques des champs du formulaire de création mouvement
 * 
 * Comportements:
 * 1. Quand UniteHebergement change -> met à jour la liste Chambre
 * 2. Quand Chambre change -> met à jour la liste Lit
 * 3. Quand Type change -> met à jour la liste Raison
 * 4. Au chargement: pré-charge les chambres/lits si UH pré-sélectionnée
 */

(function() {
  'use strict';

  /**
   * Met à jour un select avec les options récupérées via AJAX
   * @param {HTMLElement} selectElement - Élément select à mettre à jour
   * @param {Array} options - Liste {value, label} 
   * @param {string} placeholder - Texte du placeholder
   */
  function updateSelectOptions(selectElement, options, placeholder = '-- Sélectionner --') {
    if (!selectElement) return;
    
    // Garder la valeur actuellement sélectionnée
    const currentValue = selectElement.value;
    
    // Vider le select
    selectElement.innerHTML = '';
    
    // Ajouter le placeholder
    const placeholderOpt = document.createElement('option');
    placeholderOpt.value = '';
    placeholderOpt.textContent = placeholder;
    selectElement.appendChild(placeholderOpt);
    
    // Ajouter les nouvelles options
    options.forEach(opt => {
      const optElement = document.createElement('option');
      optElement.value = opt.value;
      optElement.textContent = opt.label;
      selectElement.appendChild(optElement);
    });
    
    // Restaurer la valeur si elle existe toujours
    if (currentValue && Array.from(selectElement.options).some(o => o.value === currentValue)) {
      selectElement.value = currentValue;
    }
    
    // Déclencher un changement pour cascade
    selectElement.dispatchEvent(new Event('change', { bubbles: true }));
  }

  /**
   * Appelle une AJAX endpoint et retourne les options
   * @param {string} endpoint - URL de l'API
   * @returns {Promise<Array>} Liste des options {value, label}
   */
  async function fetchOptions(endpoint) {
    try {
      const response = await fetch(endpoint);
      if (!response.ok) {
        console.error(`Erreur API: ${response.status} ${response.statusText}`);
        return [];
      }
      const data = await response.json();
      if (data.success) {
        return data.options || [];
      } else {
        console.error(`API error: ${data.error}`);
        return [];
      }
    } catch (error) {
      console.error(`Fetch error: ${error}`);
      return [];
    }
  }

  /**
   * Initialise les event listeners pour les mises à jour dynamiques
   */
  function initDynamicUpdates() {
    const form = document.querySelector('form[role="form"]');
    if (!form) return;

    const uhSelect = form.querySelector('select[name="unite_hebergement_id"]');
    const chambreSelect = form.querySelector('select[name="chambre_id"]');
    const litSelect = form.querySelector('select[name="lit_id"]');
    const typeSelect = form.querySelector('select[name="type"]');
    const reasonSelect = form.querySelector('select[name="reason"]');

    // 1. UniteHebergement -> Chambre
    if (uhSelect && chambreSelect) {
      uhSelect.addEventListener('change', async function() {
        if (!this.value) {
          // Vider chambre si rien sélectionné
          updateSelectOptions(chambreSelect, [], '-- Sélectionner une chambre --');
          return;
        }
        
        const options = await fetchOptions(`/api/mouvements/chambres/${this.value}`);
        updateSelectOptions(chambreSelect, options, '-- Sélectionner une chambre --');
      });
    }

    // 2. Chambre -> Lit
    if (chambreSelect && litSelect) {
      chambreSelect.addEventListener('change', async function() {
        if (!this.value) {
          updateSelectOptions(litSelect, [], '-- Sélectionner un lit --');
          return;
        }
        
        const options = await fetchOptions(`/api/mouvements/lits/${this.value}`);
        updateSelectOptions(litSelect, options, '-- Sélectionner un lit --');
      });
    }

    // 3. Type (movement) -> Reason
    if (typeSelect && reasonSelect) {
      typeSelect.addEventListener('change', async function() {
        if (!this.value) {
          updateSelectOptions(reasonSelect, [], '-- Sélectionner une raison --');
          return;
        }
        
        // Extraire le code du type (ex: "A01^Admission" -> "A01")
        const typeValue = this.value;
        const typeCode = typeValue.includes('^') ? typeValue.split('^')[1] : typeValue;
        
        const options = await fetchOptions(`/api/mouvements/reasons/${typeCode}`);
        updateSelectOptions(reasonSelect, options, '-- Sélectionner une raison --');
      });
    }

    // 4. Au chargement: si UH est pré-sélectionnée, charger ses chambres/lits
    if (uhSelect && uhSelect.value && chambreSelect) {
      // Déclencher le changement pour pré-charger les chambres
      uhSelect.dispatchEvent(new Event('change', { bubbles: true }));
    }
  }

  // Initialiser au chargement du DOM
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initDynamicUpdates);
  } else {
    initDynamicUpdates();
  }
})();

