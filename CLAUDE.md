# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

IntegraSanté / MedData Bridge is a FastAPI + Jinja2 interoperability test bench for HL7v2 and FHIR
healthcare exchanges (IHE PAM ADT, HPRIM, FHIR R4 with the French Core IG). It lets users import/validate
HL7v2 and FHIR messages, browse simulated patient records, run "cotation" (CCAM/NGAP/UCD/LPP billing
code) workflows, and drive scripted interoperability scenarios for qualification testing. Persistence is
SQLModel over SQLite (`medbridge.db` / `data/medbridge.db`).

Full architecture docs already exist in-repo and are more detailed than this file — read them when you
need depth:
- `docs/PROGRAM_DOCUMENTATION.md` — domain flows and contracts (FHIR import/export, IHE PAM inbound, MFN structure)
- `docs/PROJECT_ORGANIZATION.md` — full router/service/model file inventory
- `docs/NAMESPACES_CLARIFICATION.md` — HL7v2 vs FHIR identifier/namespace (OID/URI) semantics
- `docs/API_REST_DOCUMENTATION.md`, `docs/MENU_MAP.md`

## Commands

### Setup
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### Run the app
```bash
uvicorn app.app:app --reload --port 8000
```
- UI: http://localhost:8000/ · API docs: http://localhost:8000/docs · SQLAdmin: http://localhost:8000/sqladmin

### Database
```bash
python init_db.py              # full seed: EJ/GHT hierarchy, vocab, 40 patients, ~400 HL7/HPRIM/PAM scenarios
python init_db.py --minimal    # fast: single patient
python init_db.py --reset      # drop and recreate from scratch
python3 seed_scenarios_from_json.py   # (re)seed scenarios from data/scenarios_seed_data.json — the only
                                       # supported way to load scenarios; the old file-based HL7/HPRIM
                                       # scenario import is disabled in init_db.py
alembic upgrade head            # apply migrations (sqlite:///./data/medbridge.db by default)
```

### Tests
Two pytest configs exist: `pytest.ini` (project root, authoritative — sets `testpaths = tests`,
ignores `tools/`, `scripts_manual/`, `archives/`, `one_shot_legacy/`) and a `[tool.pytest.ini_options]`
block in `pyproject.toml`. `pytest.ini` wins when both are present.

```bash
pytest -q                                       # full suite (575+ tests)
pytest tests/unit/test_foo.py                   # one file
pytest tests/unit/test_foo.py::test_bar -v      # one test
pytest -m "not slow and not ui"                 # skip slow/browser tests
pytest -m security                              # marker-scoped run (unit/integration/ui/api/security/performance/critical/property/...)
```
`tests/conftest.py` sets `TESTING=1` and mocks the Redis cache service (`app.services.cache_service`)
before app import — always import app modules after conftest has run (i.e. via pytest, not a bare script).
UI tests use Playwright (`pytest-playwright`); install browsers with `playwright install` if UI tests fail
to launch.

There is no configured linter/formatter (no ruff/black/mypy config in the repo) and CI workflows under
`.github/workflows/` are all suffixed `.disabled` — tests are not currently gated automatically, so run
`pytest -q` yourself before considering a change done.

### Frontend assets
```bash
npm run build-css        # Tailwind watch build → app/static/css/output.css
npm run build-css-prod   # minified prod build
```

## Architecture

**Request flow**: Browser/tests → FastAPI routers (`app/routers/**`, ~60 files, UI + REST mixed) →
services (`app/services/**`, 80+ files, business logic) → SQLModel models (`app/models*.py`) → SQLite.
Templates are Jinja2 under `app/templates/`, styled with Tailwind/DaisyUI.

**App composition**: `app/app.py` builds the FastAPI instance, wires ~30 middlewares/routers, and owns
the `lifespan` context: on startup it calls `init_db()`, registers entity-event listeners
(`entity_events.py`, `entity_events_structure.py` — auto-emit messages when entities are created), starts
all configured MLLP servers via a shared `MLLPManager` (`app.state`), and starts the FILE-endpoint polling
scheduler. All of this is **skipped when `TESTING=1` or under pytest** — tests own their own DB/session
setup via `db_session_factory` overrides, so don't expect lifespan side effects in tests.

