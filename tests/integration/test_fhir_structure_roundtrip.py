"""Roundtrip complet de la structure FR Core entre deux bases indépendantes."""

from sqlalchemy import create_engine
from sqlmodel import SQLModel, Session, select

# Enregistre tous les modèles SQLModel (y compris les dépendances FK) avant
# de créer les schémas de bases temporaires.
import app.db  # noqa: F401
from app.converters.fhir_import_converter import FHIRBundleImporter
from app.models_structure import (
    Chambre,
    EntiteGeographique,
    EntiteJuridique,
    GHTContext,
    Lit,
    Pole,
    Service,
    UniteActivite,
    UniteFonctionnelle,
    UniteHebergement,
)
from app.services.fhir_export_service import FHIRExportService


def _create_context(engine, with_hierarchy: bool) -> int:
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        ght = GHTContext(name="GHT roundtrip", code="GHT-FHIR-RT")
        session.add(ght)
        session.flush()
        ej = EntiteJuridique(
            name="EJ source" if with_hierarchy else "EJ destination",
            identifier="EJ-RT",
            finess_ej="750000010",
            ght_context_id=ght.id,
        )
        session.add(ej)
        session.flush()

        if with_hierarchy:
            eg = EntiteGeographique(
                name="Site central", identifier="EG-RT", finess="750000028",
                entite_juridique_id=ej.id,
            )
            session.add(eg)
            session.flush()
            pole = Pole(name="Pôle médecine", identifier="POLE-RT", entite_geo_id=eg.id)
            session.add(pole)
            session.flush()
            service = Service(name="Cardiologie", identifier="SERV-RT", pole_id=pole.id)
            session.add(service)
            session.flush()
            uf = UniteFonctionnelle(name="UF cardio", identifier="UF-RT", service_id=service.id)
            session.add(uf)
            session.flush()
            session.add(UniteActivite(name="UAC cardio", identifier="UAC-RT", unite_fonctionnelle_id=uf.id))
            uh = UniteHebergement(name="UH cardio", identifier="UH-RT", unite_fonctionnelle_id=uf.id)
            session.add(uh)
            session.flush()
            chambre = Chambre(name="Chambre 101", identifier="CH-RT", unite_hebergement_id=uh.id)
            session.add(chambre)
            session.flush()
            session.add(Lit(name="Lit A", identifier="LIT-RT", chambre_id=chambre.id))

        session.commit()
        return ej.id


def test_fhir_structure_roundtrip_between_independent_databases():
    """Un export FR Core peut reconstruire et mettre à jour une autre base GHT."""
    source_engine = create_engine("sqlite://")
    target_engine = create_engine("sqlite://")
    source_ej_id = _create_context(source_engine, with_hierarchy=True)
    target_ej_id = _create_context(target_engine, with_hierarchy=False)

    with Session(source_engine) as source_session:
        source_ej = source_session.get(EntiteJuridique, source_ej_id)
        bundle = FHIRExportService(
            source_session, "http://localhost/fhir", enable_cache=False
        ).export_structure(source_ej).model_dump()

    assert len(bundle["entry"]) == 9  # EJ, EG, Pôle, Service, UF, UAC, UH, chambre, lit

    with Session(target_engine) as target_session:
        target_ej = target_session.get(EntiteJuridique, target_ej_id)
        importer = FHIRBundleImporter(target_session, target_ej)
        result = importer.import_bundle(bundle)
        target_session.commit()

        assert result["errors"] == []
        assert result["imported"] == 9
        assert result["organizations"] == 6
        assert result["locations"] == 3

        eg = target_session.exec(select(EntiteGeographique).where(EntiteGeographique.identifier == "EG-RT")).one()
        pole = target_session.exec(select(Pole).where(Pole.identifier == "POLE-RT")).one()
        service = target_session.exec(select(Service).where(Service.identifier == "SERV-RT")).one()
        uf = target_session.exec(select(UniteFonctionnelle).where(UniteFonctionnelle.identifier == "UF-RT")).one()
        uac = target_session.exec(select(UniteActivite).where(UniteActivite.identifier == "UAC-RT")).one()
        uh = target_session.exec(select(UniteHebergement).where(UniteHebergement.identifier == "UH-RT")).one()
        chambre = target_session.exec(select(Chambre).where(Chambre.identifier == "CH-RT")).one()
        lit = target_session.exec(select(Lit).where(Lit.identifier == "LIT-RT")).one()

        assert eg.entite_juridique_id == target_ej.id
        assert pole.entite_geo_id == eg.id
        assert service.pole_id == pole.id
        assert uf.service_id == service.id
        assert uac.unite_fonctionnelle_id == uf.id
        assert uh.unite_fonctionnelle_id == uf.id
        assert chambre.unite_hebergement_id == uh.id
        assert lit.chambre_id == chambre.id

        # Le même bundle ne crée aucun doublon : l'import est idempotent.
        second_result = FHIRBundleImporter(target_session, target_ej).import_bundle(bundle)
        target_session.commit()
        assert second_result["errors"] == []
        assert len(target_session.exec(select(EntiteGeographique)).all()) == 1
        assert len(target_session.exec(select(UniteActivite)).all()) == 1
        assert len(target_session.exec(select(Lit)).all()) == 1

    # Mise à jour métier : renommage, désactivation et déplacement de service.
    with Session(source_engine) as source_session:
        eg = source_session.exec(select(EntiteGeographique).where(EntiteGeographique.identifier == "EG-RT")).one()
        service = source_session.exec(select(Service).where(Service.identifier == "SERV-RT")).one()
        new_pole = Pole(name="Pôle chirurgie", identifier="POLE-RT-2", entite_geo_id=eg.id)
        source_session.add(new_pole)
        source_session.flush()
        service.name, service.status, service.pole_id = "Cardiologie déplacée", "inactive", new_pole.id
        source_session.add(service)
        source_session.commit()
        changed_bundle = FHIRExportService(
            source_session, "http://localhost/fhir", enable_cache=False
        ).export_structure(source_session.get(EntiteJuridique, source_ej_id)).model_dump()

    with Session(target_engine) as target_session:
        result = FHIRBundleImporter(
            target_session, target_session.get(EntiteJuridique, target_ej_id)
        ).import_bundle(changed_bundle)
        target_session.commit()
        service = target_session.exec(select(Service).where(Service.identifier == "SERV-RT")).one()
        moved_pole = target_session.exec(select(Pole).where(Pole.identifier == "POLE-RT-2")).one()
        assert result["errors"] == []
        assert service.name == "Cardiologie déplacée"
        assert service.status == "inactive"
        assert service.pole_id == moved_pole.id

        # Une référence de parent inconnue produit un verdict explicite, sans
        # créer une structure partielle silencieuse.
        invalid = {
            "resourceType": "Bundle",
            "type": "transaction",
            "entry": [{"resource": {
                "resourceType": "Location",
                "id": "UH-ORPHELINE",
                "meta": {"profile": ["https://hl7.fr/ig/fhir/core/StructureDefinition/fr-core-location"]},
                "status": "active",
                "name": "UH orpheline",
                "type": [{"coding": [{"code": "UH"}]}],
                "partOf": {"reference": "Organization/UF-INEXISTANTE"},
            }}],
        }
        invalid_result = FHIRBundleImporter(target_session, target_session.get(EntiteJuridique, target_ej_id)).import_bundle(invalid)
        assert invalid_result["imported"] == 0
        assert "parent UF" in invalid_result["errors"][0]["error"]
