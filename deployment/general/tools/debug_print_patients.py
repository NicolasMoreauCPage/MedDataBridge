from app.db import engine
from sqlmodel import Session, select
from app.models import Patient

def print_patients():
    with Session(engine) as session:
        patients = session.exec(select(Patient)).all()
        for p in patients:
            print(f"ID={p.id} | external_id={p.external_id} | Nom={p.family} | EJ={p.entite_juridique_id} | GHT={p.ght_context_id}")

if __name__ == "__main__":
    print_patients()
