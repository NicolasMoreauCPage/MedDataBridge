# TODO Refonte UI/UX MedData Bridge

Branche de travail : `uxui-restart-2025-12-26`

Ce fichier suit la progression détaillée de la refonte UI/UX basée sur l'audit du 26/12/2025.

## 1. Quick wins (priorité immédiate)
- [x] Centraliser les macros UI dans `components.html` (boutons, alerts, badges, modals) — *fait 2025-12-26, cf. branche uxui-restart-2025-12-26*
- [x] Refactoriser tous les boutons/alerts pour utiliser ces macros — *fait 2025-12-26, cf. branche uxui-restart-2025-12-26*
- [x] Ajouter un état vide + CTA sur toutes les listes principales — *fait 2025-12-26, cf. branche uxui-restart-2025-12-26*

## 2. Design system maintenable (standard)
- [x] Installer Tailwind CSS en mode build (purge, config locale, pas de CDN) — *fait 2025-12-26*
- [x] Ajouter DaisyUI (ou une autre librairie UI compatible Tailwind) pour accélérer la création de composants accessibles et cohérents — *fait 2025-12-26*
- [x] Nettoyer les tokens CSS maison pour ne garder que les overrides nécessaires (branding, dark mode, etc.) — *fait 2025-12-26*
- [x] Documenter la palette et la typographie dans la config Tailwind — *fait 2025-12-26*
- [x] Préparer le support dark mode via Tailwind et DaisyUI — *implémentation complète avec toggle faite 2025-12-26*

## 3. Améliorations UI/UX avancées
- [x] Implémenter le dark mode complet avec toggle — *fait 2025-12-26*
- [ ] Ajouter des composants DaisyUI (modals, tooltips, dropdowns)
- [ ] Créer un sélecteur de thème (light/dark/auto)
- [ ] Optimiser les animations et transitions

## 2.5 Migration templates vers Tailwind
- [x] Migrer `base.html` pour utiliser le CSS compilé au lieu du CDN — *fait 2025-12-26*
- [x] Migrer `list.html` : remplacer tokens personnalisés par classes Tailwind — *fait 2025-12-26*
- [x] Migrer `forms.html` : remplacer tokens personnalisés par classes Tailwind — *fait 2025-12-26*
- [x] Migrer `patient_detail.html` : remplacer tokens personnalisés par classes Tailwind — *fait 2025-12-26*
- [x] Migrer `endpoint_transport.html` : remplacer tokens personnalisés par classes Tailwind — *fait 2025-12-26*
- [x] Migrer `examples_hl7v2.html` : remplacer tokens personnalisés par classes Tailwind — *fait 2025-12-26*
- [x] Tester tous les templates migrés pour s'assurer du bon rendu — *fait 2025-12-26*

## 3. Prochaines étapes (optionnel)
- [ ] Migrer les templates restants (dashboard.html, endpoint_detail.html, etc.) vers Tailwind
- [ ] Ajouter DaisyUI pour des composants UI plus riches (modals, tooltips, etc.)
- [ ] Implémenter le dark mode
- [ ] Optimiser les performances CSS (purge plus aggressive)
- [ ] Créer un styleguide pour documenter les composants

## 3. Typographie & spacing
- [ ] Hiérarchie typographique claire (h1..h4, Inter partout)
- [ ] Variables d’espacement et utility-classes pour homogénéiser cards, listes, formulaires


## 4. Composants réutilisables
- Utiliser les composants DaisyUI/Tailwind natifs partout où c’est pertinent (boutons, inputs, alerts, badges, modals, etc.).
- Refactoriser les macros Jinja pour ne faire que l’assemblage logique, pas le style.
- Documenter chaque macro avec exemples d’usage (README ou doc inline).
- Ajouter une page de styleguide pour visualiser tous les composants clés.

## 5. Iconographie & microcopy
- Remplacer tous les emojis par des icônes SVG cohérentes (Heroicons).
- Uniformiser les labels d’action (ex : "Supprimer" vs "Delete").
- Ajouter des confirmations claires pour les actions destructives.
- Vérifier la cohérence des tooltips et micro-textes d’aide.

## 6. Forms
- Grouper les champs par section logique (identité, contact, administratif, etc.).
- Ajouter validation front-end progressive (inline) et messages d’aide sous chaque champ.
- Indiquer clairement le statut (succès/erreur) au niveau du champ et global.
- Ajouter placeholders et exemples pour les champs complexes.
- Rendre les champs critiques obligatoires visibles et explicites.
- Bouton "Sauvegarder" fixe en bas de l’écran mobile.

## 7. Tables & listes
- Ajouter tri rapide et filtres persistants sur toutes les tables.
- Colonnes collapsibles et "row hover" + sélection multi-lignes.
- Pagination visuelle améliorée (page actuelle en évidence, choix taille page).
- État vide (empty state) avec CTA clair sur toutes les listes.
- Actions par ligne regroupées dans un menu kebab.
- Pour longues listes : activer chargement asynchrone (infinite scroll ou pagination serveur).

## 8. Modals
- Rendre tous les modals accessibles (focus trap, aria-modal, close on ESC, close on backdrop click configurable).
- Uniformiser boutons "Confirmer" / "Annuler" et leur couleur.
- Ajouter des tests d’accessibilité sur les modals.

## 9. Feedback utilisateur
- Loader global au submit.
- Toasts non-bloquants pour actions asynchrones.
- Statuts (success/error) visibles dans la barre top.
- Quick-preview et highlight des erreurs dans les messages.

## 10. Performance & assets
- Utiliser Tailwind compilé pour un CSS minimal et performant (purge automatique).
- Supprimer le CDN Tailwind en production.
- Optimiser le chargement des assets (icônes, images, SVG inline).

## 11. Accessibilité
- Ajouter `role`, `aria-*` sur tous les composants interactifs.
- Vérifier le contraste des couleurs (AA minimal).
- Focus-visible personnalisé et navigation clavier sur tous les menus/modals.
- Labels associés aux `input` via `for`/`id`.
- S’assurer que le skip-link fonctionne et que la navigation clavier est fluide.


Chaque point sera coché et daté à mesure de l’avancement, avec liens vers les commits associés.

Dernière mise à jour : 26/12/2025
5. Refactorer toute la palette/couleurs : remplacer toutes les classes Tailwind de couleur par des utilitaires basés sur les tokens CSS (bg-accent, text-accent, border-theme, etc.) dans tous les templates (étape 1 : base.html) ✅ (26/12/2025)
6. Refonte palette/tokens appliquée à tous les templates principaux (list.html, forms.html, tables, détails, navigation, etc.) ✅ (26/12/2025)

7. Prochaine étape : composants réutilisables (vérifier l’usage systématique des macros, factoriser les patterns restants, documenter et tester visuellement chaque composant clé)

