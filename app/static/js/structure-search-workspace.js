/**
 * 🔍 Interface de Recherche Avancée Structure - Phase 5.3
 * Utilise l'API FHIR Structure existante (/fhir/Location)
 */

class AdvancedStructureSearch {
  constructor() {
    this.searchHistory = JSON.parse(localStorage.getItem('structureSearchHistory') || '[]');
    this.currentQuery = {};
    this.currentResults = [];
    this.currentPage = 0;
    this.pageSize = 20;
    this.totalResults = 0;
    this.searchRun = 0;
    
    this.init();
  }

  init() {
    this.initSearchComponent();
    this.initAdvancedFilters();
    this.initEventListeners();
    this.loadSearchHistory();
    
    // Recherche initiale (toutes les structures)
    this.performSearch();
  }

  initSearchComponent() {
    const container = document.getElementById('main-search-container');
    this.searchComponent = new SearchComponent(container, {
      placeholder: 'Nom, code, identifiant FINESS...',
      minChars: 0,
      onSearch: (query) => {
        this.currentQuery.name = query;
        this.performSearch();
      },
      onClear: () => {
        delete this.currentQuery.name;
        this.performSearch();
      }
    });
  }

  initAdvancedFilters() {
    const container = document.getElementById('advanced-filters');
    this.filterComponent = new FilterComponent(container, [
      {
        name: 'type',
        label: 'Type de structure',
        type: 'select',
        options: [
          { value: 'hospital', label: '🏥 Hôpital' },
          { value: 'department', label: '🏢 Département' },
          { value: 'ward', label: '🏛️ Service' },
          { value: 'room', label: '🛏️ Chambre' },
          { value: 'bed', label: '💺 Lit' }
        ],
        onChange: (value) => {
          if (value) {
            this.currentQuery.type = value;
          } else {
            delete this.currentQuery.type;
          }
          this.performSearch();
        }
      },
      {
        name: 'status',
        label: 'Statut',
        type: 'select',
        options: [
          { value: 'active', label: '✅ Actif' },
          { value: 'inactive', label: '❌ Inactif' },
          { value: 'suspended', label: '⏸️ Suspendu' }
        ],
        onChange: (value) => {
          if (value) {
            this.currentQuery.status = value;
          } else {
            delete this.currentQuery.status;
          }
          this.performSearch();
        }
      },
      {
        name: 'operational-status',
        label: 'Statut opérationnel',
        type: 'select',
        options: [
          { value: 'operational', label: '🟢 Opérationnel' },
          { value: 'closed', label: '🔴 Fermé' },
          { value: 'housekeeping', label: '🧹 Maintenance' }
        ],
        onChange: (value) => {
          if (value) {
            this.currentQuery['operational-status'] = value;
          } else {
            delete this.currentQuery['operational-status'];
          }
          this.performSearch();
        }
      },
      {
        name: 'identifier',
        label: 'Identifiant/FINESS',
        type: 'text',
        onChange: (value) => {
          if (value) {
            this.currentQuery.identifier = value;
          } else {
            delete this.currentQuery.identifier;
          }
          this.performSearch();
        }
      }
    ]);

    // Masquer par défaut
    container.style.display = 'none';
  }

  initEventListeners() {
    // Formulaire
    document.getElementById('search-form').addEventListener('submit', (e) => {
      e.preventDefault();
      this.performSearch();
    });

    // Boutons d'action
    document.getElementById('clear-filters').addEventListener('click', () => {
      this.clearFilters();
    });

    document.getElementById('toggle-advanced').addEventListener('click', () => {
      this.toggleAdvancedFilters();
    });

    document.getElementById('export-results').addEventListener('click', () => {
      this.exportResults();
    });
  }

