# Contrôles d'accessibilité WCAG 2.1 AA

La cible de ce dépôt est le socle **WCAG 2.1 niveau AA**, en préparation d'un
audit RGAA distinct. Le contrôle automatisé ne vaut pas déclaration de
conformité : il empêche les régressions détectables et complète la revue
manuelle.

## Parcours automatisés

`tests/e2e/test_accessibility_axe.py` démarre l'application de test et injecte
`axe-core` dans Chromium. Les parcours contrôlés sont :

- `/scenarios/new` — création de scénario ;
- `/structure/wizard` — création de structure ;
- `/validation` — poste de validation.

Seules les règles Axe portant les tags `wcag2a` et `wcag2aa` sont évaluées. Une
violation d'impact `critical` ou `serious` échoue le job. Le même test vérifie
que le premier élément atteint au clavier possède un focus visible.

Dernière exécution complète : **23 septembre 2026 — 6 contrôles réussis**.

Exécution locale :

```bash
npm ci
.venv/bin/python -m pytest tests/e2e/test_accessibility_axe.py -q
```

## Revue manuelle à chaque évolution IHM

- parcourir l'écran au clavier uniquement (`Tab`, `Maj+Tab`, `Entrée`,
  `Espace`, `Échap` et flèches lorsque nécessaire) ;
- vérifier l'ouverture, la fermeture et le retour de focus des modales ;
- provoquer une erreur de formulaire et confirmer l'annonce, le résumé et le
  lien vers le champ ;
- vérifier qu'un état de chargement, succès ou erreur est annoncé ;
- contrôler l'alternative textuelle des graphiques et tableaux ;
- vérifier le reflow à 320 px et le contraste des nouveaux composants.

Les écarts qui nécessitent une appréciation humaine sont consignés dans le
ticket de l'évolution avant publication.
