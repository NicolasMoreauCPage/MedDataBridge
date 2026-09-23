/* Interactions de la démonstration du design system. */
"use strict";

document.addEventListener('click', (event) => {
  const button = event.target.closest('[data-demo-notification]');
  if (!button) return;
  const message = button.dataset.message || 'Notification de démonstration';
  const type = button.dataset.demoNotification;
  if (type === 'permanent') NotificationSystem.show(message, 'success', 0);
  else NotificationSystem[type]?.(message);
});

// Gestion des onglets
document.querySelectorAll('.demo-tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    const tab = btn.dataset.tab;
    
    // Update button states
    document.querySelectorAll('.demo-tab-btn').forEach(b => {
      b.className = b === btn
        ? 'demo-tab-btn rounded px-3 py-2 bg-blue-600 text-white'
        : 'demo-tab-btn rounded px-3 py-2 border border-slate-300';
    });
    
    // Show/hide content
    document.querySelectorAll('.tab-content').forEach(content => {
      content.style.display = content.id === `tab-${tab}` ? 'block' : 'none';
    });
  });
});

// Demo: Cartes de structure
function initCardsDemo() {
  const container = document.getElementById('cards-demo');
  
  const entities = [
    {
      id: 1,
      type: 'EG',
      nom: 'CHU Démo',
      code: 'CHU001',
      stats: {
        'Pôles': '4',
        'Services': '15',
        'Lits': '287'
      },
      occupation: 82
    },
    {
      id: 2,
      type: 'Pole',
      nom: 'Pôle Médecine',
      code: 'MED',
      stats: {
        'Services': '6',
        'Lits': '156'
      },
      occupation: 89
    },
    {
      id: 3,
      type: 'Service',
      nom: 'Cardiologie',
      code: 'CARDIO',
      stats: {
        'UF': '2',
        'Lits': '32'
      },
      occupation: 95
    },
    {
      id: 4,
      type: 'UF',
      nom: 'UF Cardiologie A',
      code: 'CARDIO-A',
      stats: {
        'Lits': '16'
      },
      occupation: 100
    }
  ];

  entities.forEach(entity => {
    const card = StructureCard.create(entity, {
      showStats: true,
      showOccupation: true,
      showActions: true,
      onClick: (e) => {
        NotificationSystem.info(`Clic sur: ${e.nom}`);
      }
    });
    container.appendChild(card);
  });
}

// Demo: Barres d'occupation
function initOccupationBarsDemo() {
  const container = document.getElementById('occupation-bars-demo');
  const levels = [
    { label: 'Service A', value: 35 },
    { label: 'Service B', value: 65 },
    { label: 'Service C', value: 87 },
    { label: 'Service D', value: 97 },
    { label: 'Service E', value: 105 }
  ];

  levels.forEach(({ label, value }) => {
    const wrapper = document.createElement('div');
    wrapper.style.marginBottom = '16px';

    const labelEl = document.createElement('div');
    labelEl.style.cssText = 'font-weight: 600; margin-bottom: 8px; color: #374151;';
    labelEl.textContent = `${label} - ${value}% (${OccupationColors.getLabel(value)})`;

    const bar = StructureCard.createOccupationBar(value);

    wrapper.appendChild(labelEl);
    wrapper.appendChild(bar);
    container.appendChild(wrapper);
  });
}

// Demo: Recherche
function initSearchDemo() {
  const container = document.getElementById('search-demo');
  new SearchComponent(container, {
    placeholder: 'Rechercher une structure...',
    onSearch: (query) => {
      NotificationSystem.info(`Recherche: "${query}"`);
    },
    onClear: () => {
      NotificationSystem.info('Recherche effacée');
    }
  });
}

// Demo: Filtres
function initFiltersDemo() {
  const container = document.getElementById('filters-demo');
  new FilterComponent(container, [
    {
      name: 'type',
      label: 'Type',
      type: 'select',
      options: [
        { value: 'eg', label: 'EG' },
        { value: 'pole', label: 'Pôle' },
        { value: 'service', label: 'Service' },
        { value: 'uf', label: 'UF' }
      ],
      onChange: (value) => {
        NotificationSystem.info(`Filtre Type: ${value}`);
      }
    },
    {
      name: 'um',
      label: 'Unité Médicale',
      type: 'select',
      options: [
        { value: 'mco', label: 'MCO' },
        { value: 'psy', label: 'PSY' },
        { value: 'ssr', label: 'SSR' },
        { value: 'had', label: 'HAD' }
      ],
      onChange: (value) => {
        NotificationSystem.info(`Filtre UM: ${value}`);
      }
    },
    {
      name: 'occupation',
      label: 'Occupation min (%)',
      type: 'number',
      onChange: (value) => {
        NotificationSystem.info(`Occupation min: ${value}%`);
      }
    }
  ]);
}

// Initialisation
document.addEventListener('DOMContentLoaded', () => {
  initCardsDemo();
  initOccupationBarsDemo();
  initSearchDemo();
  initFiltersDemo();
});
