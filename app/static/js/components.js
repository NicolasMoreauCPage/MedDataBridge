/**
 * 🧩 Composants Réutilisables - Phase 5.2
 * Bibliothèque de composants UI pour le système hospitalier
 */

/**
 * 🏥 Classe utilitaire pour les icônes de structure
 */
class StructureIcons {
  static icons = {
    eg: '🏥',
    ej: '🏥',
    pole: '🏢',
    service: '🏛️',
    uf: '🔹',
    uh: '🏠',
    chambre: '🛏️',
    lit: '💺'
  };

  static getIcon(type) {
    return this.icons[type.toLowerCase()] || '📍';
  }
}

/**
 * 🎨 Classe pour calculer les couleurs d'occupation
 */
class OccupationColors {
  static getLevel(percentage) {
    if (percentage > 100) return 'overcapacity';
    if (percentage >= 95) return 'critical';
    if (percentage >= 80) return 'warning';
    if (percentage >= 50) return 'normal';
    return 'low';
  }

  static getColor(percentage) {
    const level = this.getLevel(percentage);
    const colors = {
      low: '#10b981',
      normal: '#3b82f6',
      warning: '#f59e0b',
      critical: '#ef4444',
      overcapacity: '#991b1b'
    };
    return colors[level];
  }

  static getLabel(percentage) {
    const level = this.getLevel(percentage);
    const labels = {
      low: 'Disponible',
      normal: 'Normal',
      warning: 'Tendu',
      critical: 'Critique',
      overcapacity: 'Suroccupation'
    };
    return labels[level];
  }
}

/**
 * 🃏 Générateur de cartes structure
 */
class StructureCard {
  /**
   * Crée une carte pour une entité de structure
   * @param {Object} entity - Entité (EG, Pôle, Service, etc.)
   * @param {Object} options - Options d'affichage
   * @returns {HTMLElement}
   */
  static create(entity, options = {}) {
    const {
      showStats = true,
      showActions = true,
      showOccupation = true,
      onClick = null
    } = options;

    const card = document.createElement('div');
    card.className = `card-structure level-${entity.type.toLowerCase()}`;
    card.dataset.entityId = entity.id;
    card.dataset.entityType = entity.type;

    // Header
    const header = this.createHeader(entity, showActions);
    card.appendChild(header);

    // Body
    if (showStats || showOccupation) {
      const body = this.createBody(entity, showStats, showOccupation);
      card.appendChild(body);
    }

    // Click handler
    if (onClick) {
      card.style.cursor = 'pointer';
      card.addEventListener('click', (e) => {
        if (!e.target.closest('.btn-action')) {
          onClick(entity, e);
        }
      });
    }

    return card;
  }

  static createHeader(entity, showActions) {
    const header = document.createElement('div');
    header.className = 'card-structure-header';

    // Icon
    const icon = document.createElement('div');
    icon.className = 'card-structure-icon';
    icon.textContent = StructureIcons.getIcon(entity.type);
    header.appendChild(icon);

    // Title
    const title = document.createElement('div');
    title.className = 'card-structure-title';
    title.textContent = entity.nom || entity.code;
    header.appendChild(title);

    // Badge (code ou type)
    if (entity.code) {
      const badge = document.createElement('span');
      badge.className = 'card-structure-badge';
      badge.textContent = entity.code;
      header.appendChild(badge);
    }

    // Actions
    if (showActions) {
      const actions = this.createActions(entity);
      header.appendChild(actions);
    }

    return header;
  }

  static createBody(entity, showStats, showOccupation) {
    const body = document.createElement('div');
    body.className = 'card-structure-body';

    // Stats
    if (showStats && entity.stats) {
      const stats = this.createStats(entity.stats);
      body.appendChild(stats);
    }

    // Occupation bar
    if (showOccupation && entity.occupation !== undefined) {
      const occBar = this.createOccupationBar(entity.occupation);
      body.appendChild(occBar);
    }

    return body;
  }

  static createActions(entity) {
    const actions = document.createElement('div');
    actions.className = 'flex gap-2';

    const editBtn = document.createElement('button');
    editBtn.className = 'btn btn-sm btn-secondary btn-action';
    editBtn.innerHTML = '✏️';
    editBtn.title = 'Éditer';
    editBtn.onclick = (e) => {
      e.stopPropagation();
      this.onEdit(entity);
    };

    const deleteBtn = document.createElement('button');
    deleteBtn.className = 'btn btn-sm btn-danger btn-action';
    deleteBtn.innerHTML = '🗑️';
    deleteBtn.title = 'Supprimer';
    deleteBtn.onclick = (e) => {
      e.stopPropagation();
      this.onDelete(entity);
    };

    actions.appendChild(editBtn);
    actions.appendChild(deleteBtn);

    return actions;
  }

