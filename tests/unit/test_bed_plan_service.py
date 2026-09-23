from datetime import datetime, timezone

from sqlalchemy import event

from app.db import engine
from app.models import Dossier, Patient, Venue
from app.models_structure import (
    Chambre,
    Lit,
    Pole,
    Service,
    UniteFonctionnelle,
    UniteHebergement,
)
from app.services.bed_plan import build_bed_plan


def test_bed_plan_route_renders_the_service_projection(client):
    response = client.get("/mouvements/plan-lits")

    assert response.status_code == 200
    assert "Plan de lits" in response.text
    assert "js/plan-lits-workspace.js" in response.text


def test_bed_plan_batches_occupants_and_movement_history(session):
    pole = Pole(identifier="POLE-PLAN-1", name="Pôle plan")
    session.add(pole)
    session.flush()
    service = Service(identifier="SVC-PLAN-1", name="Service plan", pole_id=pole.id)
    session.add(service)
    session.flush()
    uf = UniteFonctionnelle(identifier="UF-PLAN-1", name="UF plan", service_id=service.id)
    session.add(uf)
    session.flush()
    uh = UniteHebergement(
        identifier="UH-PLAN-1",
        name="UH plan",
        unite_fonctionnelle_id=uf.id,
    )
    session.add(uh)
    session.flush()
    room = Chambre(identifier="CH-PLAN-1", name="Chambre plan", unite_hebergement_id=uh.id)
    session.add(room)
    session.flush()
    bed = Lit(
        identifier="LIT-PLAN-1",
        name="Lit plan",
        chambre_id=room.id,
        operational_status="available",
    )
    patient = Patient(identifier="IPP-PLAN-1", family="MARTIN", given="Alice")
    session.add_all([bed, patient])
    session.flush()
    dossier = Dossier(
        dossier_seq=801,
        patient_id=patient.id,
        admit_time=datetime.now(timezone.utc),
    )
    session.add(dossier)
    session.flush()
    session.add(
        Venue(
            venue_seq=801,
            dossier_id=dossier.id,
            start_time=datetime.now(timezone.utc),
            lit_id=bed.id,
            chambre_id=room.id,
        )
    )
    session.commit()

    selects = 0

    def count_selects(_conn, _cursor, statement, _parameters, _context, _many):
        nonlocal selects
        if statement.lstrip().lower().startswith("select"):
            selects += 1

    event.listen(engine, "before_cursor_execute", count_selects)
    try:
        plan = build_bed_plan(session)
    finally:
        event.remove(engine, "before_cursor_execute", count_selects)

    bed_row = plan["structure"][service.id]["ufs"][uf.id]["uhs"][uh.id][
        "chambres"
    ][room.id]["lits"][0]
    assert bed_row["status"] == "occupied"
    assert bed_row["occupant"]["patient_name"] == "MARTIN Alice"
    assert plan["stats"] == {
        "total": 1,
        "libres": 0,
        "occupes": 1,
        "taux_occupation": 100.0,
    }
    assert selects <= 5


def test_bed_plan_status_filter_keeps_only_matching_beds(session):
    pole = Pole(identifier="POLE-PLAN-2", name="Pôle filtre")
    session.add(pole)
    session.flush()
    service = Service(identifier="SVC-PLAN-2", name="Service filtre", pole_id=pole.id)
    session.add(service)
    session.flush()
    uf = UniteFonctionnelle(identifier="UF-PLAN-2", name="UF filtre", service_id=service.id)
    session.add(uf)
    session.flush()
    uh = UniteHebergement(
        identifier="UH-PLAN-2",
        name="UH filtre",
        unite_fonctionnelle_id=uf.id,
    )
    session.add(uh)
    session.flush()
    room = Chambre(identifier="CH-PLAN-2", name="Chambre filtre", unite_hebergement_id=uh.id)
    session.add(room)
    session.flush()
    session.add_all(
        [
            Lit(
                identifier="LIT-PLAN-FREE",
                name="Lit libre",
                chambre_id=room.id,
                operational_status="available",
            ),
            Lit(
                identifier="LIT-PLAN-CLOSED",
                name="Lit fermé",
                chambre_id=room.id,
                operational_status="maintenance",
            ),
        ]
    )
    session.commit()

    plan = build_bed_plan(session, status_filter="free")

    beds = plan["structure"][service.id]["ufs"][uf.id]["uhs"][uh.id]["chambres"][room.id]["lits"]
    assert [bed["name"] for bed in beds] == ["Lit libre"]
    assert plan["stats"]["total"] == 1
