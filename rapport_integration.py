#!/usr/bin/env python3
"""Génère un rapport d'intégration pour Test GHT et EJ 5."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlmodel import Session, select, func
from app.db import engine
from app.models_structure import *
from app.models_shared import SystemEndpoint
from datetime import datetime

def main():
    with Session(engine) as s:
        print("=" * 80)
        print("RAPPORT D'INTÉGRATION - MedData Bridge")
        print("=" * 80)
        print(f"Date: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
        print()
        
        # === PARTIE 1: Test GHT (Import MFN) ===
        ght = s.exec(select(GHTContext).where(GHTContext.name == 'Test GHT')).first()
        if ght:
            print("╔" + "═" * 78 + "╗")
            print("║" + " " * 25 + "IMPORT MFN - Test GHT" + " " * 32 + "║")
            print("╚" + "═" * 78 + "╝")
            print()
            print(f"📋 GHT: {ght.name} (id={ght.id})")
            print(f"   Description: {ght.description or '(aucune)'}")
            print()
            
            # Statistiques structures - récupération progressive des IDs pour éviter stack overflow
            # Étape 1: EJ du GHT
            ej_ids = list(s.exec(select(EntiteJuridique.id).where(EntiteJuridique.ght_context_id == ght.id)).all())
            ej_count = len(ej_ids)
            
            # Étape 2: EG des EJ
            eg_ids = list(s.exec(select(EntiteGeographique.id).where(EntiteGeographique.entite_juridique_id.in_(ej_ids))).all()) if ej_ids else []
            eg_count = len(eg_ids)
            
            # Étape 3: Poles des EG
            pole_ids = list(s.exec(select(Pole.id).where(Pole.entite_geo_id.in_(eg_ids))).all()) if eg_ids else []
            
            # Étape 4: Services des Poles
            srv_ids = list(s.exec(select(Service.id).where(Service.pole_id.in_(pole_ids))).all()) if pole_ids else []
            srv_count = len(srv_ids)
            
            # Étape 5: UF des Services
            uf_ids = list(s.exec(select(UniteFonctionnelle.id).where(UniteFonctionnelle.service_id.in_(srv_ids))).all()) if srv_ids else []
            uf_count = len(uf_ids)
            
            # Étape 6: UH des UF
            uh_ids = list(s.exec(select(UniteHebergement.id).where(UniteHebergement.unite_fonctionnelle_id.in_(uf_ids))).all()) if uf_ids else []
            uh_count = len(uh_ids)
            
            # Étape 7: Chambres des UH
            ch_ids = list(s.exec(select(Chambre.id).where(Chambre.unite_hebergement_id.in_(uh_ids))).all()) if uh_ids else []
            ch_count = len(ch_ids)
            
            # Étape 8: Lits des Chambres
            lit_count = s.exec(select(func.count(Lit.id)).where(Lit.chambre_id.in_(ch_ids))).one() if ch_ids else 0
            
            print("📊 STRUCTURE ORGANISATIONNELLE IMPORTÉE")
            print("   " + "─" * 50)
            print(f"   {'Entités Juridiques':<30} : {ej_count:>6}")
            print(f"   {'Entités Géographiques':<30} : {eg_count:>6}")
            print(f"   {'Services':<30} : {srv_count:>6}")
            print(f"   {'Unités Fonctionnelles':<30} : {uf_count:>6}")
            uh_label = "Unités d'Hébergement"
            print(f"   {uh_label:<30} : {uh_count:>6}")
            print(f"   {'Chambres':<30} : {ch_count:>6}")
            print(f"   {'Lits':<30} : {lit_count:>6}")
            print("   " + "─" * 50)
            total = ej_count + eg_count + srv_count + uf_count + uh_count + ch_count + lit_count
            print(f"   {'TOTAL ENTITÉS':<30} : {total:>6}")
            print()
            
            # Détail des EJ
            ejs = s.exec(select(EntiteJuridique).where(EntiteJuridique.ght_context_id == ght.id)).all()
            if ejs:
                print("📁 ENTITÉS JURIDIQUES DANS LE GHT")
                print("   " + "─" * 50)
                for ej in ejs:
                    print(f"   • {ej.name}")
                    print(f"     FINESS: {ej.finess_ej}, ID: {ej.id}")
                print()
        
        # === PARTIE 2: EJ 5 (Endpoint FILE) ===
        ej5 = s.get(EntiteJuridique, 5)
        if ej5:
            print("╔" + "═" * 78 + "╗")
            print("║" + " " * 20 + "ENDPOINT FILE - EJ 5 (GRGAP)" + " " * 28 + "║")
            print("╚" + "═" * 78 + "╝")
            print()
            print(f"🏥 ENTITÉ JURIDIQUE")
            print(f"   Nom: {ej5.name}")
            print(f"   ID: {ej5.id}")
            print(f"   FINESS: {ej5.finess_ej}")
            print(f"   Short Name: {ej5.short_name}")
            print()
            
            # Endpoint créé
            ep = s.exec(select(SystemEndpoint).where(SystemEndpoint.entite_juridique_id == 5).where(SystemEndpoint.kind == 'FILE')).first()
            if ep:
                print("📡 ENDPOINT FILE CONFIGURÉ")
                print("   " + "─" * 50)
                print(f"   ID: {ep.id}")
                print(f"   Nom: {ep.name}")
                print(f"   Type: {ep.kind}")
                print(f"   Rôle: {ep.role}")
                print(f"   Statut: {'✓ Actif' if ep.is_enabled else '✗ Inactif'}")
                print()
                print(f"   📂 CHEMINS")
                print(f"      Inbox:   {ep.inbox_path}")
                print(f"      Outbox:  {ep.outbox_path}")
                print(f"      Archive: {ep.archive_path}")
                print(f"      Erreurs: {ep.error_path}")
                print(f"      Filtres: {ep.file_extensions}")
                print()
                
                # Compter fichiers dans inbox
                inbox = Path(ep.inbox_path)
                if inbox.exists():
                    hl7_files = list(inbox.glob('*.hl7'))
                    print(f"   📨 MESSAGES DISPONIBLES")
                    print(f"      {len(hl7_files)} fichiers .hl7 dans le dossier inbox")
                    print()
                    
                    # Échantillon de fichiers
                    if hl7_files:
                        print(f"   📄 ÉCHANTILLON (5 premiers fichiers)")
                        for f in sorted(hl7_files)[:5]:
                            size_kb = f.stat().st_size / 1024
                            print(f"      • {f.name} ({size_kb:.1f} KB)")
                        if len(hl7_files) > 5:
                            print(f"      ... et {len(hl7_files) - 5} autres fichiers")
                        print()
                else:
                    print(f"   ⚠️  Dossier inbox introuvable: {ep.inbox_path}")
                    print()
            else:
                print("   ⚠️  Aucun endpoint FILE trouvé pour cette EJ")
                print()
        
        # === RÉSUMÉ ===
        print("=" * 80)
        print("RÉSUMÉ")
        print("=" * 80)
        print()
        print("✅ Import MFN réussi:")
        print(f"   • {total if ght else 0} entités de structure organisationnelle")
        print(f"   • Importées dans le GHT 'Test GHT'")
        print()
        print("✅ Endpoint FILE créé:")
        print(f"   • Associé à l'EJ 5 (GRGAP)")
        print(f"   • {len(hl7_files) if ep and inbox.exists() else '?'} messages IHE PAM disponibles")
        print()
        print("🔄 PROCHAINES ÉTAPES:")
        print("   1. Démarrer le service FilePollerService pour l'import automatique")
        print("   2. Ou utiliser l'API/UI pour déclencher un import manuel")
        print("   3. Les messages seront traités et archivés automatiquement")
        print()
        print("=" * 80)

if __name__ == "__main__":
    main()
