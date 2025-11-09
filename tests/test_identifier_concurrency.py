import threading
from sqlmodel import SQLModel, Session, create_engine
from sqlalchemy.pool import StaticPool
from app.models_structure_fhir import IdentifierNamespace
from app.models_identifiers import IdentifierType
from app.services.identifier_generator import generate_and_persist_identifier

GENERATED: list[str] = []

def setup_db():
    # Shared in-memory DB across threads
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return engine

def worker(engine, namespace_id: int, count: int):
    with Session(engine) as session:
        ns = session.get(IdentifierNamespace, namespace_id)
        for _ in range(count):
            val = generate_and_persist_identifier(session, ns, IdentifierType.IPP)
            GENERATED.append(val)

def test_concurrent_generation_unique():
    GENERATED.clear()
    engine = setup_db()
    # Pre-create namespace in a main session
    with Session(engine) as session:
        ns = IdentifierNamespace(
            name="Test IPP",
            system="urn:oid:1.2.3",
            type="IPP",
            prefix_pattern="9...",
            ght_context_id=1,
            is_active=True,
        )
        session.add(ns)
        session.commit()
        session.refresh(ns)
        namespace_id = ns.id

    threads = [threading.Thread(target=worker, args=(engine, namespace_id, 5)) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(GENERATED) == 50
    assert len(set(GENERATED)) == 50, "Des collisions ont été détectées malgré la génération atomique"
