"""
Script de démonstration pour utiliser le seed des scénarios

Ce script montre comment initialiser une nouvelle base de données
avec tous les scénarios de test HL7/HPRIM.
"""

from app.db import engine
from seed_scenarios_from_db import seed_scenarios_from_db, verify_seed_integrity
from sqlmodel import Session, text

def reset_database_for_demo():
    """Remet la base de données à zéro pour la démonstration (ATTENTION: destructive!)"""

    print("⚠️ ATTENTION: Cette fonction va supprimer TOUS les scénarios existants!")
    confirm = input("Tapez 'OUI' pour confirmer la suppression: ")

    if confirm != 'OUI':
        print("❌ Opération annulée")
        return False

    with Session(engine) as session:
        try:
            # Supprimer toutes les étapes d'abord (contrainte de clé étrangère)
            session.exec(text("DELETE FROM interopscenariostep"))
            # Supprimer tous les scénarios
            session.exec(text("DELETE FROM interopscenario"))
            session.commit()
            print("🗑️ Base de données remise à zéro")
            return True
        except Exception as e:
            print(f"❌ Erreur lors de la remise à zéro: {e}")
            session.rollback()
            return False

def demo_seed_usage():
    """Démontre l'utilisation du script de seed"""

    print("🚀 Démonstration du script de seed des scénarios")
    print("=" * 60)

    # Vérifier l'état initial
    print("\n📊 État initial de la base de données:")
    verify_seed_integrity()

    # Demander confirmation pour la remise à zéro
    if not reset_database_for_demo():
        return

    # Vérifier que la base est vide
    print("\n📊 État après remise à zéro:")
    verify_seed_integrity()

    # Lancer le seed
    print("\n🌱 Lancement du seed...")
    seed_scenarios_from_db()

    # Vérification finale
    print("\n📊 État final après seed:")
    verify_seed_integrity()

    print("\n✅ Démonstration terminée!")
    print("\n💡 Pour utiliser ce seed en production:")
    print("   1. Copiez scenarios_seed_data.json et seed_scenarios_from_db.py")
    print("   2. Exécutez: python seed_scenarios_from_db.py")
    print("   3. Le script détectera automatiquement les doublons")

if __name__ == "__main__":
    demo_seed_usage()