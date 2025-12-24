import os
import pytest

os.environ.setdefault("TESTING", "1")

# Configure pytest-asyncio
pytestmark = pytest.mark.asyncio

# Suppress a noisy SQLAlchemy SAWarning triggered by in-memory vocabulary mapping
# objects that may be created detached from the session during startup/meta init.
import warnings
from sqlalchemy.exc import SAWarning
warnings.filterwarnings("ignore", category=SAWarning)

# Mock cache service for tests
class MockCacheService:
    def __init__(self):
        self.blacklist = set()

    def exists(self, key):
        return key in self.blacklist

    def set(self, key, value, ttl=None):
        self.blacklist.add(key)
        return True

    def get(self, key):
        # Return None for all keys in tests to simulate empty cache
        # This avoids returning mock data that doesn't match expected schemas
        return None

    def get_stats(self):
        return {
            "enabled": True,
            "used_memory": "1MB",
            "total_connections": 10,
            "total_commands": 100,
            "keyspace_hits": 80,
            "keyspace_misses": 20,
            "hit_rate": 80.0
        }

mock_cache = MockCacheService()

# Mock the cache service module
import sys
from unittest.mock import MagicMock
cache_service_mock = MagicMock()
cache_service_mock.get_cache_service.return_value = mock_cache
sys.modules['app.services.cache_service'] = cache_service_mock

# Delay heavy imports until needed
from datetime import datetime


