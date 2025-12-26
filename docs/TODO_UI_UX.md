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
- [ ] Centraliser inputs, alerts, badges, table rows, modals dans `components.html`
- [ ] Utiliser ces macros partout (progressif)

## 5. Iconographie & microcopy
- [ ] Remplacer emojis par icônes SVG cohérentes (Heroicons)
- [ ] Uniformiser les labels d’action (ex: Supprimer vs Delete)

## 6. Forms
- [ ] Grouper les champs, feedback inline, placeholders, champs obligatoires visibles
- [ ] Validation front progressive et messages d’aide succincts
- [ ] Bouton Sauvegarder fixe en bas sur mobile

## 7. Tables & listes
- [ ] Tri, filtres, colonnes collapsibles, row hover, sélection multi-lignes
- [ ] Pagination améliorée (taille de page, page actuelle en évidence)

## 8. Modals
- [ ] Accessibilité (focus trap, aria-modal), boutons uniformes, close on ESC

## 9. Feedback utilisateur
- [ ] Loader global, toasts non-bloquants, statuts visibles

## 10. Performance & assets
- [ ] Passer Tailwind en build (purge), compiler CSS utilitaires

## 11. Accessibilité
- [ ] Rôles/aria, color-contrast, focus-visible, navigation clavier

---

Chaque point sera coché et daté à mesure de l’avancement, avec liens vers les commits associés.

Dernière mise à jour : 26/12/2025
