"""Regression tests for bounded timeline data loading."""

from datetime import datetime, timedelta

from sqlalchemy import event

from app.models import Dossier, Mouvement, Patient, Venue
from app.routers.timeline import _build_patient_events, _load_patient_timeline_graph


def test_patient_timeline_loads_a_full_graph_in_four_queries(session):
    """A patient timeline must not add one query per dossier or venue."""
    patient = Patient(family="Timeline", given="Patient")
    session.add(patient)
    session.commit()
    session.refresh(patient)

    now = datetime.now()
    dossiers = []
    for index in range(2):
        dossier = Dossier(
            dossier_seq=9_000 + index,
            patient_id=patient.id,
            admit_time=now + timedelta(minutes=index),
        )
        session.add(dossier)
        dossiers.append(dossier)
    session.commit()

    venues = []
    for index, dossier in enumerate(dossiers):
        session.refresh(dossier)
        for venue_index in range(2):
            venue = Venue(
                venue_seq=9_100 + (index * 10) + venue_index,
                dossier_id=dossier.id,
                start_time=now + timedelta(minutes=index + venue_index),
            )
            session.add(venue)
            venues.append(venue)
    session.commit()

    for index, venue in enumerate(venues):
        session.refresh(venue)
        session.add(
            Mouvement(
                mouvement_seq=9_200 + index,
                venue_id=venue.id,
                when=now + timedelta(minutes=index),
                trigger_event="A01",
            )
        )
    session.commit()
    session.expire_all()

    statements = []

    def record_statement(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(session.bind, "before_cursor_execute", record_statement)
    try:
        loaded_patient, graph = _load_patient_timeline_graph(session, patient.id)
        events = _build_patient_events(loaded_patient, graph)
    finally:
        event.remove(session.bind, "before_cursor_execute", record_statement)

    assert loaded_patient is not None
    assert len(graph.dossiers) == 2
    assert len(graph.venues) == 4
    assert len(graph.mouvements) == 4
    assert len(events) == 10  # 2 admissions + 4 venues + 4 mouvements
    assert len(statements) <= 4
