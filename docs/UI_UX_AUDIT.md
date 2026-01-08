# Audit UI / UX — Recommandations

Date: 26/12/2025

Ce document résume l'audit des interfaces (templates + composants) et liste des pistes d'amélioration concrètes, priorisées et actionnables.

Principales pages analysées (exemples) :
- [app/templates/base.html](app/templates/base.html)
- [app/templates/list.html](app/templates/list.html)
- [app/templates/forms.html](app/templates/forms.html)
- [app/templates/components.html](app/templates/components.html)
- [app/templates/patient_detail.html](app/templates/patient_detail.html)
- [app/templates/dossier_detail.html](app/templates/dossier_detail.html)
- [app/templates/hprim_cotation.html](app/templates/hprim_cotation.html)
- [app/templates/scenario_detail.html](app/templates/scenario_detail.html)
- [app/templates/messages.html](app/templates/messages.html)
- [app/templates/endpoint_detail.html](app/templates/endpoint_detail.html)

**Résumé rapide**
- L'application dispose d'une base solide : design system simple (Tailwind via CDN), composants réutilisables, macros Jinja pour pagination/modals.
- Opportunités majeures : cohérence visuelle, formulaires lourds, tables denses, feedbacks action utilisateur insuffisants, accessibilité à renforcer, performance JS/CSS pour pages lourdes.

**Recommandations globales (UI)**
- **Palette & Typographie:** définir une palette officielle et variables CSS dans `app/static/css/vars.css` et aligner la hiérarchie typographique (h1..h4). Utiliser Inter pour titres + système de taille modulable.
- **Spacing System:** introduire variables d'espacement (xxs..xl) et utility-classes pour `gap` et `padding` afin d'homogénéiser les cartes, listes et formulaires.
- **Composants réutilisables:** centraliser boutons, inputs, alerts, badges, table rows, modals dans `components.html` (macros) et utiliser systématiquement.
- **Design tokens & dark mode:** extraire les couleurs et tokens depuis `:root` déjà présent dans `base.html` vers un fichier unique et documenté.
- **Iconographie & microcopy:** remplacer emoji inconsistants par icônes SVG cohérentes (Heroicons), uniformiser labels d'action (Ex: `Supprimer` vs `Delete`) et ajouter confirmations claires.

**Recommandations globales (UX)**
- **Forms:** grouper les champs, indiquer clairement le statut (succès/erreur) au niveau du champ et global; ajouter placeholders et examples; rendre les champs critiques obligatoires visibles.
- **Tables:** ajouter tri expéditif, filtres persistants, colonnes collapsibles, et « row hover » + sélection multi-lignes. Pour longues listes, activer chargement asynchrone (infinite scroll ou pagination serveur propre).
- **Modals:** rendre accessibles (focus trap, aria-modal, close on ESC, close on backdrop click configurable). Uniformiser boutons `Confirmer` / `Annuler` et leur couleur.
- **Feedback & Loading:** loader global au submit, toasts non-bloquants pour actions asynchrones, statuts (success/error) visibles dans la barre top.
- **Performance & Assets:** passer Tailwind en build (purge) pour réduire poids, limiter CDN runtime config en prod, compiler CSS utilitaires.

**Accessibilité (A11y)**
- Ajouter `role`, `aria-*` sur composants interactifs, vérifier color-contrast (AA minimal), focus-visible personnalisé, labels associés aux `input` via `for`/`id`.
- Keyboard navigation: s'assurer que modals et menus sont accessibles au clavier et que le skip-link fonctionne.

**Recommandations par écran (extraits)**

- **Navigation principale — [app/templates/base.html](app/templates/base.html)**
  - Simplifier les mega-menus : limiter leur largeur, augmenter le contraste des liens, et améliorer l'agrégation visuelle (séparer visuellement sections et CTA). Puis rendre la version mobile plus compacte (drawer minimal).
  - Rendre les badges contextuels (contexte EJ/patient) cliquables et affichant une info-synthèse (tooltip ou mini-card) au hover/tap.

