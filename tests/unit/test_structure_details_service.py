import pytest

from app.models_structure import EntiteGeographique, UniteFonctionnelle
from app.services.structure_details import (
    StructureEntityNotFoundError,
    UnknownStructureTypeError,
    get_structure_details,
)


def test_structure_details_projects_common_and_type_specific_fields(session):
    uf = UniteFonctionnelle(
        identifier="UF-DETAIL-1",
        name="UF de détail",
        description="Description",
        um_code="UM-42",
        address_city="Paris",
        status="inactive",
    )
    session.add(uf)
    session.commit()

    details = get_structure_details(session, entity_type="uf", entity_id=uf.id)

    assert details["id"] == uf.id
    assert details["identifier"] == "UF-DETAIL-1"
    assert details["status"] == "inactive"
    assert details["address_city"] == "Paris"
    assert details["um_code"] == "UM-42"


def test_structure_details_normalizes_enum_status_and_reports_contract_errors(session):
    eg = EntiteGeographique(identifier="EG-DETAIL-1", name="Site")
    session.add(eg)
    session.commit()

    assert get_structure_details(session, entity_type="eg", entity_id=eg.id)["status"] == "active"
    with pytest.raises(UnknownStructureTypeError, match="Type invalide"):
        get_structure_details(session, entity_type="unknown", entity_id=eg.id)
    with pytest.raises(StructureEntityNotFoundError, match="Entité non trouvée"):
        get_structure_details(session, entity_type="eg", entity_id=999_999)
