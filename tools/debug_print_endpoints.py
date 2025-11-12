from sqlmodel import Session, select
from app.db import engine
from app.models_shared import SystemEndpoint
from app.models_structure_fhir import EntiteJuridique

def print_endpoints():
    with Session(engine) as session:
        eps = session.exec(select(SystemEndpoint)).all()
        for e in eps:
            ej_name = None
            if e.entite_juridique_id:
                ej = session.get(EntiteJuridique, e.entite_juridique_id)
                ej_name = ej.short_name if ej else None
            print(f"ID={e.id} | Name={e.name} | Kind={e.kind} | Role={e.role} | GHT={e.ght_context_id} | EJ={e.entite_juridique_id} | EJ_NAME={ej_name}")

if __name__ == "__main__":
    print_endpoints()