- **Listes génériques — [app/templates/list.html](app/templates/list.html)**
  - Introduire un état vide (empty state) avec CTA clair.
  - Améliorer la pagination visuelle (page actuelle en évidence) et ajouter possibilité de changer la taille de page (25/50/100).
  - Actions par ligne: regrouper dans un menu kebab pour réduire le bruit et préserver l'espace colonne.

- **Formulaires — [app/templates/forms.html](app/templates/forms.html) & patient_form.html**
  - Ajouter validation front-end progressive (inline) et messages d'aide succincts sous chaque champ.
  - Regrouper les sections (identité / contact / administratif) avec accordéons pour réduire la hauteur initiale.
  - Bouton `Sauvegarder` fixe en bas de l'écran mobile pour éviter scroll long.

- **Détail patient / dossier — [app/templates/patient_detail.html](app/templates/patient_detail.html) & [app/templates/dossier_detail.html](app/templates/dossier_detail.html)**
  - Mettre en avant les actions fréquentes (créer dossier, ajouter mouvement) comme primary CTA en haut à droite.
  - Résumé synthétique (card) en haut avec metrics clés (nb dossiers, dernières venues, statut) pour une lecture rapide.
  - Historique & timeline: rendre scrollable horizontalement ou via accordéons chronologiques.

- **Cotation HPRIM — [app/templates/hprim_cotation.html](app/templates/hprim_cotation.html)**
  - Modal de sélection d'acte: ajouter recherche instantanée, catégories, et keyboard navigation.
  - Rendre l'ajout d'acte non bloquant (toasts) et permettre édition in-place.

- **Scénarios & Génération — [app/templates/scenario_detail.html](app/templates/scenario_detail.html) / test_scenario_generator.html**
  - Clarifier état de l'exécution (en file d'attente / running / terminé) via pill/status coloré.
  - Workflow d'exécution: confirmations et estimations de durée pour éviter clics répétés.

- **Messages & Rejets — [app/templates/messages.html](app/templates/messages.html) & messages_rejections.html**
  - Filtrage multi-critères, sauvegarde de filtres, et quick-preview (hover ou modal) des messages, avec highlight des erreurs.
  - Ajouter action bulk pour marquer/archiver/retransmettre.

- **Endpoints / Transport — [app/templates/endpoint_detail.html](app/templates/endpoint_detail.html)**
  - Mettre les actions critiques (restart/start/stop) dans une zone séparée avec confirmations explicites et couleurs (danger pour delete).
  - Show health/status with timestamp and last log snippet, and quick test button opening an async job with toasts.

**Quick Wins (1-2 jours)**
- Centraliser les macros `components.html` et refactoriser usage boutons/alerts.
- Ajouter état vide + CTA pour listes principales.
- Uniformiser couleurs des boutons (primary/secondary/danger) et apply to all templates.
- Add focus-visible and contrast adjustments.

**Projets moyen/long terme (2-4 semaines)**
- Mettre en place un design system minimal (tokens + Tailwind build), créer `app/static/css/ui-redesign.css` et migrer progressivement.
- Remodeler les formulaires critiques en groupes accordéon et validation progressive.
- Implémenter pagination asynchrone et filtres sauvegardés pour listes lourdes.

**KPIs & Tests utilisateur**
- Mesurer temps moyen pour créer un dossier, nombre d'erreurs de validation, taux d'utilisation des actions principales.
- Faire 5 tests utilisateur modérés (scénarios clé: créer patient + dossier, rechercher un message rejeté, lancer un scénario) et collecter feedbacks.

**Prochaines étapes recommandées**
1. Implémenter les Quick Wins sur la branche `feature/ui-redesign` (déjà créée).
2. Ajouter `app/static/css/ui-redesign.css` (squelette) et modifier `base.html` pour l'inclure en local pour tests.
3. Refactor des macros dans `app/templates/components.html` (boutons/inputs/modals/pagination).
4. Déployer une PR minimaliste et tester manuellement sur un env local.

Pour toute action détaillée (patches ou prototype), je peux créer les fichiers initiaux et implémenter les Quick Wins — veux-tu que je commence par générer `app/static/css/ui-redesign.css` et refactoriser `components.html` pour normaliser boutons et modals ?
