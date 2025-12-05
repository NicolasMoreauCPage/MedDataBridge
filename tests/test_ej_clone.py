"""Tests de clonage d'EJ avec structure, namespaces, configuration scénarios et endpoints.

Ce module teste la fonctionnalité de clonage complet d'une EJ:
- Clonage de l'EntiteJuridique avec nouveau nom/FINESS
- Clonage des namespaces liés à l'EJ
- Clonage du ScenarioEJConfig
- Clonage de la structure (EG, Pole, Service, UF, UH, Chambre, Lit)
- Clonage des namespaces de chaque niveau de structure
- Clonage des endpoints avec leurs configurations MLLP/FHIR
"""

import pytest
from datetime import datetime
from sqlmodel import Session, select, delete
from fastapi.testclient import TestClient

from app.app import app
from app.db import engine
from app.models_structure import (
    GHTContext, EntiteJuridique, EntiteGeographique, 
    IdentifierNamespace, Pole, Service, UniteFonctionnelle,
    UniteHebergement, Chambre, Lit
)
from app.models_scenario_config import ScenarioEJConfig
from app.models_shared import SystemEndpoint
from app.models_endpoints import MLLPConfig, FHIRConfig


@pytest.fixture
def client():
    """Client de test FastAPI."""
    return TestClient(app)


@pytest.fixture
def session():
    """Session de base de données."""
    with Session(engine) as session:
        yield session


