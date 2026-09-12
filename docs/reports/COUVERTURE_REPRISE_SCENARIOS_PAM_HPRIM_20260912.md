# Couverture de reprise des scénarios PAM/HPRIM

Date : 12 septembre 2026

## Verdict

Le programme reprend le périmètre demandé de l'ancien outil : les scénarios
**IHE PAM France** et **HPRIM XML**. Les autres domaines de l'ancien dépôt ne
sont volontairement pas importés.

La reprise ne consiste pas seulement à stocker des payloads : un scénario
importé peut être classé, activé par cible, versionné, prévisualisé, routé vers
plusieurs endpoints, livré de manière durable et rejoué sans régénérer ses
identifiants.

## Corpus et traçabilité

| Élément | Couverture |
|---|---|
| Corpus PAM historique | 322 entrées, consolidées en 165 séquences distinctes |
| Corpus HPRIM fourni par le projet | 60 entrées, consolidées en 54 séquences distinctes |
| Catalogue opérationnel attendu | 219 scénarios actifs distincts |
| Sources historiques | clés, chemins et package conservés dans `legacy_source_json` / `legacy_package` |
| Doublons techniques | regroupés sans perdre les références d'origine |
| Formats historiques | `hprim`, `hprimxml` et préfixe `MSH|` devant XML normalisés |
| Variables CPage | converties vers les tokens du moteur ; inconnues signalées au contrôle préalable |

L’import `/scenarios/qualification/catalog/import` est idempotent : il peut
être relancé après une mise à jour du corpus sans créer de doublons.

## Fonctions opérationnelles reprises ou améliorées

| Besoin de recette | Fonction MedData Bridge |
|---|---|
| Organiser les scénarios comme des packages | thèmes hiérarchiques, thème principal, tags et package historique |
| Expliquer le but d’un scénario | commentaire fonctionnel séparé du payload |
| Activer/désactiver par logiciel cible | état persistant scénario × système cible |
| Voir le dernier résultat et depuis quand | statut, date de changement, dernière réussite/erreur et échecs consécutifs |
| Émettre PAM et HPRIM ensemble | jeu multi-protocole, matrice étape × endpoint et clé de système cible |
| Prévenir l’écrasement d’un jeu précédent | nouvelle identité/IPP/NDA/venue à chaque nouveau jeu |
| Reprendre une panne | outbox persistante, retry d’une livraison ou de tous les échecs d’un jeu, sans duplicata des succès |
| Conserver des preuves | version, payload source/compilé, ACK/réponse, erreur et diagnostic JSON téléchargeable |
| Qualifier un résultat | assertions de transport et assertions BDD déclaratives contrôlées |
| Exécuter une sélection ordonnée | campagnes durables et preuves par scénario |

## Limites assumées

- Les domaines historiques hors PAM/HPRIM (IMBO/MBO, GEF, RH, EDI,
  B2/DRE/TG et Chorus) restent exclus du périmètre, conformément au besoin.
- Les 1 350 assertions de l’ancien outil ne peuvent pas être déduites sans
  ambiguïté des payloads. Le moteur offre les assertions nécessaires ; les
  attentes fonctionnelles propres à chaque partenaire doivent être saisies et
  validées par l’équipe de recette.
- La preuve finale d’interopérabilité avec un logiciel cible reste la recette
  sur ses endpoints et sa BDD. Le test PAM + HPRIM à deux cibles FILE vérifie
  le déterminisme du moteur sans prétendre certifier le logiciel tiers.

## Preuves automatisées associées

- `tests/unit/test_legacy_scenario_catalog.py` : import, dédoublonnage et
  conservation des sources ;
- `tests/unit/test_scenario_play_service.py` : outbox, identifiants et
  assertions du jeu ;
- `tests/unit/test_scenario_campaign_service.py` : campagne durable ;
- `tests/integration/test_mixed_scenario_play_roundtrip.py` : PAM + HPRIM vers
  deux cibles isolées et distinction entre deux jeux.
