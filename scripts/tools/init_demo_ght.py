"""Script pour initialiser le GHT de démo avec ses espaces de noms."""
import argparse
import sys
from pathlib import Path
from sqlalchemy import text

# Ajouter le répertoire parent au path pour pouvoir importer app
parent_dir = str(Path(__file__).resolve().parent.parent)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from sqlmodel import Session, select, SQLModel
from app.db import engine, migrate_database
from app.models_structure import GHTContext, IdentifierNamespace

def init_demo_ght(reset: bool = False):
    """Initialise les données de démo, sans effacer la base par défaut."""
    if reset:
        SQLModel.metadata.drop_all(engine)
        with engine.begin() as connection:
            connection.execute(text("DROP TABLE IF EXISTS alembic_version"))
    migrate_database(str(engine.url))
    
    with Session(engine) as session:
        # Vérifier si le GHT existe déjà
        ght = session.exec(select(GHTContext).where(GHTContext.name == "GHT Démo Interop")).first()
        if not ght:
            print("Création du GHT Démo Interop...")
            ght = GHTContext(
                name="GHT Démo Interop",
                description="GHT de démonstration pour tests d'interopérabilité",
                oid_racine="1.2.250.1.xxx.1.1",  # À remplacer par un vrai OID
                fhir_server_url="http://localhost:8000/fhir"
            )
            session.add(ght)
            session.commit()
            session.refresh(ght)
        else:
            print("Le GHT Démo Interop existe déjà")

        # Créer/vérifier les espaces de nom
        namespaces = [
            {
                "name": "CPAGE",
                "description": "Identifiants CPAGE",
                "oid": "1.2.250.1.211.10.200.2",
                "uri": "http://cpage.fr/identifiers"
            },
            {
                "name": "IPP",
                "description": "Identifiant Patient Permanent",
                "oid": "1.2.250.1.71.1.2.1",
                "uri": "http://interop.demo/ns/ipp"
            },
            {
                "name": "NDA",
                "description": "Numéro de Dossier Administratif",
                "oid": "1.2.250.1.71.1.2.2", 
                "uri": "http://interop.demo/ns/nda"
            },
            {
                "name": "VENUE",
                "description": "Identifiant de venue",
                "oid": "1.2.250.1.71.1.2.3",
                "uri": "http://interop.demo/ns/venue"
            }
        ]

        for ns_data in namespaces:
            ns = session.exec(
                select(IdentifierNamespace).where(
                    IdentifierNamespace.name == ns_data["name"],
                    IdentifierNamespace.ght_context_id == ght.id
                )
            ).first()
            
            if not ns:
                print(f"Création de l'espace de nom {ns_data['name']}...")
                ns = IdentifierNamespace(
                    name=ns_data["name"],
                    description=ns_data["description"],
                    oid=ns_data["oid"],
                    system=ns_data["uri"],
                    type=ns_data["name"],  # Utilise le nom comme type par simplicité
                    ght_context_id=ght.id
                )
                session.add(ns)

        session.commit()
        print("Configuration terminée")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reset", action="store_true", help="Supprime les données avant l'initialisation")
    init_demo_ght(reset=parser.parse_args().reset)