@pytest.fixture
def test_ej_with_structure(session):
    """Crée une EJ de test avec structure complète pour le clonage."""
    
    # Créer ou récupérer un contexte GHT
    context = session.exec(select(GHTContext)).first()
    if not context:
        context = GHTContext(name="GHT Test Clone", code="TEST-CLONE")
        session.add(context)
        session.commit()
        session.refresh(context)
    
    # Créer l'EJ source
    timestamp = int(datetime.utcnow().timestamp() * 1000)
    source_ej = EntiteJuridique(
        name="EJ Source Test",
        finess_ej=f"TEST{timestamp % 100000:05d}",
        identifier=f"ej-test-{timestamp}",
        ght_context_id=context.id,
        is_active=True
    )
    session.add(source_ej)
    session.flush()
    
    # Créer des namespaces pour l'EJ
    ns_ipp = IdentifierNamespace(
        name="IPP Test",
        system=f"urn:oid:1.2.3.4.{source_ej.id}.1",
        type="PI",
        entite_juridique_id=source_ej.id
    )
    ns_nda = IdentifierNamespace(
        name="NDA Test",
        system=f"urn:oid:1.2.3.4.{source_ej.id}.2",
        type="VN",
        entite_juridique_id=source_ej.id
    )
    session.add_all([ns_ipp, ns_nda])
    
    # Créer une EG
    eg = EntiteGeographique(
        name="EG Test",
        identifier=f"eg-test-{timestamp}",
        entite_juridique_id=source_ej.id
    )
    session.add(eg)
    session.flush()
    
    # Namespace pour EG
    ns_eg = IdentifierNamespace(
        name="NS EG Test",
        system=f"urn:oid:1.2.3.4.{eg.id}.1",
        type="XX",
        entite_geographique_id=eg.id
    )
    session.add(ns_eg)
    
    # Créer un Pole
    pole = Pole(
        name="Pole Test",
        identifier=f"pole-test-{timestamp}",
        entite_geo_id=eg.id,
        entite_juridique_id=source_ej.id
    )
    session.add(pole)
    session.flush()
    
    # Namespace pour Pole
    ns_pole = IdentifierNamespace(
        name="NS Pole Test",
        system=f"urn:oid:1.2.3.4.{pole.id}.1",
        type="XX",
        pole_id=pole.id
    )
    session.add(ns_pole)
    
    # Créer un Service
    service = Service(
        name="Service Test",
        identifier=f"service-test-{timestamp}",
        pole_id=pole.id
    )
    session.add(service)
    session.flush()
    
    # Créer une UF
    uf = UniteFonctionnelle(
        name="UF Test",
        identifier=f"uf-test-{timestamp}",
        service_id=service.id
    )
    session.add(uf)
    session.flush()
    
    # Namespace pour UF
    ns_uf = IdentifierNamespace(
        name="NS UF Test",
        system=f"urn:oid:1.2.3.4.{uf.id}.1",
        type="UF",
        unite_fonctionnelle_id=uf.id
    )
    session.add(ns_uf)
    
    # Créer une UH
    uh = UniteHebergement(
        name="UH Test",
        identifier=f"uh-test-{timestamp}",
        unite_fonctionnelle_id=uf.id
    )
    session.add(uh)
    session.flush()
    
    # Créer une Chambre
    chambre = Chambre(
        name="Chambre 101",
        identifier=f"chambre-test-{timestamp}",
        unite_hebergement_id=uh.id
    )
    session.add(chambre)
    session.flush()
    
    # Créer un Lit
    lit = Lit(
        name="Lit A",
        identifier=f"lit-test-{timestamp}",
        chambre_id=chambre.id
    )
    session.add(lit)
    
    # Créer le ScenarioEJConfig
    config = ScenarioEJConfig(
        entite_juridique_id=source_ej.id,
        uf_hospitalisation_id=uf.id,
        medecin_hospitalisation_rpps="10100000001",
        medecin_hospitalisation_nom="Dr TEST Pierre"
    )
    session.add(config)
    
    # Créer un endpoint de test avec config MLLP
    endpoint = SystemEndpoint(
        name="Endpoint Test Clone",
        kind="mllp",
        role="receiver",
        entite_juridique_id=source_ej.id,
        ght_context_id=context.id,
        host="0.0.0.0",
        port=6001,
        sending_app="TEST_APP",
        sending_facility="TEST_FAC"
    )
    session.add(endpoint)
    session.flush()
    
    # Créer une config MLLP pour l'endpoint
    mllp_config = MLLPConfig(
        name="MLLP Config Test",
        port=6001,
        host="0.0.0.0",
        sending_app="TEST_APP",
        sending_facility="TEST_FAC",
        endpoint_id=endpoint.id
    )
    session.add(mllp_config)
    
    session.commit()
    session.refresh(source_ej)
    
    yield {
        "context": context,
        "ej": source_ej,
        "eg": eg,
        "pole": pole,
        "service": service,
        "uf": uf,
        "uh": uh,
        "chambre": chambre,
        "lit": lit,
        "config": config,
        "endpoint": endpoint,
        "mllp_config": mllp_config,
        "namespaces_count": 5  # 2 EJ + 1 EG + 1 Pole + 1 UF
    }
    
    # Cleanup après test
    # (Suppression en cascade inversée)
    session.exec(delete(MLLPConfig).where(MLLPConfig.endpoint_id == endpoint.id))
    session.exec(delete(SystemEndpoint).where(SystemEndpoint.id == endpoint.id))
    session.exec(delete(Lit).where(Lit.chambre_id == chambre.id))
    session.exec(delete(Chambre).where(Chambre.unite_hebergement_id == uh.id))
    session.exec(delete(UniteHebergement).where(UniteHebergement.unite_fonctionnelle_id == uf.id))
    session.exec(delete(IdentifierNamespace).where(IdentifierNamespace.unite_fonctionnelle_id == uf.id))
    session.exec(delete(UniteFonctionnelle).where(UniteFonctionnelle.service_id == service.id))
    session.exec(delete(Service).where(Service.pole_id == pole.id))
    session.exec(delete(IdentifierNamespace).where(IdentifierNamespace.pole_id == pole.id))
    session.exec(delete(Pole).where(Pole.entite_geo_id == eg.id))
    session.exec(delete(IdentifierNamespace).where(IdentifierNamespace.entite_geographique_id == eg.id))
    session.exec(delete(EntiteGeographique).where(EntiteGeographique.entite_juridique_id == source_ej.id))
    session.exec(delete(ScenarioEJConfig).where(ScenarioEJConfig.entite_juridique_id == source_ej.id))
    session.exec(delete(IdentifierNamespace).where(IdentifierNamespace.entite_juridique_id == source_ej.id))
    session.delete(source_ej)
    session.commit()