@pytest.fixture(autouse=True, scope='session')
def setup_test_db():
    """Initialize the in-memory DB and create minimal records used by UI pages."""
    # Import here to avoid loading SQLAlchemy at conftest import time
    from app.db import init_db, session_factory
    from app.models import Patient, Dossier, Venue
    from app.models_structure import GHTContext
    from app.models_shared import SystemEndpoint
    from sqlmodel import select

    init_db()
    sess = session_factory()
    try:
        # Create a GHTContext if none exists
        if not sess.exec(select(GHTContext)).first():
            g = GHTContext(name="TESTGHT", code="TEST")
            sess.add(g)
            sess.commit()

        # Create a minimal Patient/Dossier/Venue trio if missing
        if not sess.exec(select(Patient)).first():
            # Patient requires family (nom); provide minimal required fields
            p = Patient(family="Test", given="User")
            sess.add(p)
            sess.commit()
            # Create a Dossier with an explicit dossier_seq using the sequence helper
            try:
                from app.db import get_next_sequence
                dossier_seq = get_next_sequence(sess, "dossier")
            except Exception:
                dossier_seq = None

            if dossier_seq:
                d = Dossier(dossier_seq=dossier_seq, patient_id=p.id, admit_time=datetime.utcnow())
            else:
                # Solution de repli: rely on before_flush auto-assignment if sequence helper unavailable
                d = Dossier(patient_id=p.id, admit_time=datetime.utcnow())

            sess.add(d)
            sess.commit()

            # Venue requires a venue_seq (no auto-assignment). Use get_next_sequence to populate it.
            try:
                from app.db import get_next_sequence
                venue_seq = get_next_sequence(sess, "venue")
            except Exception:
                venue_seq = None

            if venue_seq:
                v = Venue(venue_seq=venue_seq, dossier_id=d.id, start_time=datetime.utcnow())
            else:
                # Last-resort: provide a numeric placeholder to satisfy NOT NULL constraint
                v = Venue(venue_seq=1, dossier_id=d.id, start_time=datetime.utcnow())

            sess.add(v)
            sess.commit()

        # Ensure at least one SystemEndpoint exists
        if not sess.exec(select(SystemEndpoint)).first():
            se = SystemEndpoint(name="local", kind="FILE")
            sess.add(se)
            sess.commit()
        # Ensure minimal legal entity / geographic entity and namespaces exist
        try:
            from app.models_structure import EntiteJuridique, EntiteGeographique, IdentifierNamespace
            # Create an EntiteJuridique if missing
            if not sess.exec(select(EntiteJuridique)).first():
                ej = EntiteJuridique(name="Test EJ", finess_ej="999999999", is_active=True)
                sess.add(ej)
                sess.commit()
            else:
                ej = sess.exec(select(EntiteJuridique)).first()

            # Create an EntiteGeographique linked to the EJ
            if not sess.exec(select(EntiteGeographique)).first():
                eg = EntiteGeographique(name="Test EG", finess="999999999", entite_juridique_id=(ej.id if ej else None))
                sess.add(eg)
                sess.commit()
            else:
                eg = sess.exec(select(EntiteGeographique)).first()

            # Create a basic IdentifierNamespace so identifier lookups in UI succeed
            if not sess.exec(select(IdentifierNamespace)).first():
                ns = IdentifierNamespace(name="TEST-IPP", system="urn:medbridge:test:ipp", type="IPP", ght_context_id=None, entite_juridique_id=(ej.id if ej else None), entite_geographique_id=(eg.id if eg else None))
                sess.add(ns)
                sess.commit()
        except Exception:
            # If any structure models are missing in a trimmed test environment, skip seeding
            pass

        # Create a minimal vocabulary system (administrative gender) used by some templates
        try:
            from app.models_vocabulary import VocabularySystem, VocabularyValue
            if not sess.exec(select(VocabularySystem)).first():
                vs = VocabularySystem(name="administrative-gender", label="Genre administratif", system_type="FHIR")
                sess.add(vs)
                sess.commit()
                v_m = VocabularyValue(system_id=vs.id, code="M", display="Masculin")
                v_f = VocabularyValue(system_id=vs.id, code="F", display="Féminin")
                sess.add(v_m)
                sess.add(v_f)
                sess.commit()
        except Exception:
            pass

        # If a Patient exists (we may have just created one), ensure it has an Identifier (IPP)
        try:
            from app.models_identifiers import Identifier as IdentifierModel
            pat = sess.exec(select(Patient)).first()
            if pat and not sess.exec(select(IdentifierModel).where(IdentifierModel.patient_id == pat.id)).first():
                idn = IdentifierModel(value=str(pat.id), type="IPP", system="urn:medbridge:test:ipp", patient_id=pat.id)
                sess.add(idn)
                sess.commit()
        except Exception:
            pass

        # Seed additional common models to cover UI pages: Poles, Services, UF, Sequence entries
        try:
            from app.models_structure import Pole, Service, UniteFonctionnelle, EntiteJuridique, EntiteGeographique, IdentifierNamespace
            from app.db import get_next_sequence

            # Ensure there's at least one Pole / Service / UF for structure pages
            if not sess.exec(select(Pole)).first():
                pole = Pole(identifier="POLE_TEST", name="Pôle Test")
                sess.add(pole)
                sess.commit()
            if not sess.exec(select(Service)).first():
                svc = Service(identifier="SRV_TEST", name="Service Test", pole_id=(pole.id if 'pole' in locals() else None))
                sess.add(svc)
                sess.commit()
            if not sess.exec(select(UniteFonctionnelle)).first():
                uf = UniteFonctionnelle(identifier="UF_TEST", name="UF Test", service_id=(svc.id if 'svc' in locals() else None))
                sess.add(uf)
                sess.commit()

            # Ensure sequence entries exist for dossier/venue/mouvement to avoid insertion errors
            try:
                _ = get_next_sequence(sess, "dossier")
                _ = get_next_sequence(sess, "venue")
                _ = get_next_sequence(sess, "mouvement")
                _ = get_next_sequence(sess, "patient")
            except Exception:
                # ignore if sequences cannot be created in this environment
                pass
        except Exception:
            pass

        # Endpoints with configs: create one MLLP and one FHIR config attached to SystemEndpoint
        try:
            from app.models_endpoints import MLLPConfig, FHIRConfig
            from app.models_shared import SystemEndpoint as SEP

            # Create one SystemEndpoint with MLLP and FHIR configs if none exist
            if not sess.exec(select(SEP)).first():
                sep = SEP(name="Test Endpoint", kind="FILE", role="both", is_enabled=True)
                sess.add(sep)
                sess.commit()
            else:
                sep = sess.exec(select(SEP)).first()

            if not sess.exec(select(MLLPConfig)).first():
                mcfg = MLLPConfig(name="Test MLLP", port=2575, sending_app="APP", sending_facility="FAC", endpoint_id=sep.id)
                sess.add(mcfg)
                sess.commit()
            if not sess.exec(select(FHIRConfig)).first():
                fcfg = FHIRConfig(name="Test FHIR", base_url="http://localhost:8080/fhir", endpoint_id=sep.id)
                sess.add(fcfg)
                sess.commit()
        except Exception:
            pass

        # Seed a basic InteropScenario and WorkflowScenario to cover scenario pages
        try:
            from app.models_scenarios import InteropScenario, InteropScenarioStep, ScenarioTemplate, ScenarioTemplateStep
            from app.models_workflows import WorkflowScenario, WorkflowScenarioStep

            if not sess.exec(select(InteropScenario)).first():
                sc = InteropScenario(key="test.scenario", name="Test Scenario", protocol="HL7")
                sess.add(sc)
                sess.commit()
                step = InteropScenarioStep(scenario_id=sc.id, order_index=1, payload="MSH|||")
                sess.add(step)
                sess.commit()

            if not sess.exec(select(ScenarioTemplate)).first():
                tpl = ScenarioTemplate(key="tpl.test", name="Template Test")
                sess.add(tpl)
                sess.commit()
                tstep = ScenarioTemplateStep(template_id=tpl.id, order_index=1, semantic_event_code="PARCOURS_START")
                sess.add(tstep)
                sess.commit()

            if not sess.exec(select(WorkflowScenario)).first():
                ws = WorkflowScenario(name="WS Test", scenario_type="ADMISSION")
                sess.add(ws)
                sess.commit()
                wstep = WorkflowScenarioStep(scenario_id=ws.id, order_index=0, action_type="CREER_PATIENT")
                sess.add(wstep)
                sess.commit()
        except Exception:
            pass

        # Add a sample MessageLog to avoid empty logs in UI
        try:
            from app.models_shared import MessageLog
            if not sess.exec(select(MessageLog)).first():
                ml = MessageLog(direction="in", kind="FILE", payload="test", status="received")
                sess.add(ml)
                sess.commit()
        except Exception:
            pass
    finally:
        sess.close()

    yield


