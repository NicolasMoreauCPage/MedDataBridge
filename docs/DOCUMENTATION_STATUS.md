# Statut et classement de la documentation

Mis à jour le 24 septembre 2026. Propriétaire : équipe Qualité documentaire.

Le dépôt contient de nombreux Markdown produits au fil des audits, sprints et
qualifications. Ils ne sont pas supprimés : ils constituent une trace utile.
Ce fichier évite qu'un instantané ancien soit confondu avec une spécification
ou une preuve courante.

Le registre des documents actifs, de leurs propriétaires et de leur date de
dernière vérification est la table « Références à utiliser » de
[`docs/README.md`](README.md). Un document absent de ce registre n'est pas une
référence active, même s'il reste conservé pour la traçabilité.

## Hiérarchie de référence

1. Le code, les migrations et les tests exécutables.
2. Les contrats de protocole et les rapports de qualification les plus récents.
3. Les guides d'exploitation et d'API maintenus.
4. Les plans, audits, sprints, comptes rendus et TODO historiques.

## Classement par répertoire

| Emplacement | Usage | Statut |
|---|---|---|
| `README.md` | Présentation et démarrage du dépôt | Maintenu |
| `docs/README.md` | Index de la documentation maintenue | Maintenu |
| `docs/user_guide.md` | Guide utilisateur et procédures d'exploitation | Maintenu |
| `docs/IHE_PAM*.md`, `docs/MFN_*.md`, `docs/HPRIM_*.md` | Guides techniques de protocole | À lire avec les rapports de conformité récents |
| `docs/API_*.md`, `docs/FHIR_API.md` | Contrats et API applicatives | Certaines API IHM historiques ; contrat FR Core partenaire distinct |
| `docs/OUTBOX.md`, `docs/TESTS_STATUS.md` | Exploitation et preuves exécutables | Maintenu |
| `docs/reports/` | Audits, plans et preuves de qualification | Indexé ; un rapport daté est un instantané |
| `docs/Technical/full/` | Description détaillée de l'architecture | Référence d'orientation ; le code prévaut |
| `docs/architecture/`, `docs/ux/`, `docs/Patient/` | Notes de conception et décisions locales | Historique ou à revalider avant évolution |
| `docs/archive/` | Documents explicitement remplacés | Archive |
| `deployment/`, `docs/deployment/` | Guides de déploiement dépendants de la plate-forme | À revalider au déploiement |
| `scripts/`, `tests/` | Aide aux scripts et tests | À maintenir avec le code concerné |

## Conventions appliquées

- Les noms de fichiers ne sont pas changés : ils sont déjà cités dans des
  rapports et des scripts externes.
- Les rapports historiques conservent leurs constats initiaux. Leur en-tête ou
  leur index indique désormais s'ils sont remplacés, validés ou encore ouverts.
- Les plans multi-protocoles clos restent à leur emplacement pour préserver les
  liens entrants, mais leur statut historique est explicite dans l'index actif.
- Les nombres globaux de tests sont évités dans les documents maintenus. Une
  commande reproductible et la CI sont plus fiables qu'un chiffre figé.
- Un lien vers une page HTML inexistante, un ancien nom de produit ou un ancien
  endpoint ne doit pas servir de référence : le document d'index approprié doit
  pointer vers le contrat actuel.

## Révision à effectuer lors d'une évolution

Pour tout changement qui touche un protocole, mettre à jour :

1. le test unitaire ou d'intégration associé ;
2. le test de roundtrip si une donnée persistée est concernée ;
3. le rapport de référence indiqué dans `docs/README.md` ;
4. cet index si le statut, le périmètre ou la localisation du contrat change.
