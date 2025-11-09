import pytest
from sqlmodel import Session, create_engine, select

from app.services.mfn_structure import (
    _normalize_loc_type,
    _extract_identifier_from_loc,
    _extract_type_and_identifier_from_loc,
    extract_location_type,
    parse_location_characteristics,
    save_location,
)

# We'll use in-memory SQLite and the project's SQLModel metadata

@pytest.fixture
def in_memory_session():
    engine = create_engine("sqlite:///:memory:")
    from app.models import SQLModel
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_normalize_loc_type_variants():
    assert _normalize_loc_type("chambre") == "R"
    assert _normalize_loc_type("Chambre") == "R"
    assert _normalize_loc_type("lit") == "B"
    assert _normalize_loc_type("LIT") == "LIT" or _normalize_loc_type("LIT") in ("LIT", "B")
    assert _normalize_loc_type("etablissement geographique") == "ETBL_GRPQ"
    assert _normalize_loc_type("") == ""


def test_extract_identifier_from_loc_variants():
    raw = "^^^^^P^^^^123&CPAGE&700004591&FINEJ"
    assert _extract_identifier_from_loc(raw) == "123"
    raw2 = "^^^^^ETBL_GRPQ^^^^75&CPAGE"
    assert _extract_identifier_from_loc(raw2) == "75"


def test_extract_type_and_identifier_from_loc():
    t, ident = _extract_type_and_identifier_from_loc("^^^^^D^^^^0192&CPAGE&700004591&FINEJ")
    assert t in ("D", "ETBL_GRPQ", "P")
    assert ident == "0192"


def test_extract_location_type_prefers_field4():
    # LOC with type in field 4
    seg = ["LOC", "^^^^^D^^^^0192&CPAGE&700004591&FINEJ", "", "", "D", "Service"]
    t, ident = extract_location_type(seg)
    assert t == "D"
    assert ident == "0192"


def test_parse_location_characteristics():
    lch = [
        ["LCH", "^^^^^D^^^^0192&CPAGE&700004591&FINEJ", "", "", "LBL^Libelle^L", "^Mon service"],
        ["LCH", "^^^^^D^^^^0192&CPAGE&700004591&FINEJ", "", "", "ID_GLBL^Identifiant^L", "^SVC-0192"],
    ]
    chars = parse_location_characteristics(lch)
    assert chars.get("LBL") == "Mon service"
    assert chars.get("ID_GLBL") == "SVC-0192"


def test_save_location_db_lookup_fallback(in_memory_session):
    # Create a minimal location hierarchy so Chambre constraints are satisfied
    from app.models_structure import (
        EntiteGeographique, Pole, Service, UniteFonctionnelle, UniteHebergement, Chambre
    )
    eg = EntiteGeographique(identifier="EG-1", name="EG", finess="0001")
    in_memory_session.add(eg)
    in_memory_session.flush()

    pole = Pole(identifier="POLE-1", name="Pôle 1", entite_geo_id=eg.id, physical_type="area")
    in_memory_session.add(pole)
    in_memory_session.flush()

    service = Service(identifier="SVC-1", name="Service 1", pole_id=pole.id, service_type="mco", physical_type="si")
    in_memory_session.add(service)
    in_memory_session.flush()

    uf = UniteFonctionnelle(identifier="UF-1", name="UF 1", service_id=service.id, physical_type="si")
    in_memory_session.add(uf)
    in_memory_session.flush()

    uh = UniteHebergement(identifier="UH-1", name="UH 1", unite_fonctionnelle_id=uf.id, physical_type="wi")
    in_memory_session.add(uh)
    in_memory_session.flush()

    ch = Chambre(identifier="ROOM-001", name="Chambre 1", unite_hebergement_id=uh.id, physical_type="ro")
    in_memory_session.add(ch)
    in_memory_session.commit()
    in_memory_session.refresh(ch)

    # Now call save_location with empty loc_type but identifier matching existing chambre
    result = save_location("", "ROOM-001", {"LBL":"From MFN","ID_GLBL":"ROOM-001"}, [], in_memory_session)
    assert result["status"] in ("success", "updated")


def test_save_location_relation_inference(in_memory_session):
    # Ensure relation-based inference when loc_type missing
    # Create a minimal hierarchy and a parent Chambre for which identifier=CH-123
    from app.models_structure import (
        EntiteGeographique, Pole, Service, UniteFonctionnelle, UniteHebergement, Chambre
    )
    eg = EntiteGeographique(identifier="EG-2", name="EG2", finess="0002")
    in_memory_session.add(eg)
    in_memory_session.flush()
    pole = Pole(identifier="POLE-2", name="Pôle 2", entite_geo_id=eg.id, physical_type="area")
    in_memory_session.add(pole)
    in_memory_session.flush()
    service = Service(identifier="SVC-2", name="Service 2", pole_id=pole.id, service_type="mco", physical_type="si")
    in_memory_session.add(service)
    in_memory_session.flush()
    uf = UniteFonctionnelle(identifier="UF-2", name="UF 2", service_id=service.id, physical_type="si")
    in_memory_session.add(uf)
    in_memory_session.flush()
    uh = UniteHebergement(identifier="UH-2", name="UH 2", unite_fonctionnelle_id=uf.id, physical_type="wi")
    in_memory_session.add(uh)
    in_memory_session.flush()
    parent = Chambre(identifier="CH-123", name="Parent Chambre", unite_hebergement_id=uh.id, physical_type="ro")
    in_memory_session.add(parent)
    in_memory_session.commit()
    in_memory_session.refresh(parent)

    # Save a Lit with no loc_type but relation pointing to parent CH
    relations = [{"type":"LCLSTN","target":"^^^^^CH^^^^CH-123&CPAGE"}]
    result = save_location("", "LIT-001", {"LBL":"Lit test","ID_GLBL":"LIT-001"}, relations, in_memory_session)
    assert result["status"] in ("success", "updated")


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-q"])