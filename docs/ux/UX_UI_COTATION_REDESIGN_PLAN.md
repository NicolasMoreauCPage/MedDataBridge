# Refonte UX/UI Cotation HPRIM – Plan d’action et recommandations

## 1. Ergonomie et accessibilité

- Labels toujours visibles, jamais dans le placeholder
- Aide contextuelle (icône info ou tooltip sur chaque champ complexe)
- Validation en temps réel sous chaque champ (feedback immédiat)
- Navigation clavier optimisée (tabulation logique, focus visible)
- Contrastes vérifiés (accessibilité WCAG)

## 2. Modernisation UI

- Design system cohérent (espacements, couleurs, arrondis, tailles)
- Composants réutilisables (macros Jinja ou modules JS)
- Feedback visuel (loader, transitions, animations)
- Affichage des actes : tableau responsive ou cartes, drag & drop pour réordonner

## 3. Expérience utilisateur

- Recherche intelligente d’actes (autocomplete, suggestions, historique)
- Gestion des modificateurs : boutons toggle, validation stricte, suppression rapide
- Résumé dynamique (montant total, nombre d’actes, synthèse avant émission)
- Notifications toasts pour succès/erreur, confirmation d’envoi

## 4. Responsive et mobile

- Disposition mobile-first (une colonne, boutons larges, modals plein écran)
- Actions flottantes (bouton “Ajouter acte” sticky)

## 5. Code et maintenance

- Séparation JS/HTML, modules JS dédiés, hooks si migration React/Vue
- Tests UI automatisés (saisie, validation, envoi, erreurs)

---

## Exemple de composant “Acte” moderne (HTML/CSS/JS)

```html
<div class="card acte-card flex flex-col gap-2 p-4 rounded-xl shadow-md border border-slate-200 bg-white">
  <div class="flex items-center justify-between">
    <div>
      <span class="font-bold text-indigo-700">{{ acte.code_acte }}</span>
      <span class="text-xs text-gray-500 ml-2">{{ acte.date_execution | date }}</span>
    </div>
    <div class="flex gap-2">
      <button class="btn-icon" aria-label="Éditer"><i class="fas fa-edit"></i></button>
      <button class="btn-icon text-red-600" aria-label="Supprimer"><i class="fas fa-trash"></i></button>
    </div>
  </div>
  <div class="flex flex-wrap gap-2 mt-2">
    <span class="badge">{{ acte.quantite }}x</span>
    <span class="badge">{{ acte.montant }} €</span>
    <span class="badge" v-for="mod in acte.modificateurs">{{ mod }}</span>
  </div>
  <div class="text-sm text-gray-600 mt-1">{{ acte.commentaire }}</div>
</div>
```

---

## Macro Jinja pour champ formulaire accessible

```jinja
{% macro input_field(name, label, value='', type='text', required=False, help='', error='') %}
<div class="mb-4">
  <label for="{{ name }}" class="block text-sm font-medium text-slate-700">
    {{ label }}{% if required %}<span class="text-red-500">*</span>{% endif %}
    {% if help %}<span class="ml-1 text-xs text-slate-400" title="{{ help }}">&#9432;</span>{% endif %}
  </label>
  <input type="{{ type }}" id="{{ name }}" name="{{ name }}" value="{{ value }}"
         class="block w-full rounded-xl border-2 border-slate-300 px-4 py-3 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 {% if error %}border-red-500{% endif %}"
         {% if required %}required{% endif %} aria-invalid="{{ 'true' if error else 'false' }}">
  {% if error %}<p class="text-xs text-red-500 mt-1">{{ error }}</p>{% endif %}
</div>
{% endmacro %}
```

---

## Suggestions d’architecture JS
- Un module `cotationForm.js` dédié pour la gestion dynamique des actes, modificateurs, validation, feedback.
- Utilisation de fetch/async pour les appels API, gestion centralisée des erreurs.
- Extraction des composants modaux, toasts, loader en modules réutilisables.

---

## Prototypage et tests
- Prototyper la nouvelle IHM sur Figma (ou Penpot) pour valider les parcours.
- Recueillir le feedback utilisateurs métiers avant dev.
- Intégrer des tests utilisateurs (parcours, erreurs, rapidité).

---

**Pour la mise en œuvre : je peux générer le HTML/CSS/JS d’un composant ou d’un écran complet, ou fournir une maquette Figma sur demande.**
