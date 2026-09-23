# Catalogue de composants UI

Ce catalogue est la référence pour les nouveaux templates PAMélia. Les styles
locaux dans un bloc `<style>` ne sont pas autorisés ; une exception historique
doit être migrée ou ajoutée explicitement au contrôle frontend.

| Besoin | Implémentation recommandée | Référence |
| --- | --- | --- |
| Formulaire et erreurs | macros `input`, `textarea`, `select` et classes de `forms.css`; ajouter `data-guard-unsaved` aux formulaires à risque | `templates/macros/ui.html`, `static/css/forms.css` |
| Tableau | conteneur `ui-table-shell` puis table Tailwind avec en-tête et état vide `empty_state` | `templates/macros/ui.html` |
| Badge d'état | macro `badge` ou `message_status_badge` pour les messages | `templates/macros/ui.html` |
| Retour utilisateur | `window.toastSystem.show(message, type)` et le conteneur de toast partagé | `static/js/notifications.js` |
| Modale | macro `modal` ou `confirm_modal`, avec titre et déclencheur qui récupère le focus | `templates/macros/ui.html` |
| État vide / chargement | macros `empty_state`, `loading_state` et `spinner` | `templates/macros/ui.html` |
| Variante d'espace de travail | classe préfixée par domaine (`analytics-*`, `hprim-*`, `cotations-list-*`) dans `design-system.css` | `static/css/design-system.css` |

Les routes `/styleguide` et `/design-system` sont des références internes de
développement : elles ne doivent pas figurer dans la navigation utilisateur ni
servir de parcours métier. Toute nouvelle variante est documentée ici, utilise
un préfixe de domaine et est validée en thème clair/sombre ainsi qu'en largeur
mobile et desktop dans le job navigateur de CI.
