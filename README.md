# MedData Bridge

MedData Bridge est une plateforme de qualification d'interfaces de santé. Elle
permet de manipuler des données de démonstration, de valider et rejouer des
échanges IHE PAM, HPRIM, MFN et FHIR, ainsi que de construire des scénarios
d'interopérabilité reproductibles.

Ce dépôt contient une application FastAPI avec interface Jinja2, une base
SQLite pour le développement local et une pile PostgreSQL/Redis pour Compose.
Ce n'est pas un POC : les contrats d'interopérabilité, les migrations, les
scénarios, les roundtrips et la chaîne CI font partie du produit.

## Références

- [Index de la documentation maintenue](docs/README.md)
- [Guide de déploiement Compose](docs/deployment/deployment.md)
- [Commandes de test et périmètre de qualification](docs/TESTS_STATUS.md)
- [Guide utilisateur](docs/user_guide.md)
- [Rapports et preuves de qualification](docs/reports/README_FOR_REPORTS.md)

Les plans, audits et comptes rendus datés restent accessibles dans `docs/` pour
la traçabilité. Ils ne remplacent pas le code, les tests automatisés ou les
guides ci-dessus.

## Démarrage local

Prérequis : Python 3.10 ou supérieur (3.11 est utilisé en CI) et Node.js 20
pour les contrôles frontend.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
cp .env.example .env
uvicorn app.app:app --reload --port 8000
```

L'application applique les migrations Alembic à son démarrage. Pour ajouter le
jeu de démonstration complet, après avoir arrêté le serveur :

```bash
python init_db.py
```

L'initialisation complète ajoute des données de démonstration, des vocabulaires
et des scénarios ; elle ne doit pas être utilisée sur une base de recette à
préserver. L'option `--minimal` fournit un jeu plus réduit.

Une fois le serveur lancé :

- interface : <http://localhost:8000/> ;
- OpenAPI : <http://localhost:8000/api/docs> ;
- disponibilité : <http://localhost:8000/health> ;
- disponibilité enrichie : <http://localhost:8000/ready>.

## Validation locale

```bash
TESTING=1 PYTHONPATH=. python -m pytest -q tests/unit tests/integration
npm ci
npm run check-frontend
```

Les tests navigateur, de charge et les campagnes de conformité interopérable
sont documentés dans [docs/TESTS_STATUS.md](docs/TESTS_STATUS.md). La
configuration exécutée sur chaque push et pull request est
[`interop-conformance.yml`](.github/workflows/interop-conformance.yml).

## Compose

Le déploiement Compose est reproductible depuis un checkout propre. Créer et
renseigner `.env`, puis suivre le
[guide de déploiement](docs/deployment/deployment.md). La CI construit la pile,
applique les migrations sur PostgreSQL vierge et contrôle `/health`.

## Structure du dépôt

- `app/` : application, domaines métier, routeurs et assets UI ;
- `alembic/` : migrations et baseline de schéma ;
- `tests/` : tests unitaires, intégration, E2E et performance ;
- `docker/` : image, Compose et configurations de services ;
- `scripts/` : contrôles de qualité, qualification et utilitaires ;
- `docs/` : documentation maintenue et historique de décision.
