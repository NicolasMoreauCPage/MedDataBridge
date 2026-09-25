# État des tests

Dernière revue documentaire : 14 septembre 2026.

Ce document ne fige volontairement ni un nombre global de tests ni une promesse
de suite intégralement verte : ces chiffres deviennent vite périmés. La CI et
les commandes ci-dessous constituent la source de vérité exécutable.

## Périmètre de conformité interopérabilité

La campagne ciblée vérifie les contrats réellement revendiqués :

- IHE PAM France / CPage, y compris le roundtrip MLLP entre deux BDD ;
- HPRIM XML CCAM, NGAP, UCD et LPP, avec validation XSD et acquittements ;
- HL7 MFN^M05, avec import/export et roundtrip de structure ;
- FHIR R4 / FR Core 2.2.0, avec import/export, idempotence et relations de
  structure ;
- outbox persistante, rejet et reprise des émissions sortantes.

La liste exacte est exécutée par
[`interop-conformance.yml`](../.github/workflows/interop-conformance.yml).

## Exécution locale

La commande rapide par défaut exclut les tests qui demandent un navigateur, une
pile E2E ou de la charge. Ces catégories sont marquées automatiquement à partir
de `tests/ui`, `tests/e2e` et `tests/performance` :

```bash
TESTING=1 PYTHONPATH=. .venv/bin/pytest -q
npm run check-frontend
```

Les parcours navigateur restent exécutables séparément :

```bash
TESTING=1 PYTHONPATH=. .venv/bin/pytest -m ui -q tests/ui
```

## Validation Compose

Le service applicatif écoute par défaut sur le port local `8000`. Lorsqu'il est
déjà utilisé, le port peut être choisi sans modifier le fichier Compose :

```bash
cp .env.example .env
# Renseigner au minimum SECRET_KEY, JWT_SECRET_KEY et SESSION_SECRET_KEY.
MEDBRIDGE_PORT=8002 docker compose -f docker/docker-compose.yml up -d --build
curl --fail http://127.0.0.1:8002/health
docker compose -f docker/docker-compose.yml down
```

Le démarrage applique les migrations Alembic avant Uvicorn. PostgreSQL et
Redis restent accessibles au réseau interne Compose ; les données applicatives
sont conservées dans des volumes nommés. `docker compose -f
docker/docker-compose.yml config` reste exécutable sans `.env`, ce qui permet
de valider la configuration depuis un checkout propre ; le lancement du
service, lui, requiert les clés de runtime.

L'inventaire des opérations publiques est généré depuis l'OpenAPI effectif :

```bash
PYTHONPATH=. python3 scripts/generate_openapi_inventory.py --output docs/reports/OPENAPI_INVENTORY.md
```

La campagne ciblée de conformité interopérabilité est :

```bash
TESTING=1 PYTHONPATH=. .venv/bin/pytest -q \
  tests/unit/test_fhir_frcore_2_2_0_conformance.py \
  tests/integration/test_fhir_structure_roundtrip.py \
  tests/integration/test_fhir_interop.py \
  tests/unit/test_outbox_service.py \
  tests/unit/test_mfn_export.py \
  tests/integration/test_mfn_structure_roundtrip.py \
  tests/unit/test_hprim_acquittement_xsd.py \
  tests/integration/test_hprim_xml_roundtrip.py

python3 scripts/true_roundtrip_cpage.py run
```

Les tests d'IHM sont distincts des preuves de conformité protocolaire. Les
suites Phase 5 sont vertes lors de la dernière campagne ciblée ; le scénario
Phase 6 de filtrage de dossiers requiert encore une stabilisation E2E. Cette
limite n'affecte ni la validation PAM ni les roundtrips interopérables.

## Règles de maintenance

- Ajouter un test positif, un test négatif et un roundtrip dès qu'un nouveau
  champ métier est pris en charge par un protocole.
- Ne pas masquer une régression par un `xfail` non justifié.
- Publier les empreintes anonymisées et les rapports de roundtrip comme
  artefacts CI.
- Conserver les écarts restant ouverts dans le rapport de référence du
  protocole, avec leur sévérité et leur effet métier.
