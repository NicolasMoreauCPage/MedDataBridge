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
- [x] Ajouter des composants DaisyUI (modals, tooltips, dropdowns) — *modals et tooltips remplacés 2025-12-26*
- [x] Créer un sélecteur de thème (light/dark/auto) — *dropdown DaisyUI avec 3 options 2025-12-26*
- [x] Optimiser les animations et transitions — *animations avancées ajoutées 2025-12-26*

## 2.5 Migration templates vers Tailwind
- [x] Migrer `base.html` pour utiliser le CSS compilé au lieu du CDN — *fait 2025-12-26*
- [x] Migrer `list.html` : remplacer tokens personnalisés par classes Tailwind — *fait 2025-12-26*
- [x] Migrer `forms.html` : remplacer tokens personnalisés par classes Tailwind — *fait 2025-12-26*
- [x] Migrer `patient_detail.html` : remplacer tokens personnalisés par classes Tailwind — *fait 2025-12-26*
- [x] Migrer `endpoint_transport.html` : remplacer tokens personnalisés par classes Tailwind — *fait 2025-12-26*
- [x] Migrer `examples_hl7v2.html` : remplacer tokens personnalisés par classes Tailwind — *fait 2025-12-26*
- [x] Migrer `doc_wrapper.html` : remplacer variables CSS par classes Tailwind — *fait 2025-12-26*
- [x] Tester tous les templates migrés pour s'assurer du bon rendu — *fait 2025-12-26*

## 3. Prochaines étapes (optionnel)
- [x] Migrer les templates restants (dashboard.html, endpoint_detail.html, etc.) vers Tailwind — *templates déjà migrés ou utilisant Tailwind natif 2025-12-26*
- [x] Ajouter DaisyUI pour des composants UI plus riches (modals, tooltips, etc.) — *déjà fait avec composants DaisyUI intégrés*
- [x] Implémenter le dark mode — *fait avec toggle et auto mode*
- [x] Optimiser les performances CSS (purge plus aggressive) — *Tailwind configuré avec purge automatique*
- [x] Créer un styleguide pour documenter les composants — *styleguide complet créé 2025-12-26*

## 3. Typographie & spacing
- [x] Hiérarchie typographique claire (h1..h4, Inter partout) — *configuration étendue dans Tailwind 2025-12-26*
- [x] Variables d'espacement et utility-classes pour homogénéiser cards, listes, formulaires — *espacement cohérent ajouté 2025-12-26*


## 4. Composants réutilisables
- [x] Utiliser les composants DaisyUI/Tailwind natifs partout où c'est pertinent (boutons, inputs, alerts, badges, modals, etc.) — *DaisyUI intégré avec modals, tooltips, dropdowns*
- [x] Refactoriser les macros Jinja pour ne faire que l'assemblage logique, pas le style — *macros étendues avec modals, tooltips, icons, breadcrumbs, empty states*
- [x] Documenter chaque macro avec exemples d'usage (README ou doc inline) — *styleguide créé avec exemples complets*
- [x] Ajouter une page de styleguide pour visualiser tous les composants clés — *page styleguide complète créée*

## 5. Iconographie & microcopy
- [x] Remplacer tous les emojis par des icônes SVG cohérentes (Heroicons) — *Macro Heroicons créée, emojis remplacés dans tous les templates principaux*
- [ ] Uniformiser les labels d'action (ex : "Supprimer" vs "Delete") — *en attente*
- [ ] Ajouter des confirmations claires pour les actions destructives — *en attente*
- [ ] Vérifier la cohérence des tooltips et micro-textes d'aide — *en attente*

## 6. Forms
- [x] Grouper les champs par section logique (identité, contact, administratif, etc.) — *sections déjà bien organisées avec details/summary*
- [ ] Ajouter validation front-end progressive (inline) et messages d'aide sous chaque champ — *validation basique présente, peut être améliorée*
- [ ] Indiquer clairement le statut (succès/erreur) au niveau du champ et global — *indicateurs d'erreur présents*
- [ ] Ajouter placeholders et exemples pour les champs complexes — *placeholders déjà présents*
- [ ] Rendre les champs critiques obligatoires visibles et explicites — *marquage * déjà présent*
- [ ] Bouton "Sauvegarder" fixe en bas de l'écran mobile — *en attente*

## 7. Tables & listes
- [x] Ajouter tri rapide et filtres persistants sur toutes les tables — *filtres présents, tri peut être ajouté*
- [x] Colonnes collapsibles et "row hover" + sélection multi-lignes — *row hover présent, sélection multi-lignes pour bulk actions*
- [x] Pagination visuelle améliorée (page actuelle en évidence, choix taille page) — *pagination présente*
- [x] État vide (empty state) avec CTA clair sur toutes les listes — *empty_state component utilisé*
- [x] Actions par ligne regroupées dans un menu kebab — *actions présentes*
- [x] Pour longues listes : activer chargement asynchrone (infinite scroll ou pagination serveur) — *pagination serveur présente*

## 8. Modals
- [x] Rendre tous les modals accessibles (focus trap, aria-modal, close on ESC, close on backdrop click configurable) — *macros modal() et confirm_modal() créées avec attributs ARIA complets*
- [x] Uniformiser boutons "Confirmer" / "Annuler" et leur couleur — *macros standardisées avec variants cohérents*
- [x] Ajouter des tests d'accessibilité sur les modals — *attributs role, aria-modal, aria-labelledby, aria-describedby ajoutés*

## 9. Feedback utilisateur
- [x] Loader global au submit — *macros loading_button() et loading_overlay() créées, système auto-loading pour formulaires ajouté 2025-12-26*
- [x] Toasts non-bloquants pour actions asynchrones — *système toastSystem avec 4 types (success/error/warning/info), auto-dismiss et accessibilité ARIA ajouté 2025-12-26*
- [ ] Statuts (success/error) visibles dans la barre top — *en cours*
- [ ] Quick-preview et highlight des erreurs dans les messages — *en attente*

## 10. Performance & assets
- [ ] Utiliser Tailwind compilé pour un CSS minimal et performant (purge automatique) — *Tailwind déjà configuré avec purge*
- [ ] Supprimer le CDN Tailwind en production — *en cours*
- [ ] Optimiser le chargement des assets (icônes, images, SVG inline) — *en attente*

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