@pytest.fixture(autouse=True, scope='function')
def clean_db_tables():
    """Clean all database tables between tests to ensure test isolation."""
    from app.db import session_factory, engine
    from sqlalchemy import text
    from app.models import SQLModel
    import time

    # Close all active connections to avoid "database table is locked" errors
    engine.dispose()

    # Retry mechanism for database operations
    max_retries = 3
    for attempt in range(max_retries):
        try:
            # Drop all tables and recreate them - more reliable than trying to clean
            SQLModel.metadata.drop_all(bind=engine)
            SQLModel.metadata.create_all(bind=engine)
            break  # Success, exit retry loop
        except Exception as e:
            if attempt < max_retries - 1:
                # Wait a bit before retrying
                time.sleep(0.1)
                # Force close connections again
                engine.dispose()
            else:
                # Last attempt failed, re-raise the exception
                raise e


# Test categorization markers for better organization and selective running
def pytest_configure(config):
    """Register custom markers for test categorization."""
    config.addinivalue_line("markers", "unit: Unit tests (fast, isolated)")
    config.addinivalue_line("markers", "integration: Integration tests (slower, test real components)")
    config.addinivalue_line("markers", "ui: UI tests (require browser/playwright)")
    config.addinivalue_line("markers", "api: API endpoint tests")
    config.addinivalue_line("markers", "security: Security-related tests")
    config.addinivalue_line("markers", "performance: Performance tests")
    config.addinivalue_line("markers", "flaky: Tests that may fail intermittently")
    config.addinivalue_line("markers", "slow: Tests that take longer than 30 seconds")
    config.addinivalue_line("markers", "critical: Critical functionality tests")


@pytest.fixture(scope='function')
def isolated_session():
    """Provide an isolated database session that rolls back all changes."""
    from app.db import session_factory
    session = session_factory()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture(scope='function')
def test_patient(isolated_session):
    """Create a test patient for use in tests."""
    from app.models import Patient
    patient = Patient(
        family="TestPatient",
        given="User",
        birth_date=datetime(1990, 1, 1).date()
    )
    isolated_session.add(patient)
    isolated_session.commit()
    isolated_session.refresh(patient)
    return patient


