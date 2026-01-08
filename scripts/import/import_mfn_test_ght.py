#!/usr/bin/env python3
"""Import de la structure MFN dans le GHT 'Test GHT'

Lit le fichier MFN depuis l'Archive et l'importe via l'importeur MFN.
"""
import sys
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db import session_factory
from app.services.mfn_importer import import_mfn
from app.models_structure import GHTContext
from app.models_practitioners import MedecinResponsable  # noqa: F401 - needed for SQLAlchemy relationship resolution
from sqlmodel import select

# Path to MFN structure file in Archive
MFN_FILE = Path("/home/nico/Travail/Fhir_MedBridgeData/Interfaces/Entrant/MFN/Archive/ExempleExtractionStructure.txt")


def main():
    print("=== Import MFN dans Test GHT ===\n")
    
    with session_factory() as session:
        # Récupérer ou créer le GHT "Test GHT"
        ght = session.exec(
            select(GHTContext).where(GHTContext.name == "Test GHT")
        ).first()
        
        if not ght:
            print("❌ GHT 'Test GHT' introuvable. Création...")
            ght = GHTContext(
                name="Test GHT",
                code="TEST_GHT",
                description="GHT de test pour import MFN",
                is_active=True
            )
            session.add(ght)
            session.commit()
            session.refresh(ght)
            print(f"✓ GHT créé: {ght.name} (id={ght.id})\n")
        else:
            print(f"✓ GHT trouvé: {ght.name} (id={ght.id})\n")
        
        # Importer chaque fichier MFN
        total_results = {
            "ej": 0, "eg": 0, "service": 0, "uf": 0, 
            "uh": 0, "chambre": 0, "lit": 0
        }
        
        if not MFN_FILE.exists():
            print(f"❌ Fichier MFN introuvable: {MFN_FILE}")
            return
        
        print(f"📂 Lecture du fichier MFN: {MFN_FILE.name}")
        print(f"   Taille: {MFN_FILE.stat().st_size / 1024 / 1024:.1f} MB")
        
        try:
            # Lire le contenu
            content = MFN_FILE.read_text(encoding="utf-8", errors="ignore")
            print(f"✅ Message MFN chargé: {len(content)} caractères\n")
            
            # Importer via le service MFN
            print("⏳ Import en cours...")
            result = import_mfn(content, session, ght)
            
            # Afficher le résumé
            print("\n" + "="*60)
            print("📊 RÉSULTATS DE L'IMPORT MFN")
            print("="*60)
            print(f"✅ Entités Juridiques (EJ):    {result.get('ej', 0)} créées")
            print(f"✅ Entités Géographiques (EG): {result.get('eg', 0)} créées")
            print(f"✅ Services:                   {result.get('service', 0)} créés")
            print(f"✅ Unités Fonctionnelles (UF): {result.get('uf', 0)} créées")
            print(f"✅ Unités d'Hébergement (UH):  {result.get('uh', 0)} créées")
            print(f"✅ Chambres:                   {result.get('chambre', 0)} créées")
            print(f"✅ Lits:                       {result.get('lit', 0)} créés")
            print("="*60)
            
            total = sum(result.values())
            print(f"\n🎉 TOTAL: {total} entités créées/mises à jour")
            
        except Exception as e:
            print(f"❌ Erreur lors de l'import: {str(e)}\n")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    main()