  async performSearch() {
    const startTime = Date.now();
    
    this.showLoading();
    
    try {
      // Construire les paramètres de recherche FHIR
      const params = new URLSearchParams();
      
      // Ajouter les paramètres de recherche
      Object.entries(this.currentQuery).forEach(([key, value]) => {
        if (value && value.trim()) {
          params.append(key, value);
        }
      });

      // Pagination
      params.append('_count', this.pageSize.toString());
      if (this.currentPage > 0) {
        params.append('_offset', (this.currentPage * this.pageSize).toString());
      }

      // Format JSON
      params.append('_format', 'json');

      console.log('FHIR search params:', params.toString());

      // Appel API FHIR : le client commun gère délai, annulation et enveloppe
      // d'erreur MedData Bridge de manière identique aux autres espaces.
      const { data: bundle } = await window.medbridgeHttp.get(
        `/fhir/Location?${params.toString()}`
      );
      
      // Traitement des résultats
      this.currentResults = bundle.entry || [];
      this.totalResults = bundle.total || 0;
      
      // Mise à jour de l'interface
      const searchTime = Date.now() - startTime;
      this.updateStats(this.totalResults, searchTime);
      this.displayResults();
      
      // Sauvegarder dans l'historique
      this.saveToHistory();

    } catch (error) {
      console.error('Erreur recherche:', error);
      NotificationSystem.error(`Erreur de recherche: ${error.message}`);
      this.showEmptyResults();
    }
  }

  showLoading() {
    document.getElementById('loading-container').style.display = 'block';
    document.getElementById('empty-results').style.display = 'none';
    document.getElementById('search-results').style.display = 'none';
  }

  showEmptyResults() {
    document.getElementById('loading-container').style.display = 'none';
    document.getElementById('empty-results').style.display = 'block';
    document.getElementById('search-results').style.display = 'none';
  }

  displayResults() {
    document.getElementById('loading-container').style.display = 'none';
    document.getElementById('empty-results').style.display = 'none';

    if (this.currentResults.length === 0) {
      this.showEmptyResults();
      return;
    }

    document.getElementById('search-results').style.display = 'block';
    
    const resultsList = document.getElementById('results-list');
    resultsList.replaceChildren();

    // Convertir les résultats FHIR en format de cartes
    this.currentResults.forEach((entry) => {
      const location = entry.resource;
      
      // Mapper les données FHIR vers notre format de carte
      const entity = this.mapFhirToEntity(location);
      
      // Créer la carte avec le Design System
      const card = StructureCard.create(entity, {
        showStats: true,
        showOccupation: false, // Pas d'occupation dans FHIR
        showActions: true,
        onClick: (e) => {
          // Navigation vers les détails
          window.location.href = `/fhir/Location/${location.id}`;
        }
      });

      card.classList.add('search-result-card');
      resultsList.appendChild(card);
    });

    this.updatePagination();
  }

  mapFhirToEntity(location) {
    // Convertir une ressource FHIR Location vers notre format de carte
    return {
      id: location.id,
      type: this.mapFhirTypeToEntityType(location.type?.[0]?.coding?.[0]?.code),
      nom: location.name || 'Sans nom',
      code: location.identifier?.[0]?.value || location.id,
      stats: {
        'ID': location.id,
        'Statut': location.status === 'active' ? '✅ Actif' : '❌ Inactif'
      }
    };
  }

  mapFhirTypeToEntityType(fhirType) {
    const mapping = {
      'hospital': 'EG',
      'department': 'Pole', 
      'ward': 'Service',
      'room': 'Chambre',
      'bed': 'Lit'
    };
    return mapping[fhirType] || 'Structure';
  }

  updateStats(count, time) {
    this.searchRun += 1;
    document.getElementById('search-count').textContent = count;
    document.getElementById('search-time').textContent = `${time}ms · recherche ${this.searchRun}`;
  }

  updatePagination() {
    const container = document.getElementById('search-pagination');
    container.replaceChildren();

    if (this.totalResults <= this.pageSize) {
      return; // Pas de pagination nécessaire
    }

    const totalPages = Math.ceil(this.totalResults / this.pageSize);
    
    // Bouton précédent
    const prevBtn = document.createElement('button');
    prevBtn.className = `btn btn-sm btn-secondary ${this.currentPage === 0 ? 'disabled' : ''}`;
    prevBtn.textContent = '← Précédent';
    prevBtn.onclick = () => this.goToPage(this.currentPage - 1);
    container.appendChild(prevBtn);

    // Info pagination
    const info = document.createElement('span');
    info.className = 'pagination-info';
    info.textContent = `Page ${this.currentPage + 1} sur ${totalPages} (${this.totalResults} résultats)`;
    container.appendChild(info);

    // Bouton suivant
    const nextBtn = document.createElement('button');
    nextBtn.className = `btn btn-sm btn-secondary ${this.currentPage >= totalPages - 1 ? 'disabled' : ''}`;
    nextBtn.textContent = 'Suivant →';
    nextBtn.onclick = () => this.goToPage(this.currentPage + 1);
    container.appendChild(nextBtn);
  }

