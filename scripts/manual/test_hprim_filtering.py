#!/usr/bin/env python3
"""
Script de test pour vérifier le filtrage par type d'acte HPRIM.

Usage:
    .venv/bin/python3 test_hprim_filtering.py
"""
from sqlmodel import Session, select
from app.db import engine
from app.models_shared import SystemEndpoint

def test_hprim_filtering():
    """Affiche la configuration de filtrage des endpoints HPRIM."""
    with Session(engine) as session:
        # Récupérer tous les endpoints HPRIM
        hprim_endpoints = session.exec(
            select(SystemEndpoint)
            .where(SystemEndpoint.kind == "HPRIM")
            .where(SystemEndpoint.is_enabled == True)
        ).all()
        
        if not hprim_endpoints:
            print("⚠️  Aucun endpoint HPRIM configuré")
            print("\nPour tester le filtrage, créez un endpoint HPRIM avec :")
            print("""
from sqlmodel import Session, select
from app.db import engine
from app.models_shared import SystemEndpoint

with Session(engine) as session:
    endpoint = SystemEndpoint(
        name="Test HPRIM - CCAM uniquement",
        kind="HPRIM",
        role="sender",
        is_enabled=True,
        host="test.local",
        emit_hprim_ccam=True,   # ✅ CCAM
        emit_hprim_ngap=False,  # ❌ NGAP
        emit_hprim_ucd=False,   # ❌ UCD
        emit_hprim_lpp=False    # ❌ LPP
    )
    session.add(endpoint)
    session.commit()
    print(f"Endpoint créé : {endpoint.id}")
            """)
            return
        
        print(f"📡 Endpoints HPRIM configurés : {len(hprim_endpoints)}\n")
        
        for ep in hprim_endpoints:
            print(f"{'='*60}")
            print(f"Endpoint ID {ep.id} : {ep.name}")
            print(f"Role : {ep.role}")
            print(f"Host : {ep.host}:{ep.port if ep.port else 'N/A'}")
            
            # Contexte
            if ep.entite_juridique_id:
                print(f"Contexte : EJ {ep.entite_juridique_id}")
            elif ep.ght_context_id:
                print(f"Contexte : GHT {ep.ght_context_id}")
            else:
                print(f"Contexte : Global (tous)")
            
            # Filtrage par type d'acte
            print("\nTypes d'actes autorisés :")
            ccam = "✅" if getattr(ep, 'emit_hprim_ccam', False) else "❌"
            ngap = "✅" if getattr(ep, 'emit_hprim_ngap', False) else "❌"
            ucd = "✅" if getattr(ep, 'emit_hprim_ucd', False) else "❌"
            lpp = "✅" if getattr(ep, 'emit_hprim_lpp', False) else "❌"
            
            print(f"  {ccam} CCAM (Classification Commune des Actes Médicaux)")
            print(f"  {ngap} NGAP (Nomenclature Générale des Actes Professionnels)")
            print(f"  {ucd} UCD  (Unité Commune de Dispensation - médicaments)")
            print(f"  {lpp} LPP  (Liste des Produits et Prestations - dispositifs)")
            
            # Résumé
            enabled_types = []
            if getattr(ep, 'emit_hprim_ccam', False):
                enabled_types.append("CCAM")
            if getattr(ep, 'emit_hprim_ngap', False):
                enabled_types.append("NGAP")
            if getattr(ep, 'emit_hprim_ucd', False):
                enabled_types.append("UCD")
            if getattr(ep, 'emit_hprim_lpp', False):
                enabled_types.append("LPP")
            
            if enabled_types:
                print(f"\n💚 Cet endpoint émettra : {', '.join(enabled_types)}")
            else:
                print(f"\n⚠️  Aucun type d'acte activé ! Aucune émission ne sera faite.")
            print("")
        
        print(f"{'='*60}\n")
        print("✅ Vérification du filtrage terminée\n")
        print("📌 Comportement attendu :")
        print("  - Un acte CCAM sera émis uniquement vers les endpoints avec emit_hprim_ccam=True")
        print("  - Un acte NGAP sera émis uniquement vers les endpoints avec emit_hprim_ngap=True")
        print("  - etc.")
        print("\n💡 Créez plusieurs endpoints pour tester le routage sélectif :")
        print("  - Endpoint 1 : CCAM uniquement → Facturation bloc")
        print("  - Endpoint 2 : UCD + LPP uniquement → Pharmacie")
        print("  - Endpoint 3 : Tous types → Archive centrale")

if __name__ == "__main__":
    test_hprim_filtering()
