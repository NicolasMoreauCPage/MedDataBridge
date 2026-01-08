"""Simple benchmark for ZBE generation + parsing + validation.
Run inside virtualenv: python program_docs/benchmark_zbe_performance.py
"""
from time import perf_counter
from sqlmodel import Session
from app.db import engine, init_db
from app.models import Patient, Dossier, Venue, Mouvement, DossierType
from app.services.hl7_generator import generate_admission_message

N = 1000

def setup_entities(session: Session):
    patient = Patient(family="Bench", given="Perf", birth_date="1980-01-01", gender="male")
    session.add(patient); session.commit(); session.refresh(patient)
    dossier = Dossier(dossier_seq=777001, patient_id=patient.id, uf_responsabilite="UF-BENCH", admit_time=__import__("datetime").datetime.utcnow(), dossier_type=DossierType.HOSPITALISE)
    session.add(dossier); session.commit(); session.refresh(dossier)
    venue = Venue(venue_seq=777001, dossier_id=dossier.id, uf_responsabilite="UF-BENCH", start_time=__import__("datetime").datetime.utcnow(), code="LOC-BENCH", label="Bench Loc")
    session.add(venue); session.commit(); session.refresh(venue)
    return patient, dossier, venue

def main():
    init_db()
    with Session(engine) as session:
        patient, dossier, venue = setup_entities(session)
        mouvements = []
        for i in range(N):
            m = Mouvement(mouvement_seq=880000 + i, venue_id=venue.id, when=__import__("datetime").datetime.utcnow(), location=f"LOC-{i%10}", trigger_event="A01", action="INSERT")
            session.add(m); mouvements.append(m)
        session.commit()
        t0 = perf_counter()
        messages = [generate_admission_message(patient, dossier, venue, m, session=session) for m in mouvements]
        t1 = perf_counter()
        gen_time = t1 - t0
        size = sum(len(msg) for msg in messages)
        print(f"Generated {N} messages in {gen_time:.4f}s ({gen_time*1000/N:.2f} ms/message). Total size: {size/1024:.1f} KiB")
        # Placeholder: parsing/validation timing could be added when parser entrypoint available.

if __name__ == "__main__":
    main()