def test_clone_ej_basic(client, session, test_ej_with_structure):
    """Test basique de clonage d'une EJ."""
    source = test_ej_with_structure
    context_id = source["context"].id
    ej_id = source["ej"].id
    
    # Effectuer le clonage
    response = client.post(
        f"/admin/ght/{context_id}/ej/{ej_id}/clone",
        data={
            "new_name": "EJ Clonée Test",
            "new_finess_ej": "CLONE9999"
        },
        follow_redirects=False
    )
    
    # Vérifier la redirection (303 See Other)
    assert response.status_code == 303
    
    # Vérifier que l'EJ clonée existe
    cloned_ej = session.exec(
        select(EntiteJuridique).where(EntiteJuridique.finess_ej == "CLONE9999")
    ).first()
    
    assert cloned_ej is not None, "L'EJ clonée n'a pas été créée"
    assert cloned_ej.name == "EJ Clonée Test"
    assert cloned_ej.id != ej_id
    
    # Nettoyer l'EJ clonée
    _cleanup_cloned_ej(session, cloned_ej.id)


def test_clone_ej_structure(client, session, test_ej_with_structure):
    """Test que la structure complète est clonée."""
    source = test_ej_with_structure
    context_id = source["context"].id
    ej_id = source["ej"].id
    
    # Effectuer le clonage
    client.post(
        f"/admin/ght/{context_id}/ej/{ej_id}/clone",
        data={
            "new_name": "EJ Structure Test",
            "new_finess_ej": "STRUCT999"
        }
    )
    
    cloned_ej = session.exec(
        select(EntiteJuridique).where(EntiteJuridique.finess_ej == "STRUCT999")
    ).first()
    
    assert cloned_ej is not None
    
    # Vérifier l'EG
    cloned_egs = session.exec(
        select(EntiteGeographique).where(EntiteGeographique.entite_juridique_id == cloned_ej.id)
    ).all()
    assert len(cloned_egs) == 1, "L'EG n'a pas été clonée"
    
    # Vérifier le Pole
    cloned_poles = session.exec(
        select(Pole).where(Pole.entite_geo_id == cloned_egs[0].id)
    ).all()
    assert len(cloned_poles) == 1, "Le Pole n'a pas été cloné"
    
    # Vérifier le Service
    cloned_services = session.exec(
        select(Service).where(Service.pole_id == cloned_poles[0].id)
    ).all()
    assert len(cloned_services) == 1, "Le Service n'a pas été cloné"
    
    # Vérifier l'UF
    cloned_ufs = session.exec(
        select(UniteFonctionnelle).where(UniteFonctionnelle.service_id == cloned_services[0].id)
    ).all()
    assert len(cloned_ufs) == 1, "L'UF n'a pas été clonée"
    
    # Vérifier l'UH
    cloned_uhs = session.exec(
        select(UniteHebergement).where(UniteHebergement.unite_fonctionnelle_id == cloned_ufs[0].id)
    ).all()
    assert len(cloned_uhs) == 1, "L'UH n'a pas été clonée"
    
    # Vérifier la Chambre
    cloned_chambres = session.exec(
        select(Chambre).where(Chambre.unite_hebergement_id == cloned_uhs[0].id)
    ).all()
    assert len(cloned_chambres) == 1, "La Chambre n'a pas été clonée"
    
    # Vérifier le Lit
    cloned_lits = session.exec(
        select(Lit).where(Lit.chambre_id == cloned_chambres[0].id)
    ).all()
    assert len(cloned_lits) == 1, "Le Lit n'a pas été cloné"
    
    # Nettoyer
    _cleanup_cloned_ej(session, cloned_ej.id)


def test_clone_ej_namespaces(client, session, test_ej_with_structure):
    """Test que les namespaces sont clonés à tous les niveaux."""
    source = test_ej_with_structure
    context_id = source["context"].id
    ej_id = source["ej"].id
    
    # Effectuer le clonage
    client.post(
        f"/admin/ght/{context_id}/ej/{ej_id}/clone",
        data={
            "new_name": "EJ Namespaces Test",
            "new_finess_ej": "NSPACE99"
        }
    )
    
    cloned_ej = session.exec(
        select(EntiteJuridique).where(EntiteJuridique.finess_ej == "NSPACE99")
    ).first()
    
    assert cloned_ej is not None
    
    # Compter les namespaces clonés
    cloned_ej_ns = session.exec(
        select(IdentifierNamespace).where(IdentifierNamespace.entite_juridique_id == cloned_ej.id)
    ).all()
    assert len(cloned_ej_ns) == 2, f"Attendu 2 namespaces EJ, obtenu {len(cloned_ej_ns)}"
    
    # Vérifier namespaces EG
    cloned_egs = session.exec(
        select(EntiteGeographique).where(EntiteGeographique.entite_juridique_id == cloned_ej.id)
    ).all()
    for eg in cloned_egs:
        eg_ns = session.exec(
            select(IdentifierNamespace).where(IdentifierNamespace.entite_geographique_id == eg.id)
        ).all()
        assert len(eg_ns) == 1, "Namespace EG non cloné"
    
    # Nettoyer
    _cleanup_cloned_ej(session, cloned_ej.id)