  static createStats(stats) {
    const container = document.createElement('div');
    container.className = 'card-structure-stats mt-2';

    Object.entries(stats).forEach(([key, value]) => {
      const stat = document.createElement('div');
      stat.className = 'card-structure-stat';

      const label = document.createElement('div');
      label.className = 'card-structure-stat-label';
      label.textContent = key;

      const val = document.createElement('div');
      val.className = 'card-structure-stat-value';
      val.textContent = value;

      stat.appendChild(label);
      stat.appendChild(val);
      container.appendChild(stat);
    });

    return container;
  }

  static createOccupationBar(occupation) {
    const percentage = Math.round(occupation);
    const level = OccupationColors.getLevel(percentage);

    const container = document.createElement('div');
    container.className = 'occupation-bar-container mt-4';

    const bar = document.createElement('div');
    bar.className = `occupation-bar ${level}`;
    bar.style.width = `${Math.min(percentage, 100)}%`;
    bar.textContent = `${percentage}%`;

    container.appendChild(bar);

    return container;
  }

  // Handlers par défaut (peuvent être surchargés)
  static onEdit(entity) {
    console.log('Edit:', entity);
  }

  static onDelete(entity) {
    if (confirm(`Supprimer ${entity.nom} ?`)) {
      console.log('Delete:', entity);
    }
  }
}

/**
 * 🔔 Système de notifications
 */
class NotificationSystem {
  static container = null;

  static init() {
    if (this.container) return;

    this.container = document.createElement('div');
    this.container.id = 'notification-container';
    this.container.style.cssText = `
      position: fixed;
      top: 20px;
      right: 20px;
      z-index: 9999;
      max-width: 400px;
    `;
    document.body.appendChild(this.container);
  }

  /**
   * Affiche une notification
   * @param {string} message - Message à afficher
   * @param {string} type - Type: 'success', 'error', 'warning', 'info'
   * @param {number} duration - Durée en ms (0 = permanent)
   */
  static show(message, type = 'info', duration = 3000) {
    this.init();

    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.style.cssText = `
      background: white;
      padding: 16px;
      margin-bottom: 12px;
      border-radius: 8px;
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
      border-left: 4px solid ${this.getColor(type)};
      display: flex;
      align-items: center;
      gap: 12px;
      animation: slideIn 0.3s ease;
    `;

    const icon = document.createElement('span');
    icon.textContent = this.getIcon(type);
    icon.style.fontSize = '24px';

    const text = document.createElement('div');
    text.textContent = message;
    text.style.flex = '1';
    text.style.fontSize = '14px';
    text.style.color = '#374151';

    const closeBtn = document.createElement('button');
    closeBtn.textContent = '×';
    closeBtn.style.cssText = `
      background: none;
      border: none;
      font-size: 24px;
      cursor: pointer;
      color: #9ca3af;
      padding: 0;
      width: 24px;
      height: 24px;
      display: flex;
      align-items: center;
      justify-content: center;
    `;
    closeBtn.onclick = () => this.remove(notification);

    notification.appendChild(icon);
    notification.appendChild(text);
    notification.appendChild(closeBtn);

    this.container.appendChild(notification);

    if (duration > 0) {
      setTimeout(() => this.remove(notification), duration);
    }

    return notification;
  }

  static remove(notification) {
    notification.style.animation = 'slideOut 0.3s ease';
    setTimeout(() => notification.remove(), 300);
  }

  static getIcon(type) {
    const icons = {
      success: '✅',
      error: '❌',
      warning: '⚠️',
      info: 'ℹ️'
    };
    return icons[type] || 'ℹ️';
  }

  static getColor(type) {
    const colors = {
      success: '#10b981',
      error: '#ef4444',
      warning: '#f59e0b',
      info: '#3b82f6'
    };
    return colors[type] || '#3b82f6';
  }

  // Méthodes de convenance
  static success(message, duration) {
    return this.show(message, 'success', duration);
  }

  static error(message, duration) {
    return this.show(message, 'error', duration);
  }

  static warning(message, duration) {
    return this.show(message, 'warning', duration);
  }

  static info(message, duration) {
    return this.show(message, 'info', duration);
  }
}