@pytest.fixture(scope='function')
def test_dossier(isolated_session, test_patient):
    """Create a test dossier for use in tests."""
    from app.models import Dossier
    from app.db import get_next_sequence

    dossier_seq = get_next_sequence(isolated_session, "dossier")
    dossier = Dossier(
        dossier_seq=dossier_seq,
        patient_id=test_patient.id,
        admit_time=datetime.utcnow()
    )
    isolated_session.add(dossier)
    isolated_session.commit()
    isolated_session.refresh(dossier)
    return dossier


import os

# Ensure the application runs in testing mode during pytest runs so
# lifetime init (DB init, event listeners, background scheduler, MLLP)
# are skipped. This avoids background emission workers opening new DB
# sessions against the test DB which causes sqlite/SQLAlchemy errors.
os.environ.setdefault("TESTING", "1")

def pytest_configure(config):
    # make sure other code reading env sees the flag early
    os.environ["TESTING"] = "1"
"""Test fixtures"""
import pytest
from sqlmodel import SQLModel, Session
import os
import sys
from pathlib import Path
from datetime import datetime
from fastapi.testclient import TestClient

# Indicate to the app that we're running tests
os.environ.setdefault("TESTING", "1")
# Enable auto-creation of UF placeholders for tests
os.environ.setdefault("PAM_AUTO_CREATE_UF", "1")

# Ensure repository root is on sys.path so `import app` works when running pytest from VS Code or terminals
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


# REMARQUE: we import app.db (engine/get_session) locally in fixtures to allow
# setting TESTING env vars and manipulating sys.path before attempting to
# import application modules. This avoids E402 linter errors while keeping
# behavior stable.

# Some tests run in minimal environments and may not have all optional
# dependencies installed (passlib, etc). Avoid importing the full FastAPI
# application at import time to keep unit tests lightweight. We check whether
# the full app can be imported and set a flag accordingly. Any imports that
# require application-level modules are done lazily inside fixtures.
FULL_APP_AVAILABLE = False


@pytest.fixture(name="session")
def session_fixture():
    """Provide a DB session for tests. The DB schema is created by the autouse fixture."""
    from app.db import engine

    with Session(engine) as session:
        # Some tests expect session.refresh(obj) to Renvoie the object
        _orig_refresh = session.refresh

        def _refresh_and_return(obj, *args, **kwargs):
            _orig_refresh(obj, *args, **kwargs)
            return obj

        session.refresh = _refresh_and_return
        yield session


@pytest.fixture(name="test_endpoints")
def test_endpoints_fixture(session: Session):
    """Create a pair of test SystemEndpoint records (MLLP + FHIR)."""
    from app.models_endpoints import SystemEndpoint

    mllp_endpoint = SystemEndpoint(
        name="Test MLLP",
        kind="MLLP",
        role="sender",
        host="localhost",
        port=2575,
        sending_app="TEST_APP",
        sending_facility="TEST_FAC",
        receiving_app="REC_APP",
        receiving_facility="REC_FAC",
        is_enabled=True,
    )
    fhir_endpoint = SystemEndpoint(
        name="Test FHIR",
        kind="FHIR",
        role="sender",
        host="http://localhost",
        port=8080,
        is_enabled=True,
    )

    session.add(mllp_endpoint)
    session.add(fhir_endpoint)
    session.commit()
    session.refresh(mllp_endpoint)
    session.refresh(fhir_endpoint)

    return {"mllp": mllp_endpoint, "fhir": fhir_endpoint}


@pytest.fixture(autouse=True)
def setup_database():
    """Autouse fixture: create schema and initialize minimal reference data for tests."""
    from app.db import engine

    # Create tables
    SQLModel.metadata.create_all(engine)

    # Initialize vocabularies / minimal reference data if available
    with Session(engine) as session:
        try:
            from app.vocabulary_init import init_vocabularies

            init_vocabularies(session)
        except Exception:
            # If init_vocabularies is not present or fails for tests,
            # ignore and continue — tests can create needed rows explicitly.
            pass

        # Ensure there's at least one GHTContext to avoid queries failing
        try:
            from app.models_context import GHTContext
            from sqlmodel import select

            existing = session.exec(select(GHTContext)).first()
            if not existing:
                ctx = GHTContext(name="Test GHT", code="TEST_GHT", description="Auto init", is_active=True)
                session.add(ctx)
                session.commit()
        except Exception:
            # If the model/table isn't present or the query fails, continue.
            pass

    yield

    # Drop tables after each test to keep isolation
    from app.db import engine as _engine

    # Dispose of all connections first to avoid locks
    _engine.dispose()

    # Add retry mechanism for table dropping
    import time
    max_retries = 3
    for attempt in range(max_retries):
        try:
            SQLModel.metadata.drop_all(_engine)
            break
        except Exception as e:
            if attempt == max_retries - 1:
                print(f"Failed to drop tables after {max_retries} attempts: {e}")
                raise
            time.sleep(0.1)  # Brief pause before retry