def test_clone_ej_scenario_config(client, session, test_ej_with_structure):
    """Test que le ScenarioEJConfig est cloné."""
    source = test_ej_with_structure
    context_id = source["context"].id
    ej_id = source["ej"].id
    
    # Effectuer le clonage
    client.post(
        f"/admin/ght/{context_id}/ej/{ej_id}/clone",
        data={
            "new_name": "EJ Config Test",
            "new_finess_ej": "CONFIG99"
        }
    )
    
    cloned_ej = session.exec(
        select(EntiteJuridique).where(EntiteJuridique.finess_ej == "CONFIG99")
    ).first()
    
    assert cloned_ej is not None
    
    # Vérifier que le ScenarioEJConfig a été cloné
    cloned_config = session.exec(
        select(ScenarioEJConfig).where(ScenarioEJConfig.entite_juridique_id == cloned_ej.id)
    ).first()
    
    assert cloned_config is not None, "ScenarioEJConfig non cloné"
    assert cloned_config.medecin_hospitalisation_rpps == "10100000001"
    assert cloned_config.medecin_hospitalisation_nom == "Dr TEST Pierre"
    # Les UF foreign keys doivent être nulles car les nouvelles UF n'existent pas encore
    assert cloned_config.uf_hospitalisation_id is None, "uf_hospitalisation_id devrait être None"
    
    # Nettoyer
    _cleanup_cloned_ej(session, cloned_ej.id)


def test_clone_ej_duplicate_finess_rejected(client, session, test_ej_with_structure):
    """Test que le clonage avec un FINESS existant est rejeté."""
    source = test_ej_with_structure
    context_id = source["context"].id
    ej_id = source["ej"].id
    existing_finess = source["ej"].finess_ej
    
    # Essayer de cloner avec le même FINESS
    response = client.post(
        f"/admin/ght/{context_id}/ej/{ej_id}/clone",
        data={
            "new_name": "EJ Duplicate",
            "new_finess_ej": existing_finess
        },
        follow_redirects=False
    )
    
    # Devrait rediriger avec un message d'erreur
    assert response.status_code == 303
    
    # Vérifier qu'aucune EJ avec ce nom n'a été créée en double
    ejes_with_name = session.exec(
        select(EntiteJuridique).where(EntiteJuridique.name == "EJ Duplicate")
    ).all()
    assert len(ejes_with_name) == 0, "Une EJ avec FINESS dupliqué a été créée"