**Three domain pipelines, each with import + export directions:**

1. **FHIR** (`app/services/fhir.py`, `fhir_resources.py`, `app/converters/fhir_import_converter.py`,
   `app/routers/fhir_export.py` / `fhir_import.py`). Export produces a `collection` Bundle
   (Patient/Encounter/EpisodeOfCare) with stable `fullUrl` = `ResourceType/<id>`. Import
   (`POST /api/fhir/import/bundle`) runs `FHIRBundleImporter.import_bundle()` in three passes
   (Location → Patient → Encounter) and maintains a `resource_map` (bundle-local id and `Type/id` →
   DB numeric id) to resolve intra-bundle references; `_extract_id_from_reference()` accepts full URLs,
   `Type/id`, bare ids, `#id`, and numeric ids.

2. **IHE PAM inbound** (`app/services/transport_inbound.py`, `pam_validation.py`, `mllp_manager.py`,
   `mllp.py`). MLLP listener → `on_message_inbound()` → parses MSH/PID/PV1/ZBE → validates PAM-FR rules →
   `IHEMessageRouter` dispatches by ADT event (A01/A03/A08/A12/A13/...) to admission/discharge/
   update/cancel handlers that create/update `Patient`/`Dossier`/`Venue`/`Mouvement`.

3. **HL7 MFN structure** (`app/services/mfn_structure.py`): `generate_mfn_message()` /
   `process_mfn_message()` export/import the location hierarchy (EntiteGeographique → Pole → Service →
   UF → UH → Chambre → Lit) as MFN M05 messages; has an equivalent FHIR Location/Organization
   representation (`fhir_structure.py`).

**Cotation (billing) module**: `app/routers/cotation_modern.py` / `cotation_selector.py` for the
search/select UI, backed by nomenclature-specific routers+services: CCAM (`routers/ccam.py`), NGAP
(`services/ngap_service.py`), UCD (`routers/ucd.py` + `api/ucd.py` + `services/ucd_service.py`), LPP
(`routers/lpp.py` + `api/lpp.py` + `services/lpp_service.py`).

**Scenario system**: templated, replayable interoperability test scenarios. Definitions load from
`data/scenarios_seed_data.json` via `seed_scenarios_from_json.py` (not from raw HL7/HPRIM files anymore).
`scenario_runner.py` executes them, `scenario_capture.py` can snapshot an existing dossier into a new
template, `scenario_dashboard.py` / `scenario_status_service.py` track run state.

**Multi-tenancy**: entities are scoped under GHT → EJ (Entité Juridique) → structure tree. `app/routers/ght/`
(ej.py, structure.py) and `app/middleware/ght_context.py` carry the current GHT/EJ context through requests.

**Identifiers/namespaces**: `app/services/identifier_manager.py` centralizes OID/URI/name namespace
handling shared between HL7v2 (OID-based) and FHIR (URI-based) — see `docs/NAMESPACES_CLARIFICATION.md`
before touching identifier code, the two systems are not naively interchangeable.

**Config**: `config/settings.py` is a plain class reading `os.getenv(...)` (not pydantic-settings despite
the dependency being installed) — add new settings there, not scattered `os.getenv` calls. `.env` is
loaded via `python-dotenv` in `app/app.py`; see `.env.example` for the full variable set (DB, JWT/session
secrets, CORS, PID13 validation strictness, MLLP tracing, cache TTL, etc.). `PUBLIC_SEARCH` (default true)
deliberately makes `/cotation-modern/search` unauthenticated to support qualification/E2E testing — this
is intentional, not an oversight.

**Admin**: SQLAdmin views are registered in `app/admin/` and mounted at `/sqladmin` for direct DB
inspection/editing.
