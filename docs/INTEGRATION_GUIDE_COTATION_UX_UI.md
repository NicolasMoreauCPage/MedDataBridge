# Guide d'intégration – Nouvelle IHM Cotation HPRIM (UX/UI Pro)

## 1. Fichiers créés

- `app/templates/hprim_cotation_modern.html` : nouveau template HTML moderne, responsive, accessible, mobile-first.
- `app/static/js/cotationForm.js` : gestion dynamique des actes, modals, résumé, feedback utilisateur.

## 2. Pour tester la nouvelle IHM

1. Ajouter une route Flask/FastAPI pour servir le template `hprim_cotation_modern.html` (exemple : `/cotation-modern`).
2. S'assurer que le JS est servi depuis `/static/js/cotationForm.js`.
3. Ouvrir `/cotation-modern` dans le navigateur.

## 3. Points d'attention

- L'ancien template (`hprim_cotation.html`) n'est pas modifié : migration progressive possible.
- Le JS est découplé, facile à maintenir et à étendre (ajout de recherche d'actes, drag & drop, feedback API…).
- Les styles utilisent Tailwind CSS : vérifier la présence du CDN ou intégrer Tailwind dans le pipeline si besoin.
- Les toasts, modals, résumé dynamique sont inclus.
- Accessibilité : labels explicites, focus visible, navigation clavier, contrastes respectés.

## 4. Prochaines étapes possibles

- Brancher les appels API réels (valider/émettre, preview XML…)
- Ajouter la recherche d'actes (autocomplete)
- Ajouter des tests UI automatisés (Playwright, Cypress…)
- Recueillir le feedback utilisateurs métiers

---

Pour toute adaptation ou extension, modifier le template ou le JS dédié. Pour une migration totale, remplacer l'ancien template dans la navigation principale.