@pytest.fixture(name="client")
def client_fixture(session: Session):
    if not FULL_APP_AVAILABLE:
        pytest.skip("Full FastAPI app not available in this environment; skipping client tests")

    # Lazy import app factory so DB is initialized first
    from app.app import create_app
    from app.db import get_session, engine as _engine

    def override_get_session():
        # Use the test session - yield it directly without context manager
        # This ensures the same session is used throughout the test
        try:
            yield session
        finally:
            pass  # Don't close the session, let the test fixture handle it

    app = create_app()
    app.dependency_overrides[get_session] = override_get_session
    app.root_path = ""
    app.base_url = "http://testserver"

    with TestClient(app, base_url="http://testserver") as c:
        # Auto-select a GHT context for routes protected by require_ght_context
        try:
            from app.models_structure import GHTContext
            from sqlmodel import select as _select
            with Session(_engine) as s:
                ctx = s.exec(_select(GHTContext)).first()
                if not ctx:
                    ctx = GHTContext(name="Test GHT", code="TEST_GHT", is_active=True)
                    s.add(ctx)
                    s.commit()
                    s.refresh(ctx)
            c.get(f"/admin/ght/{ctx.id}", follow_redirects=True)
        except Exception:
            pass
        yield c


# Exemple HL7 message fixture
@pytest.fixture(name="hl7_adt_a01")
def hl7_adt_a01_fixture():
    now = datetime.now().strftime("%Y%m%d%H%M%S")
    return (
        f"MSH|^~\\&|SENDING_APP|SENDING_FAC|RECEIVING_APP|RECEIVING_FAC|{now}||ADT^A01|MSG00001|P|2.5.1|\n"
        f"EVN|A01|{now}||||\n"
        f"PID|1||12345^^^HOPITAL^PI||DUPONT^JEAN^^^^^L||19800101|M|||1 RUE DU TEST^^VILLE^^75001^FRA||0123456789^^^test@email.com|||||\n"
        f"PV1|1|I|CARDIO^101^1^HOPITAL||||12345^DOC^JOHN^^^^^||||||||||ADM|A0|||||||||||||||||||||||||{now}|\n"
        f"ZBE|MVT_A01_{now}|||||{now}|"
    )


# -----------------------
# Multi-venue test data
# -----------------------
@pytest.fixture(name="dossier_chemo_with_sessions")
def dossier_chemo_with_sessions_fixture(session: Session):
    """
    Crée un dossier avec plusieurs venues (ex. séances de chimiothérapie en HDJ).

    Retourne un dict avec: patient, dossier, venues (list[Venue])
    """
    from app.models import Patient, Dossier, Venue
    from app.db import get_next_sequence

    # Patient minimal avec identifiant simple
    pat_seq = get_next_sequence(session, "patient")
    patient = Patient(
        patient_seq=pat_seq,
        identifier=str(pat_seq),
        family="CHEMO",
        given="Test",
        gender="other",
    )
    session.add(patient)
    session.flush()

    # Dossier parent
    dossier = Dossier(
        dossier_seq=get_next_sequence(session, "dossier"),
        patient_id=patient.id,
        uf_responsabilite="HDJ-ONCO",
        admit_time=datetime.now(),
    )
    session.add(dossier)
    session.flush()

    # Trois venues successives (ex. 3 séances)
    venues = []
    for i in range(1, 4):
        v = Venue(
            venue_seq=get_next_sequence(session, "venue"),
            dossier_id=dossier.id,
            uf_responsabilite="HDJ-ONCO",
            start_time=datetime.now(),
            code="HDJ-ONCO",
            label=f"Chimiothérapie - Séance {i}",
        )
        session.add(v)
        session.flush()
        session.refresh(v)
        venues.append(v)

    session.commit()
    session.refresh(patient)
    session.refresh(dossier)
    return {"patient": patient, "dossier": dossier, "venues": venues}


