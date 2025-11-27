import sys, os
sys.path.insert(0, os.getcwd())
from sqlmodel import Session, select
from app.models_endpoints import SystemEndpoint
from app.models import Patient
from app.db import session_factory
from app.services.emit_on_create import emit_to_senders

session = session_factory()
with session as session:
    ep = session.exec(select(SystemEndpoint).where(SystemEndpoint.role.in_(["sender","both"])).where(SystemEndpoint.is_enabled==True)).first()
    if not ep:
        print('NO_ENDPOINT')
        raise SystemExit(0)
    print('Found endpoint', ep.id, ep.kind, ep.entite_juridique_id, ep.ght_context_id)
    patient = None
    if ep.entite_juridique_id:
        patient = session.exec(select(Patient).where(Patient.entite_juridique_id==ep.entite_juridique_id)).first()
    if not patient and ep.ght_context_id:
        patient = session.exec(select(Patient).where(Patient.ght_context_id==ep.ght_context_id)).first()
    if not patient:
        print('NO_PATIENT_FOR_ENDPOINT')
        raise SystemExit(0)
    print('Using patient', patient.id)
    emit_to_senders(patient, 'patient', session, operation='insert')
    print('emit_to_senders invoked')
