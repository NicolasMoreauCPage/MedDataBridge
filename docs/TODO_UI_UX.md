# TODO Refonte UI/UX MedData Bridge

Branche de travail : `uxui-restart-2025-12-26`

Ce fichier suit la progression détaillée de la refonte UI/UX basée sur l'audit du 26/12/2025.

## 1. Quick wins (priorité immédiate)
- [x] Centraliser les macros UI dans `components.html` (boutons, alerts, badges, modals) — *fait 2025-12-26, cf. branche uxui-restart-2025-12-26*
- [x] Refactoriser tous les boutons/alerts pour utiliser ces macros — *fait 2025-12-26, cf. branche uxui-restart-2025-12-26*
- [x] Ajouter un état vide + CTA sur toutes les listes principales — *fait 2025-12-26, cf. branche uxui-restart-2025-12-26*

## 2. Design tokens & palette
- [ ] Définir une palette officielle et variables CSS dans `vars.css`
- [ ] Extraire tous les tokens (couleurs, radius, spacing) dans un seul fichier
- [ ] Préparer le support dark mode (structure CSS)

## 3. Typographie & spacing
- [ ] Hiérarchie typographique claire (h1..h4, Inter partout)
- [ ] Variables d’espacement et utility-classes pour homogénéiser cards, listes, formulaires


## 4. Composants réutilisables
- Centraliser tous les composants UI (boutons, inputs, alerts, badges, table rows, modals) dans `components.html` (macros Jinja).
- Refactoriser tous les templates pour utiliser ces macros systématiquement.
- Documenter chaque macro avec exemples d’usage.
- Ajouter des tests visuels pour chaque composant clé.

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
- Passer Tailwind en build (purge) pour réduire le poids du CSS.
- Limiter la config CDN runtime en production.
- Compiler les CSS utilitaires.
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

