# MedData Bridge

MedData Bridge est une plateforme légère d'interopérabilité destinée à la qualification et au test d'interfaces HL7 / FHIR (IHE PAM, HPRIM, etc.).

L'objectif principal est de fournir un environnement reproductible pour :
- importer et valider des messages HPRIM/HL7 ;
- visualiser et manipuler des dossiers patients de démonstration ;
- tester des parcours de cotation (CCAM/NGAP/UCD/LPP) et exporter des résultats.

Ce dépôt contient une application FastAPI + Jinja2 (UI) avec une petite base SQLite d'exemples.

## Contenu clé
- `app/` : code de l'application (routers, templates, modèles SQLModel, services).
- `docs/` : documentation détaillée (IHE PAM, HPRIM, API, guides d'intégration).
- `medbridge.db` : base SQLite utilisée localement (fichier généré après `init_db`).

Voir la documentation technique complète dans `docs/PROGRAM_DOCUMENTATION.md` et `docs/user_guide.md`.

## Démarrage rapide (développement)
1. Créez et activez un environnement virtuel Python 3.10+ :

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-server.txt
```

2. Initialiser la base de données (tables, indexes, FTS best-effort) :

```bash
.venv/bin/python3 - <<'PY'
from app.db import init_db
init_db()
print('DB initialisée')
PY
```

3. Lancer le serveur (uvicorn) en mode développement :

```bash
.venv/bin/python3 -m uvicorn app.app:app --reload --port 8000
```

4. Ouvrir l'interface web dans un navigateur :

- UI principale : http://127.0.0.1:8000/
- Import HPRIM : http://127.0.0.1:8000/hprim/import
- Sélecteur de dossier (Cotation moderne) : http://127.0.0.1:8000/cotation-modern/select

## Endpoints utiles pour les tests d'interop
- Recherche de dossiers (publique, conçue pour qualification) :
  - `GET /cotation-modern/search?q=<query>&page=<n>&per_page=<m>`
  - Exemple : `GET /cotation-modern/search?q=Martin&page=1&per_page=10`
  - Réponse : JSON `{ "results": [...], "meta": { "total": N, "page": P, "per_page": M } }`

- Cotation pour un dossier :
  - UI : `GET /cotation-modern/dossiers/{dossier_id}/cotation`

- API & documentation interactive : `GET /docs` (FastAPI OpenAPI) — utile pour voir les routes techniques.

## Notes sur sécurité et usage
- Ce dépôt contient des fonctionnalités destinées aux tests d'interopérabilité. Par défaut la recherche de dossiers a été rendue publique pour faciliter les scénarios de qualification et les tests automatisés. En production, il est recommandé d'activer un contrôle d'accès.
- Les indexes SQLite et la table FTS sont créés en mode "best-effort" par `init_db()` si la compilation de SQLite le permet.

## Contribuer / tests
- Les tests unitaires et d'intégration se trouvent sous `tests/`. Lancez :

```bash
.venv/bin/python3 -m pytest -q
```

Pour toute question ou besoin d'adaptation (ex: activation/désactivation d'auth pour certains environnements), dites-moi quelle politique vous souhaitez et je l'implémenterai.

---
Fichier de documentation plus complet : [docs/PROGRAM_DOCUMENTATION.md](docs/PROGRAM_DOCUMENTATION.md#L1)
