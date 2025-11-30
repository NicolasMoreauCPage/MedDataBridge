Résumé des corrections MFN export

Problème initial
- L'export MFN ciblé (via `generate_mfn_message(session, eg_identifier=...)`) n'incluait que l'EntiteGeographique (EG) dans certains cas.
- Les relations LRL pouvaient être manquantes car le code se fiait aux attributs de relation d'objets (p.ex. `pole.services`) qui peuvent être non chargés dans la session en cours.
- Certains appels faisaient référence à des attributs inexistants et pouvaient lever des exceptions dans des contextes particuliers.

Corrections appliquées
1. Requête explicite des entités liées
- Quand `eg_identifier` est fourni, la génération interroge explicitement la base de données pour récupérer:
  - Pôles (`Pole`) liés à l'EG
  - Services attachés aux pôles
  - Unités fonctionnelles liées aux services
  - Unités d'hébergement, chambres et lits

2. Emission des segments LRL basée sur les FK
- Les segments `LRL` sont désormais générés à partir des clefs étrangères (p.ex. `pole_id`, `service_id`, `unite_fonctionnelle_id`, `unite_hebergement_id`, `chambre_id`) via des requêtes `SELECT` pour dériver l'identifier du parent.
- Comportement de collapse_virtual conservé: si un pôle virtuel est trouvé et `collapse_virtual=True`, la relation vers l'EG parent est utilisée.

3. Robustesse
- Ajout de fallbacks et de blocs try/except autour des lookups pour garantir que la génération MFN ne lève pas en cas d'attributs manquants.

Tests
- Ajout d'un test d'intégration `tests/test_mfn_export.py` qui crée une hiérarchie EG->Pole->Service->UF->UH->Chambre->Lit, génère un MFN ciblé et vérifie la présence des segments `MFE` pour chaque type et l'existence d'au moins un `LRL`.

Comment reproduire manuellement
- Lancez :

```bash
TESTING=1 pytest -q tests/test_mfn_export.py -q
```

Remarques
- Le code conserve la logique existante de `collapse_virtual` (exclusion des pôles/services virtuels si demandé).
- Si vous souhaitez que les MFN exportés incluent d'autres champs LCH additionnels, je peux étendre `add_lch_segments()` pour exposer plus d'attributs.

Fait par: correction automatique dans la branche `fix/eg-structure-tree`.
