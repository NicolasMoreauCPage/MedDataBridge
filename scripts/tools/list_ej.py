from sqlmodel import Session, select
from app.db import engine
from app.models_structure import EntiteJuridique


def main() -> None:
    with Session(engine) as session:
        print("ID | FINESS_EJ | NAME | GHT_CONTEXT_ID")
        for ej in session.exec(select(EntiteJuridique)).all():
            print(f"{ej.id} | {ej.finess_ej} | {ej.name} | {ej.ght_context_id}")


if __name__ == "__main__":
    main()
