# Finalisation des améliorations du logiciel

Date : 13 septembre 2026
Périmètre : interopérabilité, scénarios, exploitation, UX et maintenabilité —
hors sécurité, conformément au choix du projet.

## Verdict

Le moteur de scénarios est fonctionnel pour des jeux multi-protocoles et
multi-destinations durables. Les améliorations directement réalisables dans le
dépôt sont terminées et couvertes par des tests. Les seules réserves restantes
nécessitent un environnement partenaire réel ou des décisions contractuelles.

## Réalisations

- validation du payload compilé par destination : IHE PAM France, HL7 SIU,
  HL7 MFN, HL7 v2 générique, HPRIM XML/XSD et FHIR/FR Core ;
- blocage avant émission d'un scénario positif approuvé invalide, tout en
  préservant les scénarios de tests négatifs ;
- routage par étape vers toutes les cibles compatibles, des endpoints choisis
  ou une clé de système cible ;
- étapes obligatoires ou facultatives, délais persistés et respect strict de
  l'ordre après redémarrage ;
- politiques d'arrêt cohérentes et réconciliation du statut des jeux,
  livraisons, cibles et campagnes ;
- campagnes de lancement en masse persistantes ;
- ACK synthétique exploitable et statistiques d'outbox sur `/outbox/stats` ;
- IHM enrichie : routage, criticité, échéance, validation et diagnostic JSON ;
- correction des raccourcis clavier et des filtres vides dans les listes ;
- migration Alembic unique, vérifiée sur base vide et base existante ;
- CI étendue aux migrations, validateurs et régressions du moteur.

## Preuves exécutées

| Preuve | Résultat |
|---|---:|
| Catalogue entre deux GHT/BDD isolés | 137/137 scénarios réussis |
| Égalité des projections métier du catalogue | conforme |
| Roundtrip CPage généré entre deux GHT | 125 messages, BDD identiques |
| Ingestion du corpus CPage source | 172 AA, 20 AE, 7 AR attendus |
| Capacité du moteur | 120 étapes × 3 endpoints = 360 livraisons |
| Migration Alembic depuis une base vide | conforme |
| Migration d'une copie de la base existante | conforme |

Le rapport détaillé du catalogue reste
[ROUNDTRIP_CATALOGUE_SCENARIOS_DEUX_GHT_20260912.md](ROUNDTRIP_CATALOGUE_SCENARIOS_DEUX_GHT_20260912.md).
La [revue de code et de régression](REVUE_CODE_ET_REGRESSION_20260913.md)
documente les contrôles ciblés et la dette résiduelle de la suite historique.

## Réserves externes

La qualification finale de déploiement doit être répétée avec les véritables
endpoints MLLP, HTTP/FHIR et HPRIM, leurs volumes réseau, leurs timeouts et
leurs règles métier locales. De même, l'enrichissement d'acquittements HPRIM
CCAM/NGAP dépend du contrat retenu avec les logiciels destinataires. Ces points
ne peuvent pas être déduits fidèlement d'une exécution locale.

## Conclusion

Le projet dispose désormais d'un socle cohérent, observable et testable pour
valider, générer, rejouer et diagnostiquer les échanges. Toute évolution
supplémentaire doit partir d'un nouveau besoin métier, d'un écart observé chez
un partenaire ou d'une mesure de production ; ajouter des fonctions sans l'un
de ces signaux augmenterait surtout la complexité.
