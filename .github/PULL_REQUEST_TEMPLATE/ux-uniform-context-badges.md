### Objectif
Uniformiser l'affichage des indications "Contexte requis" / "EJ requis" dans les templates en utilisant la macro `components.context_badge`.

### Changements
- Ajout de la macro `context_badge` dans `app/templates/components.html`.
- Remplacement des occurrences pertinentes dans `app/templates/base.html` et `mobile menu` pour utiliser la macro.
- Propagation de l'import + usage dans `deployment/general/app/templates/base.html` et `deployment/postgresql/app/templates/base.html`.
- Ajout d'une page interne `/menu` listant la structure du menu (router + template).

### Vérification
- Démarrer l'app en local et vérifier l'apparence sur `/menu` et la barre de navigation.
- Tester sur mobile (ou réduire la fenêtre) que le badge apparaît aussi dans le menu mobile.

### Notes
Aucun changement fonctionnel attendu ; uniquement une harmonisation visuelle.
