# Scenario runner et harness de tests

Fichiers

- `app/services/scenario_runner.py` : exécute des scénarios (suite de messages) en mode test/integration.

- `app/services/scenario_template_materializer.py` et `app/services/scenario_template_init.py` : initialisent et matérialisent templates de scénarios.

- `tests/messages/` contient scénarios d'intégration et fixtures.

Fonctionnement

- Le runner reçoit un template (suite MSH| messages), injecte dans l'application via les services d'inbound ou simule l'émission, puis vérifie les effets (MessageLog, DB state, émissions).

- Il utilise `scenario_validation` pour valider le résultat global.

Cas d'usage

- Tests chained A28→A04→A03 : injecter la suite, s'assurer que la validation signale/autorise les non-conformités attendues, vérifier les enregistrements DB et les messages émis.
