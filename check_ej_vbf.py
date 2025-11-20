
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from sqlmodel import Session, select
from app.db import engine
from app.models_structure import EntiteGeographique

IDENTIFIANT_VBF = "69"  # Code de l'EJ dans le fichier HL7 (CD^Code^L|^69)

with Session(engine) as session:
    ej = session.exec(select(EntiteGeographique).where(EntiteGeographique.identifier == IDENTIFIANT_VBF)).first()
    if ej:
        print(f"EJ trouvée : id={ej.id}, identifier={ej.identifier}, name={ej.name}")
    else:
        print("Aucune entité juridique PR205VA1 (code 69) trouvée dans la base.")
