#!/usr/bin/env python3
"""
Initialisation des chambres et lits génériques (ZGEN) pour environnement de test

Usage:
    python init_generic_rooms.py

Ce script :
1. Détecte automatiquement les chambres/lits avec identifiant ZGEN
2. Les marque comme génériques (occupation multiple autorisée)
3. Met à jour la base de données
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlmodel import Session, select
from app.db import session_factory
from app.models_structure import Chambre, Lit
from app.services.structure_validation import is_generic_resource, auto_detect_generic_resources


def init_generic_resources():
    """Initialise les ressources génériques dans la base de données"""

    print("🔧 Initialisation des chambres et lits génériques (ZGEN)...")

    with session_factory() as session:
        # Compter les ressources avant
        total_chambres = session.exec(select(Chambre)).all()
        total_lits = session.exec(select(Lit)).all()

        chambres_zgen_before = sum(1 for c in total_chambres if is_generic_resource(c.identifier))
        lits_zgen_before = sum(1 for l in total_lits if is_generic_resource(l.identifier))

        print(f"📊 Avant initialisation:")
        print(f"   - Chambres totales: {len(total_chambres)}")
        print(f"   - Chambres ZGEN: {chambres_zgen_before}")
        print(f"   - Lits totaux: {len(total_lits)}")
        print(f"   - Lits ZGEN: {lits_zgen_before}")

        # Auto-détection et marquage
        auto_detect_generic_resources(session)

        # Recompter après
        chambres_after = session.exec(select(Chambre).where(Chambre.is_generic == True)).all()
        lits_after = session.exec(select(Lit).where(Lit.is_generic == True)).all()

        print(f"\n✅ Après initialisation:")
        print(f"   - Chambres génériques: {len(chambres_after)}")
        print(f"   - Lits génériques: {len(lits_after)}")

        # Lister les ressources génériques
        if chambres_after:
            print(f"\n🏥 Chambres génériques détectées:")
            for chambre in chambres_after:
                print(f"   - {chambre.identifier}: {chambre.name}")

        if lits_after:
            print(f"\n🛏️  Lits génériques détectés:")
            for lit in lits_after:
                print(f"   - {lit.identifier}: {lit.name}")

        print(f"\n🎯 Configuration terminée!")
        print(f"   Les ressources ZGEN permettent maintenant l'occupation multiple.")
        print(f"   Utile pour les environnements de développement/test.")


if __name__ == "__main__":
    init_generic_resources()</content>
<parameter name="filePath">/home/nico/Travail/Fhir_MedBridgeData/MedData_Bridge/init_generic_rooms.py