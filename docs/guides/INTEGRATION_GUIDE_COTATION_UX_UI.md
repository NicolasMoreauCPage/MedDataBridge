# Guide d'intégration — workspace de cotation

Statut : actif — vérifié le 23 septembre 2026.

La seule saisie opérationnelle est le workspace persistant :
`/cotations/dossier/{dossier_id}/saisie`, rendu par
`app/templates/cotations/saisie_rapide.html` et ses assets dédiés.

Les entrées historiques `/cotation-modern/...` redirigent vers ce même
parcours. L'ancien prototype `hprim_cotation_modern.html` et son JavaScript de
simulation ont été retirés : aucune action utilisateur ne doit afficher un
succès local sans persistance confirmée.

Pour vérifier le parcours, créez ou choisissez un séjour, ouvrez sa saisie de
cotations, enregistrez un acte, puis contrôlez qu'il réapparaît dans la liste
du même workspace. Les actions de masse et l'export reposent également sur les
API persistantes de ce parcours.