// Animations CSS
const style = document.createElement('style');
style.textContent = `
  @keyframes slideIn {
    from {
      transform: translateX(400px);
      opacity: 0;
    }
    to {
      transform: translateX(0);
      opacity: 1;
    }
  }

  @keyframes slideOut {
    from {
      transform: translateX(0);
      opacity: 1;
    }
    to {
      transform: translateX(400px);
      opacity: 0;
    }
  }
`;
document.head.appendChild(style);

/**
 * 🔍 Composant de recherche
 */
class SearchComponent {
  constructor(container, options = {}) {
    this.container = container;
    this.options = {
      placeholder: 'Rechercher...',
      minChars: 2,
      onSearch: () => {},
      onClear: () => {},
      ...options
    };
    this.init();
  }

  init() {
    this.container.className = 'search-component';
    this.container.style.cssText = `
      position: relative;
      width: 100%;
    `;

    // Input
    this.input = document.createElement('input');
    this.input.type = 'text';
    this.input.className = 'form-control';
    this.input.placeholder = this.options.placeholder;
    this.input.style.paddingRight = '80px';

    // Clear button
    this.clearBtn = document.createElement('button');
    this.clearBtn.textContent = '×';
    this.clearBtn.className = 'btn btn-sm btn-secondary';
    this.clearBtn.style.cssText = `
      position: absolute;
      right: 40px;
      top: 50%;
      transform: translateY(-50%);
      display: none;
    `;
    this.clearBtn.onclick = () => this.clear();

    // Search button
    this.searchBtn = document.createElement('button');
    this.searchBtn.textContent = '🔍';
    this.searchBtn.className = 'btn btn-sm btn-primary';
    this.searchBtn.style.cssText = `
      position: absolute;
      right: 4px;
      top: 50%;
      transform: translateY(-50%);
    `;
    this.searchBtn.onclick = () => this.search();

    this.container.appendChild(this.input);
    this.container.appendChild(this.clearBtn);
    this.container.appendChild(this.searchBtn);

    // Events
    this.input.addEventListener('input', (e) => {
      this.clearBtn.style.display = e.target.value ? 'block' : 'none';
      if (e.target.value.length >= this.options.minChars) {
        this.search();
      }
    });

    this.input.addEventListener('keypress', (e) => {
      if (e.key === 'Enter') {
        this.search();
      }
    });
  }

  search() {
    const query = this.input.value.trim();
    if (query.length >= this.options.minChars) {
      this.options.onSearch(query);
    }
  }

  clear() {
    this.input.value = '';
    this.clearBtn.style.display = 'none';
    this.options.onClear();
  }

  getValue() {
    return this.input.value;
  }

  setValue(value) {
    this.input.value = value;
    this.clearBtn.style.display = value ? 'block' : 'none';
  }
}

/**
 * 🎛️ Composant de filtres
 */
class FilterComponent {
  constructor(container, filters = []) {
    this.container = container;
    this.filters = filters;
    this.values = {};
    this.init();
  }

  init() {
    this.container.className = 'filter-component flex flex-wrap gap-4';

    this.filters.forEach(filter => {
      const filterEl = this.createFilter(filter);
      this.container.appendChild(filterEl);
    });
  }

  createFilter(filter) {
    const wrapper = document.createElement('div');
    wrapper.className = 'form-group';
    wrapper.style.marginBottom = '0';

    const label = document.createElement('label');
    label.className = 'form-label';
    label.textContent = filter.label;

    let input;
    if (filter.type === 'select') {
      input = document.createElement('select');
      input.className = 'form-control';
      
      const defaultOption = document.createElement('option');
      defaultOption.value = '';
      defaultOption.textContent = `-- ${filter.label} --`;
      input.appendChild(defaultOption);

      filter.options.forEach(opt => {
        const option = document.createElement('option');
        option.value = opt.value;
        option.textContent = opt.label;
        input.appendChild(option);
      });
    } else {
      input = document.createElement('input');
      input.type = filter.type || 'text';
      input.className = 'form-control';
    }

    input.addEventListener('change', (e) => {
      this.values[filter.name] = e.target.value;
      if (filter.onChange) {
        filter.onChange(e.target.value, this.values);
      }
    });

    wrapper.appendChild(label);
    wrapper.appendChild(input);

    return wrapper;
  }

  getValues() {
    return { ...this.values };
  }

  reset() {
    this.values = {};
    this.container.querySelectorAll('input, select').forEach(el => {
      el.value = '';
    });
  }
}

// Export pour utilisation globale
window.StructureIcons = StructureIcons;
window.OccupationColors = OccupationColors;
window.StructureCard = StructureCard;
window.NotificationSystem = NotificationSystem;
window.SearchComponent = SearchComponent;
window.FilterComponent = FilterComponent;
