from sqlmodel import Session, select
from app.db import engine
from app.models_structure_fhir import EntiteJuridique
from app.models import Patient

with Session(engine) as session:
    print("EJ IDs in DB:")
    for ej in session.exec(select(EntiteJuridique)).all():
        print(f"EJ id={ej.id} | FINESS={ej.finess_ej} | NAME={ej.name}")
    print("\nPatient distribution:")
    for ej in session.exec(select(EntiteJuridique)).all():
        patients = session.exec(select(Patient).where(Patient.entite_juridique_id == ej.id)).all()
        print(f"EJ id={ej.id} | patients={len(patients)}")
