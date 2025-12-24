# Documentation interne : Exécution des tests automatisés

## Structure des tests

Tous les tests sont situés dans le dossier `tests/` à la racine du projet. Ce dossier contient :
- Des fichiers de test unitaires et d'intégration (ex : `test_*.py`)
- Des sous-dossiers pour organiser les tests par type ou domaine :
  - `unit/` : tests unitaires
  - `ui/` : tests d'interface utilisateur
  - `generated/` : tests générés automatiquement
  - `messages/` : tests liés aux messages HL7
  - D'autres sous-dossiers éventuels

## Découverte automatique

Le framework utilisé est **pytest**. Il détecte automatiquement tous les fichiers et fonctions de test respectant la convention :
- Fichiers : `test_*.py` ou `*_test.py`
- Fonctions : `def test_*`

## Commande pour exécuter tous les tests

Depuis la racine du projet (avec l'environnement virtuel activé) :

```bash
pytest tests --disable-warnings -v
```

- Cette commande exécute tous les tests du dossier `tests/` et de ses sous-dossiers.
- Les nouveaux tests ajoutés seront automatiquement pris en compte s'ils respectent la convention de nommage.

## Bonnes pratiques
- Toujours activer l'environnement virtuel avant d'exécuter les tests :
  ```bash
  source .venv/bin/activate
  ```
- Ajouter de nouveaux tests dans le dossier ou sous-dossier approprié.
- Utiliser la commande ci-dessus pour valider l'ensemble du projet.

---

*Ce fichier est destiné à l'automatisation et à la documentation interne pour garantir la robustesse de l'exécution des tests.*
