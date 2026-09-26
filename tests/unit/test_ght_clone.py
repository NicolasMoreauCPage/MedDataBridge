"""Tests du clonage d'un environnement GHT vers un logiciel connecté."""

import pytest
from sqlmodel import Session, select

from app.models_endpoints import FHIRConfig, MLLPConfig
from app.models_scenario_config import ScenarioEJConfig
from app.models_shared import SystemEndpoint
from app.models_structure import (
    Chambre,
    EntiteGeographique,
    EntiteJuridique,
    GHTContext,
    Lit,
    Pole,
    Service,
    UniteFonctionnelle,
    UniteHebergement,
)
from app.services.ght_clone import clone_ght_context, normalize_connected_software_url


def _source_ght(session: Session) -> tuple[GHTContext, EntiteJuridique]:
    """Create the smallest complete structure and two endpoint types."""
    source = GHTContext(
        name="GHT source",
        code="GHT-SOURCE-CLONE",
        fhir_server_url="https://ancienne-version.example.test/fhir",
    )
    session.add(source)
    session.flush()

    ej = EntiteJuridique(
        identifier="ej-source-ght-clone",
        name="EJ source",
        finess_ej="123456789",
        ght_context_id=source.id,
    )
    session.add(ej)
    session.flush()
    eg = EntiteGeographique(identifier="eg-source-ght-clone", name="Site source", entite_juridique_id=ej.id)
    session.add(eg)
    session.flush()
    pole = Pole(identifier="pole-source-ght-clone", name="Pôle source", entite_geo_id=eg.id, entite_juridique_id=ej.id)
    session.add(pole)
    session.flush()
    service = Service(identifier="service-source-ght-clone", name="Service source", pole_id=pole.id)
    session.add(service)
    session.flush()
    uf = UniteFonctionnelle(identifier="uf-source-ght-clone", name="UF source", service_id=service.id)
    session.add(uf)
    session.flush()
    uh = UniteHebergement(identifier="uh-source-ght-clone", name="UH source", unite_fonctionnelle_id=uf.id)
    session.add(uh)
    session.flush()
    chambre = Chambre(identifier="chambre-source-ght-clone", name="Chambre source", unite_hebergement_id=uh.id)
    session.add(chambre)
    session.flush()
    session.add(Lit(identifier="lit-source-ght-clone", name="Lit source", chambre_id=chambre.id))
    session.add(ScenarioEJConfig(entite_juridique_id=ej.id, uf_hospitalisation_id=uf.id))

    fhir = SystemEndpoint(
        name="FHIR du logiciel connecté",
        kind="FHIR",
        role="sender",
        ght_context_id=source.id,
        entite_juridique_id=ej.id,
        base_url="https://ancienne-version.example.test/fhir",
    )
    mllp = SystemEndpoint(
        name="MLLP sortant du logiciel connecté",
        kind="MLLP",
        role="sender",
        ght_context_id=source.id,
        entite_juridique_id=ej.id,
        host="ancienne-version.example.test",
        port=2575,
    )
    session.add_all([fhir, mllp])
    session.flush()
    session.add(FHIRConfig(name="FHIR config", base_url=fhir.base_url, endpoint_id=fhir.id))
    session.add(MLLPConfig(name="MLLP config", host=mllp.host, port=2575, sending_app="BRIDGE", sending_facility="GHT", endpoint_id=mllp.id))
    session.commit()
    return source, ej


def test_clone_ght_copies_structure_and_redirects_connected_endpoints(session: Session):
    source, source_ej = _source_ght(session)

    result = clone_ght_context(
        session,
        source,
        new_name="GHT recette",
        new_code="GHT-RECETTE-CLONE",
        connected_software_url="https://nouvelle-version.example.test/fhir/",
    )
    session.commit()

    assert result.context.id != source.id
    assert result.context.name == "GHT recette"
    assert result.context.fhir_server_url == "https://nouvelle-version.example.test/fhir"
    assert result.entity_count == 1
    assert result.endpoint_count == 2

    cloned_ej = session.exec(
        select(EntiteJuridique).where(EntiteJuridique.ght_context_id == result.context.id)
    ).one()
    assert cloned_ej.id != source_ej.id
    assert cloned_ej.finess_ej == source_ej.finess_ej

    cloned_eg = session.exec(
        select(EntiteGeographique).where(EntiteGeographique.entite_juridique_id == cloned_ej.id)
    ).one()
    cloned_pole = session.exec(select(Pole).where(Pole.entite_geo_id == cloned_eg.id)).one()
    cloned_service = session.exec(select(Service).where(Service.pole_id == cloned_pole.id)).one()
    cloned_uf = session.exec(select(UniteFonctionnelle).where(UniteFonctionnelle.service_id == cloned_service.id)).one()
    cloned_uh = session.exec(select(UniteHebergement).where(UniteHebergement.unite_fonctionnelle_id == cloned_uf.id)).one()
    cloned_room = session.exec(select(Chambre).where(Chambre.unite_hebergement_id == cloned_uh.id)).one()
    assert session.exec(select(Lit).where(Lit.chambre_id == cloned_room.id)).one().name == "Lit source"
    assert session.exec(
        select(ScenarioEJConfig).where(ScenarioEJConfig.entite_juridique_id == cloned_ej.id)
    ).one().uf_hospitalisation_id == cloned_uf.id

    cloned_endpoints = session.exec(
        select(SystemEndpoint).where(SystemEndpoint.ght_context_id == result.context.id)
    ).all()
    cloned_fhir = next(endpoint for endpoint in cloned_endpoints if endpoint.kind == "FHIR")
    cloned_mllp = next(endpoint for endpoint in cloned_endpoints if endpoint.kind == "MLLP")
    assert cloned_fhir.base_url == "https://nouvelle-version.example.test/fhir"
    assert session.exec(select(FHIRConfig).where(FHIRConfig.endpoint_id == cloned_fhir.id)).one().base_url == cloned_fhir.base_url
    assert cloned_mllp.host == "nouvelle-version.example.test"
    assert session.exec(select(MLLPConfig).where(MLLPConfig.endpoint_id == cloned_mllp.id)).one().host == cloned_mllp.host


@pytest.mark.parametrize("value", ["", "ftp://logiciel.test", "https://logiciel.test/fhir?mode=test"])
def test_connected_software_url_must_be_a_clean_http_url(value: str):
    with pytest.raises(ValueError):
        normalize_connected_software_url(value)
