// Fichier : static/js/mouvement_reason_filter.js
// Filtrage dynamique des motifs/raisons selon le type de mouvement

(function(){
  document.addEventListener('DOMContentLoaded', function() {
    const form = document.querySelector('form[role="form"]');
    if (!form) return;
    const typeSelect = form.querySelector('select[name="type"]');
    const reasonSelect = form.querySelector('select[name="reason"]');
    if (!typeSelect || !reasonSelect) return;

    // Table de correspondance type => motifs
    // Les valeurs doivent correspondre à celles du backend
    const motifsByType = {
      'ADT^A01': [ 'admission', 'urgence', 'autre' ],
      'ADT^A02': [ 'transfert', 'mutation', 'autre' ],
      'ADT^A03': [ 'sortie', 'deces', 'autre' ],
      'ADT^A04': [ 'consultation', 'autre' ],
    };

    // Stockage initial de toutes les options
    const allOptions = Array.from(reasonSelect.options);

    function filterMotifs() {
      const typeVal = typeSelect.value;
      const motifs = motifsByType[typeVal] || allOptions.map(o => o.value);
      // Filtrer les options
      reasonSelect.innerHTML = '';
      allOptions.forEach(opt => {
        if (!opt.value || motifs.includes(opt.value)) {
          reasonSelect.appendChild(opt.cloneNode(true));
        }
      });
    }

    typeSelect.addEventListener('change', filterMotifs);
    filterMotifs();
  });
})();
