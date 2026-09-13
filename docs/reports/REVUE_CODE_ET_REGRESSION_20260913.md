# Revue de code et régression finale

Date : 13 septembre 2026

## Résultat

La revue a permis de corriger les régressions identifiées sur le moteur de
scénarios, les migrations et l'IHM. Les parcours livrables sont couverts par
une suite ciblée verte et par les roundtrips à deux GHT. La suite historique
complète conserve cependant une dette de tests : elle n'est pas un indicateur
fiable unique tant que ses tests externes et ses bases de données ne sont pas
isolés.

## Correctifs issus de la revue

- fiabilisation de la validation finale des messages compilés avant émission ;
- routage persistant par étape et par destination, y compris étapes facultatives
  et planification différée ;
- correction du rendu de statut des scénarios, des filtres de listes et de la
  création de vocabulaire ;
- correction de la récupération du contexte établissement dans les formulaires
  dossiers ;
- sécurisation de l'ajout de messages de flash lorsqu'une requête de test ne
  possède pas de session ;
- compatibilité des migrations avec une base minimale déjà estampillée et avec
  une base vide ;
- remplacement des appels Pydantic v1 obsolètes dans les chemins applicatifs ;
- exclusion explicite du générateur applicatif de la collecte pytest ;
- ajout d'un test de capacité, de tests de routage/IHM et de tests de migration
  fraîche.

## Contrôles concluants

| Contrôle | Résultat |
|---|---:|
| Conformité PAM, HPRIM, MFN et FHIR ciblée + scénarios | 77 tests réussis |
| Régression IHM dossiers/venues (Playwright) | 15 tests réussis |
| Migrations Alembic base vide et base minimale | 3 tests réussis |
| Capacité des scénarios | 360 livraisons planifiées et validées |
| Roundtrip catalogue entre deux GHT | 137 scénarios réussis, projections BDD égales |
| Roundtrip CPage généré entre deux GHT | projections BDD égales |
| Compilation Python et lint Ruff des fichiers modifiés | conformes |

Les contrôles exécutables sont également intégrés au workflow
`interop-conformance`.

## Audit de la suite historique large

La commande ci-dessous a été lancée afin de caractériser la dette existante :

```bash
pytest -c pytest.ini -q --ignore=tests/e2e --ignore=tests/performance
```

Son résultat brut a été de **889 réussites, 88 échecs, 37 ignorés et 24 xfail**.
Les trois régressions repérées pendant cette passe (migration fraîche,
affichage de statut des scénarios, session absente dans les tests) ont été
corrigées puis retestées dans la suite ciblée ci-dessus.

Les échecs restants se répartissent principalement entre :

- tests qui démarrent l'application sur une base sans schéma ni contexte GHT ;
- tests MLLP, HTTP ou asynchrones nécessitant un service externe, un port ou un
  marquage pytest adapté ;
- anciennes assertions de messages ou de modèles devenues incompatibles avec
  les évolutions déjà présentes dans le dépôt ;
- tests exécutés dans un ordre qui partage un état de base de données.

Ils doivent être repris dans un chantier dédié de fiabilisation de la suite :
fixtures de base isolées, marqueurs `external`/`manual`, et séparation des
tests de contrat historiques des tests de non-régression applicatifs. Ils ne
remettent pas en cause les validations fonctionnelles et les roundtrips décrits
dans ce rapport, mais empêchent de déclarer la suite historique entièrement
verte.

## Conclusion

Le code modifié est vérifié au niveau approprié pour les fonctionnalités
livrées. La prochaine amélioration de qualité à forte valeur est de rendre la
suite de tests historique hermétique, afin que son résultat global soit de
nouveau exploitable en intégration continue.
