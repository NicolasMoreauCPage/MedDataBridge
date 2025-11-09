"""Tests basiques pour la seed multi-EJ étendue.

Objectifs:
- Vérifier la création des 4 entités juridiques du dataset EXTENDED_GHT_DATA
- Vérifier la présence des endpoints MLLP/FHIR (3 par EJ: RECV, SEND, FHIR)
- Vérifier qu'au moins 100 patients sont présents après seed (script cible 120)
- Vérifier qu'un mouvement d'admission (A01) existe pour la majorité des venues
"""
from sqlmodel import Session, select
from app.db import engine, init_db
from app.models_structure_fhir import EntiteJuridique
from app.models_shared import SystemEndpoint
from app.models import Patient, Mouvement, Venue
from app.services.structure_seed import EXTENDED_GHT_DATA, ensure_extended_demo_ght, ensure_endpoints_for_context, seed_demo_population


def test_extended_seed_basics():
    init_db()
    with Session(engine) as session:
        from app.models_structure_fhir import GHTContext
        existing_ctx = session.exec(select(GHTContext)).first()
        if not existing_ctx:
            existing_ctx = GHTContext(name="DEMO GHT", code="GHT-DEMO")
            session.add(existing_ctx)
            session.commit()
            session.refresh(existing_ctx)
        # Always ensure structure + endpoints (idempotent)
        ensure_extended_demo_ght(session, existing_ctx)
        ej_finess_seed = [ej["entite_juridique"]["finess_ej"] for ej in EXTENDED_GHT_DATA["juridical_entities"]]
        ensure_endpoints_for_context(session, existing_ctx, ej_finess_seed)
        seed_demo_population(session, existing_ctx, target_patients=120)
        # EJ count
        ej_finess = [ej["entite_juridique"]["finess_ej"] for ej in EXTENDED_GHT_DATA["juridical_entities"]]
        ej_rows = session.exec(select(EntiteJuridique).where(EntiteJuridique.finess_ej.in_(ej_finess))).all()
        assert len(ej_rows) == len(ej_finess), "Toutes les entités juridiques doivent exister"

        # Endpoints
        for finess in ej_finess:
            names = [f"MLLP RECV {finess}", f"MLLP SEND {finess}", f"FHIR API {finess}"]
            for n in names:
                ep = session.exec(select(SystemEndpoint).where(SystemEndpoint.name == n)).first()
                assert ep, f"Endpoint manquant: {n}"

        # Patients
        patient_count = len(session.exec(select(Patient.id)).all())
        assert patient_count >= 100, "Population patient insuffisante"

        # Mouvements A01
        total_venues = len(session.exec(select(Venue.id)).all())
        a01_count = len(session.exec(select(Mouvement.id).where(Mouvement.trigger_event == "A01")).all())
        assert a01_count >= int(total_venues * 0.7), "Trop peu de mouvements A01 (admissions)"