  goToPage(page) {
    if (page < 0 || page >= Math.ceil(this.totalResults / this.pageSize)) {
      return;
    }
    
    this.currentPage = page;
    this.performSearch();
  }

  clearFilters() {
    this.currentQuery = {};
    this.currentPage = 0;
    
    this.searchComponent.setValue('');
    this.filterComponent.reset();
    
    this.performSearch();
    
    NotificationSystem.info('Filtres effacés');
  }

  toggleAdvancedFilters() {
    const container = document.getElementById('advanced-filters');
    const isVisible = container.style.display !== 'none';
    
    container.style.display = isVisible ? 'none' : 'grid';
    
    const button = document.getElementById('toggle-advanced');
    button.textContent = isVisible ? '⚙️ Filtres avancés' : '🔼 Masquer filtres';
  }

  saveToHistory() {
    if (Object.keys(this.currentQuery).length === 0) {
      return; // Ne pas sauvegarder les recherches vides
    }

    const searchItem = {
      query: { ...this.currentQuery },
      timestamp: Date.now(),
      results: this.totalResults
    };

    // Éviter les doublons
    this.searchHistory = this.searchHistory.filter(item => 
      JSON.stringify(item.query) !== JSON.stringify(searchItem.query)
    );

    this.searchHistory.unshift(searchItem);
    this.searchHistory = this.searchHistory.slice(0, 10); // Garder seulement les 10 dernières

    localStorage.setItem('structureSearchHistory', JSON.stringify(this.searchHistory));
    this.loadSearchHistory();
  }

  loadSearchHistory() {
    const historyContainer = document.getElementById('search-history');
    const historyList = document.getElementById('search-history-list');

    if (this.searchHistory.length === 0) {
      historyContainer.style.display = 'none';
      return;
    }

    historyContainer.style.display = 'block';
    historyList.replaceChildren();

    this.searchHistory.forEach((item, index) => {
      const historyItem = document.createElement('div');
      historyItem.className = 'search-history-item';
      
      const queryText = Object.entries(item.query)
        .map(([key, value]) => `${key}:"${value}"`)
        .join(', ');
      
      const icon = document.createElement('span');
      icon.textContent = '🔍';
      const query = document.createElement('span');
      query.style.flex = '1';
      query.textContent = queryText;
      const count = document.createElement('small');
      count.textContent = `${item.results} résultats`;
      historyItem.append(icon, query, count);

      historyItem.onclick = () => {
        this.loadFromHistory(item);
      };

      historyList.appendChild(historyItem);
    });
  }

  loadFromHistory(historyItem) {
    this.currentQuery = { ...historyItem.query };
    this.currentPage = 0;

    // Mettre à jour l'interface
    if (this.currentQuery.name) {
      this.searchComponent.setValue(this.currentQuery.name);
    }

    // Note: Les filtres seront mis à jour automatiquement par la recherche
    this.performSearch();
    
    NotificationSystem.info('Recherche chargée depuis l\'historique');
  }

  exportResults() {
    if (this.currentResults.length === 0) {
      NotificationSystem.warning('Aucun résultat à exporter');
      return;
    }

    // Export simple en JSON
    const exportData = {
      query: this.currentQuery,
      total: this.totalResults,
      results: this.currentResults.map(entry => ({
        id: entry.resource.id,
        name: entry.resource.name,
        type: entry.resource.type?.[0]?.coding?.[0]?.code,
        status: entry.resource.status,
        identifier: entry.resource.identifier?.[0]?.value
      })),
      exportedAt: new Date().toISOString()
    };

    const blob = new Blob([JSON.stringify(exportData, null, 2)], {
      type: 'application/json'
    });
    
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `structure_search_${new Date().toISOString().split('T')[0]}.json`;
    a.click();
    URL.revokeObjectURL(url);

    NotificationSystem.success('Résultats exportés avec succès');
  }
}

// Initialisation
document.addEventListener('DOMContentLoaded', () => {
  window.structureSearch = new AdvancedStructureSearch();
  
  // Message de bienvenue
  NotificationSystem.info('Interface de recherche avancée prête !');
});