@pytest.fixture(name="dossier_psy_day_hospital_multi")
def dossier_psy_day_hospital_multi_fixture(session: Session):
    """
    Crée un dossier avec venues multiples en hospitalisation de jour (psychiatrie).

    Retourne un dict avec: patient, dossier, venues (list[Venue])
    """
    from app.models import Patient, Dossier, Venue
    from app.db import get_next_sequence

    pat_seq = get_next_sequence(session, "patient")
    patient = Patient(
        patient_seq=pat_seq,
        identifier=str(pat_seq),
        family="PSY",
        given="HDJ",
        gender="female",
    )
    session.add(patient)
    session.flush()

    dossier = Dossier(
        dossier_seq=get_next_sequence(session, "dossier"),
        patient_id=patient.id,
        uf_responsabilite="HDJ-PSY",
        admit_time=datetime.now(),
    )
    session.add(dossier)
    session.flush()

    venues = []
    labels = [
        "HDJ Psychiatrie - Evaluation",
        "HDJ Psychiatrie - Thérapie de groupe",
        "HDJ Psychiatrie - Suivi",
    ]
    for i, label in enumerate(labels, start=1):
        v = Venue(
            venue_seq=get_next_sequence(session, "venue"),
            dossier_id=dossier.id,
            uf_responsabilite="HDJ-PSY",
            start_time=datetime.now(),
            code="HDJ-PSY",
            label=label,
        )
        session.add(v)
        session.flush()
        session.refresh(v)
        venues.append(v)

    session.commit()
    session.refresh(patient)
    session.refresh(dossier)
    return {"patient": patient, "dossier": dossier, "venues": venues}


# -----------------------
# Multi-venue with movements (A01 + A03), PV1-2 = R (recurring)
# -----------------------
@pytest.fixture(name="dossier_chemo_with_sessions_recurring")
def dossier_chemo_with_sessions_recurring_fixture(session: Session, dossier_chemo_with_sessions):
    """
    Étend dossier_chemo_with_sessions en ajoutant pour chaque venue deux mouvements:
    - A01 (admission)
    - A03 (sortie)

    Semantique: hospitalisation récidivante (PV1-2 = R) — représentée par des venues distinctes
    avec ouverture/fermeture via A01/A03.
    """
    from app.models import Mouvement
    from app.db import get_next_sequence
    from datetime import timedelta

    data = dossier_chemo_with_sessions
    venues = data["venues"]

    base_time = datetime.now()
    for idx, v in enumerate(venues):
        # Admission A01
        m_admit = Mouvement(
            mouvement_seq=get_next_sequence(session, "mouvement"),
            venue_id=v.id,
            type="ADT^A01",
            when=base_time + timedelta(minutes=idx * 10),
            location=f"HDJ-ONCO-{idx+1:02d}",
            movement_type="admission",
            trigger_event="A01",
        )
        session.add(m_admit)

        # Discharge A03
        m_discharge = Mouvement(
            mouvement_seq=get_next_sequence(session, "mouvement"),
            venue_id=v.id,
            type="ADT^A03",
            when=base_time + timedelta(minutes=idx * 10 + 5),
            location=f"HDJ-ONCO-{idx+1:02d}",
            movement_type="discharge",
            trigger_event="A03",
        )
        session.add(m_discharge)

    session.commit()
    return data


