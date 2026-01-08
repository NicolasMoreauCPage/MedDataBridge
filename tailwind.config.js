/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./app/templates/**/*.html",
    "./app/static/js/**/*.js",
    "./app/static/css/**/*.css",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      // PALETTE DE COULEURS - MedData Bridge
      // ====================================
      // Primary: Bleu professionnel pour les accents, boutons, liens
      // Utilisation: bg-blue-600, text-blue-600, border-blue-600
      colors: {
        primary: {
          50: '#eff6ff',  // Très clair - backgrounds subtils
          100: '#dbeafe', // Clair - hover states
          200: '#bfdbfe', // Light - borders légers
          300: '#93c5fd', // Medium-light - éléments secondaires
          400: '#60a5fa', // Medium - focus states
          500: '#3b82f6', // Standard - éléments actifs
          600: '#2563eb', // Dark - boutons principaux, headers
          700: '#1d4ed8', // Darker - hover states
          800: '#1e40af', // Très dark - textes sur fond clair
          900: '#1e3a8a', // Ultra dark - contrastes élevés
        },
        // Secondary: Gris neutres pour le texte et les backgrounds
        // Utilisation: text-gray-600, bg-gray-50, border-gray-200
        secondary: {
          50: '#f8fafc',  // Très clair - page background
          100: '#f1f5f9', // Clair - card backgrounds
          200: '#e2e8f0', // Light - table headers, borders
          300: '#cbd5e1', // Medium-light - dividers
          400: '#94a3b8', // Medium - text muted
          500: '#64748b', // Standard - text secondary
          600: '#475569', // Dark - text primary
          700: '#334155', // Darker - headings
          800: '#1e293b', // Très dark - high contrast
          900: '#0f172a', // Ultra dark - dark theme base
        },
      },

      // TYPOGRAPHIE
      // ===========
      // Police principale: Inter (Google Fonts)
      // Utilisation: font-sans (défaut)
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'Monaco', 'Cascadia Code', 'monospace'],
      },

      // Hiérarchie typographique claire
      fontSize: {
        'xs': ['0.75rem', { lineHeight: '1rem' }],      // 12px - labels, captions
        'sm': ['0.875rem', { lineHeight: '1.25rem' }],   // 14px - body small
        'base': ['1rem', { lineHeight: '1.5rem' }],      // 16px - body standard
        'lg': ['1.125rem', { lineHeight: '1.75rem' }],   // 18px - body large
        'xl': ['1.25rem', { lineHeight: '1.75rem' }],    // 20px - headings small
        '2xl': ['1.5rem', { lineHeight: '2rem' }],       // 24px - headings medium
        '3xl': ['1.875rem', { lineHeight: '2.25rem' }],  // 30px - headings large
        '4xl': ['2.25rem', { lineHeight: '2.5rem' }],    // 36px - headings extra large
        '5xl': ['3rem', { lineHeight: '1' }],            // 48px - hero headings
        '6xl': ['3.75rem', { lineHeight: '1' }],         // 60px - mega headings
      },

      // Espacement typographique cohérent
      spacing: {
        '18': '4.5rem',  // Pour les grandes sections
        '88': '22rem',   // Pour les sidebars larges
      },

      // ANIMATIONS (héritées du système précédent)
      // =========================================
      // Maintenues pour compatibilité avec animations existantes
      animation: {
        'fadeIn': 'fadeIn 200ms ease-in',
        'slideIn': 'slideIn 200ms ease-out',
        'fade-in': 'fadeIn 300ms ease-out',
        'slide-up': 'slideUp 400ms cubic-bezier(0.16, 1, 0.3, 1)',
        'scale-in': 'scaleIn 250ms ease-out',
        'bounce-in': 'bounceIn 500ms cubic-bezier(0.68, -0.55, 0.265, 1.55)',
        'page-enter': 'pageEnter 400ms cubic-bezier(0.16, 1, 0.3, 1)',
        'page-exit': 'pageExit 300ms cubic-bezier(0.4, 0, 1, 1)',
        // Nouvelles animations optimisées
        'stagger-1': 'fadeIn 400ms ease-out 100ms both',
        'stagger-2': 'fadeIn 400ms ease-out 200ms both',
        'stagger-3': 'fadeIn 400ms ease-out 300ms both',
        'stagger-4': 'fadeIn 400ms ease-out 400ms both',
        'stagger-5': 'fadeIn 400ms ease-out 500ms both',
        'micro-bounce': 'microBounce 600ms cubic-bezier(0.68, -0.55, 0.265, 1.55)',
        'smooth-slide': 'smoothSlide 300ms cubic-bezier(0.4, 0, 0.2, 1)',
        'gentle-fade': 'gentleFade 500ms ease-out',
        'loading-dots': 'loadingDots 1.4s ease-in-out infinite both',
      },
      keyframes: {
        fadeIn: { '0%': { opacity: '0' }, '100%': { opacity: '1' } },
        slideIn: { '0%': { transform: 'translateX(-10px)', opacity: '0' }, '100%': { transform: 'translateX(0)', opacity: '1' } },
        slideUp: { '0%': { transform: 'translateY(20px)', opacity: '0' }, '100%': { transform: 'translateY(0)', opacity: '1' } },
        scaleIn: { '0%': { transform: 'scale(0.95)', opacity: '0' }, '100%': { transform: 'scale(1)', opacity: '1' } },
        bounceIn: { '0%': { transform: 'scale(0.3)', opacity: '0' }, '50%': { transform: 'scale(1.05)' }, '70%': { transform: 'scale(0.9)' }, '100%': { transform: 'scale(1)', opacity: '1' } },
        pageEnter: { '0%': { transform: 'translateY(8px)', opacity: '0' }, '100%': { transform: 'translateY(0)', opacity: '1' } },
        pageExit: { '0%': { transform: 'translateY(0)', opacity: '1' }, '100%': { transform: 'translateY(-8px)', opacity: '0' } },
        // Nouvelles keyframes optimisées
        microBounce: { '0%': { transform: 'scale(1)' }, '50%': { transform: 'scale(1.05)' }, '100%': { transform: 'scale(1)' } },
        smoothSlide: { '0%': { transform: 'translateX(-100%)' }, '100%': { transform: 'translateX(0)' } },
        gentleFade: { '0%': { opacity: '0', transform: 'translateY(10px)' }, '100%': { opacity: '1', transform: 'translateY(0)' } },
        loadingDots: {
          '0%, 80%, 100%': { transform: 'scale(0)' },
          '40%': { transform: 'scale(1)' }
        },
      },

      // TRANSITIONS ET ANIMATIONS UTILITAIRES
      // ======================================
      // Transitions fluides pour les interactions
      transition: {
        'colors': 'color, background-color, border-color, text-decoration-color, fill, stroke 200ms ease-in-out',
        'opacity': 'opacity 150ms ease-in-out',
        'transform': 'transform 200ms cubic-bezier(0.4, 0, 0.2, 1)',
        'all': 'all 300ms cubic-bezier(0.4, 0, 0.2, 1)',
        'smooth': 'all 400ms cubic-bezier(0.25, 0.46, 0.45, 0.94)',
        'bounce': 'all 500ms cubic-bezier(0.68, -0.55, 0.265, 1.55)',
      },
      // Classes utilitaires pour les animations
      animationDelay: {
        '100': '100ms',
        '200': '200ms',
        '300': '300ms',
        '400': '400ms',
        '500': '500ms',
        '1000': '1000ms',
      },
      animationDuration: {
        '75': '75ms',
        '100': '100ms',
        '150': '150ms',
        '200': '200ms',
        '300': '300ms',
        '500': '500ms',
        '700': '700ms',
        '1000': '1000ms',
      },
    },
  },
  plugins: [
    require('daisyui'),
  ],

  // DAISYUI CONFIGURATION
  // =====================
  // Composants UI prédéfinis et accessibles
  daisyui: {
    themes: [
      'light',  // Thème clair par défaut
      'dark',   // Thème sombre (à implémenter)
    ],
    darkTheme: 'dark',
  },
}