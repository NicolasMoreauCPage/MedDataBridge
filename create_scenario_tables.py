"""Script pour créer les tables de scénarios dans la base de données."""
from sqlmodel import SQLModel, create_engine

# Import de TOUS les modèles pour que SQLModel connaisse toutes les relations
from app import models, models_structure, models_scenarios, models_identifiers, models_practitioners, models_endpoints

def create_scenario_tables():
    """Crée toutes les tables manquantes (y compris scénarios)."""
    
    # Créer le moteur - utiliser directement le chemin de la base
    engine = create_engine("sqlite:///app.db", echo=False)  # echo=False pour moins de verbosité
    
    # Créer TOUTES les tables (create_all est idempotent, ne recrée pas les existantes)
    print("Création de toutes les tables manquantes...")
    SQLModel.metadata.create_all(engine)
    
    print("✅ Tables créées avec succès!")

if __name__ == "__main__":
    create_scenario_tables()