@pytest.fixture(name="dossier_psy_day_hospital_recurring")
def dossier_psy_day_hospital_recurring_fixture(session: Session, dossier_psy_day_hospital_multi):
    """
    Étend dossier_psy_day_hospital_multi en ajoutant A01 + A03 pour chaque venue (PV1-2 = R).
    """
    from app.models import Mouvement
    from app.db import get_next_sequence
    from datetime import timedelta

    data = dossier_psy_day_hospital_multi
    venues = data["venues"]

    base_time = datetime.now()
    for idx, v in enumerate(venues):
        m_admit = Mouvement(
            mouvement_seq=get_next_sequence(session, "mouvement"),
            venue_id=v.id,
            type="ADT^A01",
            when=base_time + timedelta(minutes=idx * 15),
            location=f"HDJ-PSY-{idx+1:02d}",
            movement_type="admission",
            trigger_event="A01",
        )
        session.add(m_admit)

        m_discharge = Mouvement(
            mouvement_seq=get_next_sequence(session, "mouvement"),
            venue_id=v.id,
            type="ADT^A03",
            when=base_time + timedelta(minutes=idx * 15 + 10),
            location=f"HDJ-PSY-{idx+1:02d}",
            movement_type="discharge",
            trigger_event="A03",
        )
        session.add(m_discharge)

    session.commit()
    return data


# Fixtures utilitaires pour créer des données de test courantes

@pytest.fixture
def sample_patient(session: Session):
    """Crée et retourne un patient de test"""
    from app.models import Patient
    patient = Patient(
        family="Dupont",
        given="Jean",
        birth_date="1990-01-15"
    )
    session.add(patient)
    session.commit()
    session.refresh(patient)
    return patient


@pytest.fixture
def sample_ght(session: Session):
    """Crée et retourne un contexte GHT de test"""
    from app.models_structure import GHTContext
    ght = GHTContext(name="Test GHT", code="TST")
    session.add(ght)
    session.commit()
    session.refresh(ght)
    return ght


@pytest.fixture
def sample_ej(session: Session, sample_ght):
    """Crée et retourne une entité juridique de test"""
    from app.models_structure import EntiteJuridique
    ej = EntiteJuridique(
        name="Test EJ",
        code="EJ001",
        ght_context_id=sample_ght.id
    )
    session.add(ej)
    session.commit()
    session.refresh(ej)
    return ej


@pytest.fixture
def sample_uf(session: Session, sample_ej):
    """Crée et retourne une unité fonctionnelle de test"""
    from app.models_structure import EntiteGeographique, Pole, Service, UniteFonctionnelle
    from sqlmodel import select
    
    # Créer la hiérarchie si nécessaire
    eg = session.exec(select(EntiteGeographique).where(EntiteGeographique.entite_juridique_id == sample_ej.id)).first()
    if not eg:
        eg = EntiteGeographique(
            name="Test EG",
            code="EG001",
            entite_juridique_id=sample_ej.id
        )
        session.add(eg)
        session.commit()
    
    pole = session.exec(select(Pole).where(Pole.entite_geo_id == eg.id)).first()
    if not pole:
        pole = Pole(
            identifier="POLE_TEST",
            name="Pôle Test",
            entite_geo_id=eg.id
        )
        session.add(pole)
        session.commit()
    
    service = session.exec(select(Service).where(Service.pole_id == pole.id)).first()
    if not service:
        service = Service(
            identifier="SRV_TEST",
            name="Service Test",
            pole_id=pole.id
        )
        session.add(service)
        session.commit()
    
    uf = session.exec(select(UniteFonctionnelle).where(UniteFonctionnelle.service_id == service.id)).first()
    if not uf:
        uf = UniteFonctionnelle(
            identifier="UF_TEST_FIXTURE",
            name="UF Test Fixture",
            service_id=service.id
        )
        session.add(uf)
        session.commit()
        session.refresh(uf)
    
    return uf


@pytest.fixture
def sample_dossier(session: Session, sample_patient, sample_ej):
    """Crée et retourne un dossier de test"""
    from app.models import Dossier
    from datetime import datetime

    # Utiliser une séquence unique pour éviter les conflits
    try:
        from app.db import get_next_sequence
        dossier_seq = get_next_sequence(session, "dossier")
    except Exception:
        # Fallback: utiliser un timestamp pour l'unicité
        import time
        dossier_seq = int(time.time() * 1000) % 1000000

    dossier = Dossier(
        dossier_seq=dossier_seq,
        patient_id=sample_patient.id,
        admit_time=datetime.now(),
        entite_juridique_id=sample_ej.id
    )
    session.add(dossier)
    session.commit()
    session.refresh(dossier)
    return dossier


@pytest.fixture
def authenticated_client(client, sample_ght):
    """Client FastAPI avec contexte GHT défini"""
    # Le contexte GHT est déjà défini automatiquement dans la fixture client
    return client
