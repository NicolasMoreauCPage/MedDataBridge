# Routeurs et endpoints principaux

Emplacement

- `app/routers/` contient les routeurs FastAPI par domaine (patients, dossiers, messages, admin, transport, etc.).

Endpoints critiques

- `app/routers/messages.py` : consultation et recherche dans `MessageLog`.

- `app/routers/transport.py` : endpoints pour ingestion HTTP si présents.

- `app/routers/endpoints.py` : configuration des endpoints distants (systèmes producteurs/consommateurs).

- `app/routers/admin_*` : configuration administrative, import de vocabulaires, etc.

Contrats

- Les endpoints publics retournent JSON ; les endpoints techniques acceptent des payloads HL7 (texte) ou JSON selon la route.

- Auth : certains endpoints admin exigent authentification (routeur `auth.py`).

Exemples d'appel

- Ingestion via API (si activée) : POST /transport/inbound {"message": "MSH|..."}

- Recherche message : GET /messages?patient_id=123&event=A01

Bonne pratique

- Les routeurs délèguent la logique aux services ; garder les routeurs minces facilite les tests.
