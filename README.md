# IntegraSanté by CPage

IntegraSanté est une plateforme légère d'interopérabilité destinée à la qualification et au test d'interfaces HL7 / FHIR (IHE PAM, HPRIM, etc.).

L'objectif principal est de fournir un environnement reproductible pour :
- importer et valider des messages HPRIM/HL7 ;
- visualiser et manipuler des dossiers patients de démonstration ;
- tester des parcours de cotation (CCAM/NGAP/UCD/LPP) et exporter des résultats.

Ce dépôt contient une application FastAPI + Jinja2 (UI) avec une petite base SQLite d'exemples.

## 📚 Documentation

**Documentation complète disponible dans [`docs/`](docs/)** :
- [PROGRAM_DOCUMENTATION.md](docs/PROGRAM_DOCUMENTATION.md) - Architecture et composants techniques
- [NAMESPACES_CLARIFICATION.md](docs/NAMESPACES_CLARIFICATION.md) - Guide HL7v2/FHIR sur les namespaces (OID, URI, nom)
- [API_REST_DOCUMENTATION.md](docs/API_REST_DOCUMENTATION.md) - Documentation des endpoints API
- [docs/README.md](docs/README.md) - Index complet de la documentation

### 🎨 Refonte Interface Structure (Phases 1-5.1)
- [SPRINT1_DASHBOARD_STRUCTURE.md](docs/SPRINT1_DASHBOARD_STRUCTURE.md) - Dashboard avec visualisation hiérarchique
- [SPRINT2_STRUCTURE_WIZARD_TEMPLATES.md](docs/SPRINT2_STRUCTURE_WIZARD_TEMPLATES.md) - Wizard de création avec templates
- [SPRINT3_MODE_GESTIONNAIRE.md](docs/SPRINT3_MODE_GESTIONNAIRE.md) - Mode Gestionnaire avec analytics
- [PHASE4_IMPORT_EXPORT.md](docs/PHASE4_IMPORT_EXPORT.md) - Spécifications Import/Export Excel
- [PHASE4.1_IMPORT_EXPORT_COMPLETE.md](docs/PHASE4.1_IMPORT_EXPORT_COMPLETE.md) - Documentation technique complète
- [API_FHIR_STRUCTURE.md](docs/API_FHIR_STRUCTURE.md) - API FHIR Structure (CRUD complet)
- [PHASE5_UX_MODERNE.md](docs/PHASE5_UX_MODERNE.md) - UX interactive (inline editing, drag & drop)
- [RECAPITULATIF_COMPLET.md](docs/RECAPITULATIF_COMPLET.md) - Vue d'ensemble de toutes les phases

## Contenu clé
- `app/` : code de l'application (routers, templates, modèles SQLModel, services).
- `docs/` : documentation détaillée (IHE PAM, HPRIM, API, guides d'intégration).
- `medbridge.db` : base SQLite utilisée localement (fichier généré après `init_db`).
- `tests/` : suite complète de tests (575+ tests : API, intégration, UI, sécurité, performance).

Architecture (schéma rapide)

```
  +-------------------+        +------------------+
  |  Browser / Tests  | <----> |  FastAPI (UI/API)|
  |  (Cypress, curl)  |        |  app/routers/*    |
  +-------------------+        +------------------+
                          |    ^
              search / import   |    | DB queries / FTS
                          v    |
                     +------------------+
                     |  SQLite (medbridge.db) |
                     |  (tables: patient, dossier, ...)
                     +------------------+

 - Import endpoints: `/hprim/import`, `/api/fhir/import/bundle`
 - Selector / search: `/cotation-modern/select` and `/cotation-modern/search`
 - OpenAPI docs: `/docs`
```

PUBLIC_SEARCH switch

Pour les environnements de qualification on expose la recherche de dossiers sans authentification. Vous pouvez contrôler ce comportement via la variable d'environnement `PUBLIC_SEARCH` :

- `PUBLIC_SEARCH=true` (par défaut) : `/cotation-modern/search` est publique.
- `PUBLIC_SEARCH=false` : l'endpoint requiert un token (si l'auth est activée).

La bascule est utile si vous voulez reproduire un environnement plus strict en CI/production.

## Démarrage rapide (développement)

### 1. Installation
Créez et activez un environnement virtuel Python 3.10+ :

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Initialisation de la base de données (FULL)
Un seul script pour tout créer :

```bash
python init_db.py
```

Cela crée automatiquement :
- ✅ Structure complète (4 EJ + hiérarchie)
- ✅ Vocabulaires (35 systèmes, 207 valeurs)
- ✅ 40 patients avec scénarios complexes
- ✅ ~400 scénarios HL7/HPRIM/IHE PAM
- ✅ Cotations médicales réalistes
- ✅ Endpoints MLLP + FHIR configurés

**Options disponibles** :
```bash
python init_db.py              # FULL (recommandé)
python init_db.py --minimal    # Rapide : 1 seul patient
python init_db.py --reset      # Recréer la DB depuis zéro
```

### 3. Lancer le serveur
```bash
uvicorn app.app:app --reload --port 8000
```

### 4. Accès

- **UI principale** : http://localhost:8000/
- **Admin** : http://localhost:8000/admin/ght/1/ej/1
- **Import HPRIM** : http://localhost:8000/hprim/import
- **Cotation moderne** : http://localhost:8000/cotation-modern/select
- **API docs** : http://localhost:8000/docs

## Endpoints utiles pour les tests d'interop
- Recherche de dossiers (publique, conçue pour qualification) :
  - `GET /cotation-modern/search?q=<query>&page=<n>&per_page=<m>`
  - Exemple : `GET /cotation-modern/search?q=Martin&page=1&per_page=10`
  - Réponse : JSON `{ "results": [...], "meta": { "total": N, "page": P, "per_page": M } }`

- Cotation pour un dossier :
  - UI : `GET /cotation-modern/dossiers/{dossier_id}/cotation`

- Interface d'administration SQL :
  - SQLAdmin : `GET /sqladmin` — interface d'administration de la base de données

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
