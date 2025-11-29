from datetime import datetime, timedelta
from sqlmodel import SQLModel, Session, create_engine

from app.models import Patient, Dossier, Venue, Mouvement
from app.models_scenarios import InteropScenario
from app.services.scenario_capture import capture_dossier_as_scenario

def setup_db():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    return engine

def test_capture_creates_steps_from_movements():
    engine = setup_db()
    with Session(engine) as session:
        patient = Patient(family="Doe")
        session.add(patient); session.commit(); session.refresh(patient)
        dossier = Dossier(patient_id=patient.id, dossier_seq=1, admit_time=datetime.utcnow())
        session.add(dossier); session.commit(); session.refresh(dossier)
        venue = Venue(dossier_id=dossier.id, venue_seq=1, start_time=dossier.admit_time)
        session.add(venue); session.commit(); session.refresh(venue)
        base = dossier.admit_time
        m1 = Mouvement(venue_id=venue.id, mouvement_seq=1, when=base, trigger_event="A01")
        m2 = Mouvement(venue_id=venue.id, mouvement_seq=2, when=base + timedelta(minutes=30), trigger_event="A02")
        session.add(m1); session.add(m2); session.commit()
        scenario = capture_dossier_as_scenario(session, dossier)
        session.refresh(scenario)
        steps = scenario.steps
        assert len(steps) == 2
        # Vérifie délais approx (1800 sec ~ 30 min)
        assert steps[1].delay_seconds in (1800, 1799, 1801)
        assert "ADT^A01" in steps[0].message_type
        assert "ADT^A02" in steps[1].message_type
