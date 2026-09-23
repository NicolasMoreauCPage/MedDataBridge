/* Application du thème avant le premier rendu. */
"use strict";

// Pré-flight theme: appliquer le thème stocké (ou auto) avant le rendu
(function(){
  try {
    const saved = localStorage.getItem('theme') || 'auto';
    const html = document.documentElement;
    function applyTheme(t) {
      if (t === 'auto') {
        const prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
        if (prefersDark) {
          html.classList.add('dark');
          html.setAttribute('data-theme', 'dark');
        } else {
          html.classList.remove('dark');
          html.setAttribute('data-theme', 'light');
        }
      } else if (t === 'dark') {
        html.classList.add('dark');
        html.setAttribute('data-theme', 'dark');
      } else {
        html.classList.remove('dark');
        html.setAttribute('data-theme', 'light');
      }
    }
    applyTheme(saved);
  } catch (e) {
    // defensive: ne pas empêcher le rendu si localStorage n'est pas disponible
  }
})();