def _cleanup_cloned_ej(session: Session, ej_id: int):
    """Nettoie une EJ clonée et toute sa structure."""
    # Récupérer les IDs en cascade
    egs = session.exec(select(EntiteGeographique).where(EntiteGeographique.entite_juridique_id == ej_id)).all()
    
    for eg in egs:
        poles = session.exec(select(Pole).where(Pole.entite_geo_id == eg.id)).all()
        for pole in poles:
            services = session.exec(select(Service).where(Service.pole_id == pole.id)).all()
            for svc in services:
                ufs = session.exec(select(UniteFonctionnelle).where(UniteFonctionnelle.service_id == svc.id)).all()
                for uf in ufs:
                    uhs = session.exec(select(UniteHebergement).where(UniteHebergement.unite_fonctionnelle_id == uf.id)).all()
                    for uh in uhs:
                        chambres = session.exec(select(Chambre).where(Chambre.unite_hebergement_id == uh.id)).all()
                        for chambre in chambres:
                            session.exec(delete(Lit).where(Lit.chambre_id == chambre.id))
                            session.exec(delete(IdentifierNamespace).where(IdentifierNamespace.chambre_id == chambre.id))
                        session.exec(delete(Chambre).where(Chambre.unite_hebergement_id == uh.id))
                        session.exec(delete(IdentifierNamespace).where(IdentifierNamespace.unite_hebergement_id == uh.id))
                    session.exec(delete(UniteHebergement).where(UniteHebergement.unite_fonctionnelle_id == uf.id))
                    session.exec(delete(IdentifierNamespace).where(IdentifierNamespace.unite_fonctionnelle_id == uf.id))
                session.exec(delete(UniteFonctionnelle).where(UniteFonctionnelle.service_id == svc.id))
                session.exec(delete(IdentifierNamespace).where(IdentifierNamespace.service_id == svc.id))
            session.exec(delete(Service).where(Service.pole_id == pole.id))
            session.exec(delete(IdentifierNamespace).where(IdentifierNamespace.pole_id == pole.id))
        session.exec(delete(Pole).where(Pole.entite_geo_id == eg.id))
        session.exec(delete(IdentifierNamespace).where(IdentifierNamespace.entite_geographique_id == eg.id))
    
    session.exec(delete(EntiteGeographique).where(EntiteGeographique.entite_juridique_id == ej_id))
    session.exec(delete(ScenarioEJConfig).where(ScenarioEJConfig.entite_juridique_id == ej_id))
    session.exec(delete(IdentifierNamespace).where(IdentifierNamespace.entite_juridique_id == ej_id))
    
    # Supprimer les endpoints et leurs configurations
    endpoints = session.exec(select(SystemEndpoint).where(SystemEndpoint.entite_juridique_id == ej_id)).all()
    for ep in endpoints:
        session.exec(delete(MLLPConfig).where(MLLPConfig.endpoint_id == ep.id))
        session.exec(delete(FHIRConfig).where(FHIRConfig.endpoint_id == ep.id))
    session.exec(delete(SystemEndpoint).where(SystemEndpoint.entite_juridique_id == ej_id))
    
    ej = session.get(EntiteJuridique, ej_id)
    if ej:
        session.delete(ej)
    session.commit()


def test_clone_ej_endpoints(client, session, test_ej_with_structure):
    """Test que les endpoints et leurs configurations sont clonés."""
    source = test_ej_with_structure
    context_id = source["context"].id
    ej_id = source["ej"].id
    
    # Effectuer le clonage
    client.post(
        f"/admin/ght/{context_id}/ej/{ej_id}/clone",
        data={
            "new_name": "EJ Endpoints Test",
            "new_finess_ej": "ENDPT999"
        }
    )
    
    cloned_ej = session.exec(
        select(EntiteJuridique).where(EntiteJuridique.finess_ej == "ENDPT999")
    ).first()
    
    assert cloned_ej is not None
    
    # Vérifier que l'endpoint a été cloné
    cloned_endpoints = session.exec(
        select(SystemEndpoint).where(SystemEndpoint.entite_juridique_id == cloned_ej.id)
    ).all()
    
    assert len(cloned_endpoints) == 1, "L'endpoint n'a pas été cloné"
    cloned_endpoint = cloned_endpoints[0]
    
    # Vérifier les propriétés de l'endpoint cloné
    assert "(Clone)" in cloned_endpoint.name, "Le nom de l'endpoint cloné devrait contenir '(Clone)'"
    assert cloned_endpoint.kind == "mllp"
    assert cloned_endpoint.role == "receiver"
    
    # Vérifier que la config MLLP a été clonée
    cloned_mllp_configs = session.exec(
        select(MLLPConfig).where(MLLPConfig.endpoint_id == cloned_endpoint.id)
    ).all()
    
    assert len(cloned_mllp_configs) == 1, "La config MLLP n'a pas été clonée"
    cloned_mllp = cloned_mllp_configs[0]
    
    assert "(Clone)" in cloned_mllp.name, "Le nom de la config MLLP clonée devrait contenir '(Clone)'"
    # Le port devrait être décalé de 1000 pour éviter les conflits
    assert cloned_mllp.port == 7001, f"Le port devrait être 7001 (6001 + 1000), obtenu {cloned_mllp.port}"
    assert cloned_mllp.sending_app == "TEST_APP"
    assert cloned_mllp.sending_facility == "TEST_FAC"
    
    # Nettoyer
    _cleanup_cloned_ej(session, cloned_ej.id)