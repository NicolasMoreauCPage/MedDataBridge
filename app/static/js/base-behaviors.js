      const btn = document.getElementById('menu-btn');
      const menu = document.getElementById('mobile-menu');
      if (btn && menu) {
        const closeMenu = () => {
          menu.classList.add('hidden');
          btn.setAttribute('aria-expanded', 'false');
        };
        btn.addEventListener('click', () => {
          const isOpen = menu.classList.toggle('hidden') === false;
          btn.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
        });
        document.addEventListener('keydown', (event) => {
          if (event.key === 'Escape') {
            closeMenu();
          }
        });
        document.addEventListener('click', (event) => {
          if (!menu.classList.contains('hidden') && !menu.contains(event.target) && !btn.contains(event.target)) {
            closeMenu();
          }
        });
      }

      // Keep aria-expanded synchronized and support keyboard navigation on desktop mega-menus.
      document.querySelectorAll('nav[aria-label="Navigation principale"] li.group').forEach((item) => {
        const trigger = item.querySelector('button[aria-haspopup="menu"]');
        if (!trigger) return;

        const getFocusableItems = () => {
          return Array.from(item.querySelectorAll('a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])'))
            .filter((el) => !el.hidden && el.offsetParent !== null)
            .filter((el) => el !== trigger);
        };

        const setExpanded = (expanded) => {
          trigger.setAttribute('aria-expanded', expanded ? 'true' : 'false');
        };

        const focusFirstMenuItem = () => {
          const items = getFocusableItems();
          if (items.length > 0) {
            items[0].focus();
          }
        };

        const focusRelativeMenuItem = (current, delta) => {
          const items = getFocusableItems();
          if (items.length === 0) return;
          const index = Math.max(0, items.indexOf(current));
          const next = (index + delta + items.length) % items.length;
          items[next].focus();
        };

        item.addEventListener('mouseenter', () => setExpanded(true));
        item.addEventListener('mouseleave', () => setExpanded(false));
        item.addEventListener('focusin', () => setExpanded(true));
        item.addEventListener('focusout', (event) => {
          if (!item.contains(event.relatedTarget)) {
            setExpanded(false);
          }
        });

        trigger.addEventListener('keydown', (event) => {
          if (event.key === 'Enter' || event.key === ' ' || event.key === 'ArrowDown') {
            event.preventDefault();
            setExpanded(true);
            focusFirstMenuItem();
          }
          if (event.key === 'Escape') {
            setExpanded(false);
          }
        });

        item.addEventListener('keydown', (event) => {
          const active = document.activeElement;
          if (!item.contains(active)) return;

          if (event.key === 'Escape') {
            event.preventDefault();
            setExpanded(false);
            trigger.focus();
            return;
          }

          if (event.key === 'ArrowDown') {
            event.preventDefault();
            focusRelativeMenuItem(active, 1);
          }

          if (event.key === 'ArrowUp') {
            event.preventDefault();
            focusRelativeMenuItem(active, -1);
          }
        });
      });


    document.addEventListener('keydown', (e) => {
      // Alt+A -> Admin
      if (e.altKey && e.key === 'a') {
        window.location.href = '/admin';
      }
      // Alt+D -> Documentation
      if (e.altKey && e.key === 'd') {
        window.location.href = '/documentation';
      }
      // Alt+H -> Home
      if (e.altKey && e.key === 'h') {
        window.location.href = '/';
      }
    });


    document.addEventListener('DOMContentLoaded', () => {
      const path = window.location.pathname;
      document.querySelectorAll('nav a').forEach(link => {
        if (link.getAttribute('href') === path) {
          link.classList.add('bg-blue-50', 'text-blue-700');
          link.setAttribute('aria-current', 'page');
        }
      });
    });


    document.addEventListener('DOMContentLoaded', function() {
      try {
        const candidates = Array.from(document.body.querySelectorAll('*'));
        candidates.forEach(el => {
          if (!el || !el.innerText) return;
          const txt = el.innerText.trim();
          if (!/Tableau\s+de\s+bord/i.test(txt)) return;
          const rect = el.getBoundingClientRect();
          // Heuristic: small width and positioned near left edge of viewport
          if (rect.width < 160 && rect.left < 120 && rect.height > 16) {
            el.style.display = 'none';
            console.debug('Hidden stray left pill element containing "Tableau de bord"', el);
          }
        });
      } catch (e) {
        console.error('Defensive UI cleanup script failed', e);
      }
    });

    // Gestionnaire de thème simplifié (cycle: light -> dark -> auto -> light...)
    const themeToggle = {
      themes: ['light', 'dark', 'auto'],
      currentIndex: 0,
      
      init() {
        const savedTheme = localStorage.getItem('theme') || 'auto';
        this.currentIndex = this.themes.indexOf(savedTheme);
        if (this.currentIndex === -1) this.currentIndex = 2; // default to auto
        this.applyTheme();
        this.updateIcon();
      },
      
      cycleTheme() {
        this.currentIndex = (this.currentIndex + 1) % this.themes.length;
        const theme = this.themes[this.currentIndex];
        localStorage.setItem('theme', theme);
        this.applyTheme();
        this.updateIcon();
      },
      
      applyTheme() {
        const theme = this.themes[this.currentIndex];
        const html = document.documentElement;
        
        if (theme === 'auto') {
          const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
          if (prefersDark) {
            html.classList.add('dark');
          } else {
            html.classList.remove('dark');
          }
        } else if (theme === 'dark') {
          html.classList.add('dark');
        } else {
          html.classList.remove('dark');
        }
        
        html.setAttribute('data-theme', theme);
      },
      
      updateIcon() {
        const theme = this.themes[this.currentIndex];
        const sunIcon = document.getElementById('theme-icon-sun');
        const moonIcon = document.getElementById('theme-icon-moon');
        const autoIcon = document.getElementById('theme-icon-auto');
        
        // Hide all icons first
        [sunIcon, moonIcon, autoIcon].forEach(icon => {
          if (icon) icon.classList.add('hidden');
        });
        
        // Show the appropriate icon
        if (theme === 'light' && sunIcon) {
          sunIcon.classList.remove('hidden');
        } else if (theme === 'dark' && moonIcon) {
          moonIcon.classList.remove('hidden');
        } else if (theme === 'auto' && autoIcon) {
          autoIcon.classList.remove('hidden');
        }
      },
      
      // Écouter les changements de préférences système pour le mode auto
      watchSystemTheme() {
        window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
          if (this.themes[this.currentIndex] === 'auto') {
            this.applyTheme();
          }
        });
      }
    };
    
    // Initialiser le thème au chargement
    themeToggle.init();
    themeToggle.watchSystemTheme();
    
    // Event listener pour le bouton de thème
    document.addEventListener('DOMContentLoaded', function() {
      document.getElementById('theme-toggle')?.addEventListener('click', () => themeToggle.cycleTheme());
    });
    
    // Exposer globalement
    window.themeToggle = themeToggle;
    
    // Système de toasts/notifications
    const toastSystem = {
      container: null,
      
      init() {
        this.container = document.getElementById('toast-container');
      },
      
      show(message, type = 'info', duration = 5000) {
        if (!this.container) this.init();
        
        const id = 'toast-' + Date.now();
        const toastHtml = `
          <div id="${id}" class="alert alert-${type} shadow-lg max-w-sm animate-in slide-in-from-right-full duration-300" role="alert" aria-live="assertive">
            <div class="flex items-center gap-3">
              <svg class="w-5 h-5 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                ${this.getIcon(type)}
              </svg>
              <span class="flex-1">${message}</span>
              <button class="btn btn-sm btn-circle btn-ghost" onclick="toastSystem.dismiss('${id}')" aria-label="Fermer la notification">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                </svg>
              </button>
            </div>
          </div>
        `;
        
        this.container.insertAdjacentHTML('beforeend', toastHtml);
        
        // Auto-dismiss après la durée spécifiée
        if (duration > 0) {
          setTimeout(() => this.dismiss(id), duration);
        }
        
        return id;
      },
      
      dismiss(id) {
        const toast = document.getElementById(id);
        if (toast) {
          toast.classList.add('animate-out', 'slide-out-to-right-full', 'duration-300');
          setTimeout(() => toast.remove(), 300);
        }
      },
      
      getIcon(type) {
        const icons = {
          success: '<path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"></path>',
          error: '<path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd"></path>',
          warning: '<path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd"></path>',
          info: '<path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clip-rule="evenodd"></path>'
        };
        return icons[type] || icons.info;
      }
    };
    
    // Initialiser le système de toasts
    document.addEventListener('DOMContentLoaded', function() {
      toastSystem.init();
    });
    
    // Exposer globalement
    window.toastSystem = toastSystem;
    
    // Système de loaders pour formulaires
    const loadingSystem = {
      showOverlay(message = 'Chargement en cours...') {
        const overlayHtml = `
          <div id="loading-overlay" class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50" role="dialog" aria-modal="true" aria-labelledby="loading-title">
            <div class="bg-base-100 rounded-lg p-6 shadow-xl max-w-sm mx-4">
              <div class="flex items-center gap-4">
                <div class="inline-block animate-spin rounded-full border-2 border-primary border-t-transparent w-8 h-8" role="status" aria-label="Chargement en cours"></div>
                <div>
                  <h3 id="loading-title" class="font-semibold text-lg">${message}</h3>
                  <p class="text-sm opacity-70">Veuillez patienter...</p>
                </div>
              </div>
            </div>
          </div>
        `;
        document.body.insertAdjacentHTML('beforeend', overlayHtml);
      },
      
      hideOverlay() {
        const overlay = document.getElementById('loading-overlay');
        if (overlay) {
          overlay.remove();
        }
      },
      
      setButtonLoading(button, loading = true, loadingText = 'Chargement...') {
        if (loading) {
          button.disabled = true;
          button.innerHTML = `
            <span class="loading-text">${loadingText}</span>
            <div class="inline-block animate-spin rounded-full border-2 border-current border-t-transparent w-4 h-4 ml-2" role="status" aria-label="Chargement en cours"></div>
          `;
          button.classList.add('loading');
        } else {
          button.disabled = false;
          button.innerHTML = button.dataset.originalText || 'Soumettre';
          button.classList.remove('loading');
        }
      }
    };
    
    // Gestion automatique des formulaires
    document.addEventListener('DOMContentLoaded', function() {
      // Auto-loading pour les formulaires avec data-auto-loading
      document.querySelectorAll('form[data-auto-loading]').forEach(form => {
        form.addEventListener('submit', function(e) {
          const submitBtn = form.querySelector('button[type="submit"], input[type="submit"]');
          if (submitBtn) {
            submitBtn.dataset.originalText = submitBtn.textContent || submitBtn.value;
            loadingSystem.setButtonLoading(submitBtn, true, form.dataset.loadingText || 'Chargement...');
          }
          
          // Afficher overlay si demandé
          if (form.dataset.showOverlay === 'true') {
            loadingSystem.showOverlay(form.dataset.overlayMessage || 'Traitement en cours...');
          }
        });
      });
      
      // Gestion des erreurs de formulaire
      document.querySelectorAll('form').forEach(form => {
        form.addEventListener('submit', function(e) {
          // Reset loading state après un court délai si pas de redirection
          setTimeout(() => {
            const submitBtn = form.querySelector('button[type="submit"], input[type="submit"]');
            if (submitBtn && submitBtn.disabled) {
              loadingSystem.setButtonLoading(submitBtn, false);
              loadingSystem.hideOverlay();
            }
          }, 100);
        });
      });
    });
    
    // Exposer globalement
    window.loadingSystem = loadingSystem;

