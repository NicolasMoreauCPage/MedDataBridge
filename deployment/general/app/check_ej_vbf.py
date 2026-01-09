from sqlmodel import Session, select
from .db import engine
from .models_structure import EntiteJuridique

IDENTIFIANT_VBF = "VBF"

with Session(engine) as session:
    ej = session.exec(select(EntiteJuridique).where(EntiteJuridique.identifier == IDENTIFIANT_VBF)).first()
    if ej:
        print(f"EJ trouvée : id={ej.id}, identifier={ej.identifier}, name={ej.name}")
    else:
        print("Aucune entité juridique VBF trouvée dans la base.")
from sqlmodel import Session, select
from .db import engine
from .models_structure import EntiteJuridique

IDENTIFIANT_VBF = "VBF"

def main():
    with Session(engine) as session:
        ej = session.exec(select(EntiteJuridique).where(EntiteJuridique.identifier == IDENTIFIANT_VBF)).first()
        if ej:
            print(f"EJ trouvée : id={ej.id}, identifier={ej.identifier}, name={ej.name}")
        else:
            print("Aucune entité juridique VBF trouvée dans la base.")

if __name__ == "__main__":
    main()
