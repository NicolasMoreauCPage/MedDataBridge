# Mise en œuvre — refonte front et UX

Date : 13 septembre 2026  
Référence : [plan de refonte](PLAN_REFONTE_FRONT_UX_20260913.md)

## Livré dans ce lot

- Le shell empêche désormais tout débordement horizontal du document. Les
  tableaux gardent, si nécessaire, leur propre défilement horizontal.
- Les listes Scénarios, Messages et Dossiers sont paginées à 50 éléments par
  défaut. Les filtres et la taille de page sont conservés dans les liens de
  pagination.
- Les calculs coûteux de comptage d'actes des dossiers ne sont réalisés que
  pour les dossiers de la page affichée.
- Les en-têtes, barres d'actions et la vue Structure passent en colonne ou
  reviennent à la ligne sur petit écran.
- La validation possède des onglets clavier accessibles, sans gestionnaire
  d'événement inline. Son script est chargé seulement sur cet atelier.
- Le détail d'un scénario est un poste de travail responsive :
  - les étapes sont présentées en cartes sur mobile ;
  - le payload HL7/XML/JSON conserve ses vrais retours à la ligne ;
  - chaque carte permet la consultation, le déplacement, la suppression et
    l'édition du payload ;
  - la table complète est conservée pour les grands écrans ;
  - l'envoi asynchrone et le timing réaliste sont isolés dans un module ;
  - la prévisualisation suit de nouveau son flux HTML normal.
- Les confirmations communes reposent sur un dialogue natif accessible et les
  principales erreurs de liste utilisent les notifications de l'application,
  plutôt que les boîtes de dialogue natives.
- La reprise planifiée des campagnes de qualification est réparée : elle trie
  désormais les exécutions sur `started_at`, champ réellement persisté, au
  lieu d'un champ inexistant.
- Le shell propose désormais une palette de commandes (bouton ou
  `Ctrl+K`) pour ouvrir directement les ateliers et leur documentation.
- Le script d'édition de la structure interactive n'est plus chargé par toutes
  les pages : il est limité à son atelier, avec un test de non-régression.
- Le catalogue de macros ne définit plus deux fois le même composant modal.
- Les catalogues utilisent un module partagé pour les filtres, raccourcis,
  lignes activables, pagination, exécution groupée et suppression confirmée,
  sans gestionnaire JavaScript inline.
- La supervision des messages et la vue par dossier utilisent un module dédié
  pour le rejeu et l'affichage des cotations. Les requêtes de cotations sont
  limitées à quatre simultanées afin de préserver la réactivité des grandes
  listes.
- La vue par dossier est paginée après regroupement : chaque page contient des
  dossiers complets, et les compteurs restent calculés sur tout le résultat
  filtré, pas seulement sur la page affichée.
- Les suppressions de patient, dossier, venue, mouvement et endpoint utilisent
  désormais le dialogue de confirmation commun au lieu des confirmations
  natives du navigateur.

## Contrôles réalisés

- rendu navigateur à 390 × 844 pour tableau de bord, scénarios, détail de
  scénario, messages, validation, dossiers, endpoints et structure ;
- aucune de ces pages n'élargit le document au-delà de 390 px ;
- navigation au clavier des onglets de validation ;
- tests unitaires de routage Scénarios, Messages et Dossiers ;
- compilation Python, contrôle Ruff et contrôle des espaces Git.

La nouvelle suite Playwright
`tests/e2e/test_front_responsive.py` verrouille le reflow des quatre ateliers
prioritaires et l'interaction clavier de la validation.

## Restant pour la convergence complète

Le présent lot couvre le lot 0 du plan et une partie des fondations. Restent
notamment la simplification complète du très grand layout historique, la
consolidation de toutes les macros Jinja, la suppression systématique des
scripts inline sur les pages moins prioritaires, le nouveau sélecteur de
contexte et l'atelier complet de validation avec éditeur spécialisé. Ces sujets
sont volontairement gardés dans des lots
distincts afin de ne pas fragiliser les parcours d'émission existants.
