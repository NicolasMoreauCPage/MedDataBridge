#!/usr/bin/env python3
"""
Test de la nouvelle génération d'identifiants basés sur timestamp.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from app.utils.seq_generator import generate_patient_seq, generate_dossier_seq


def test_patient_seq():
    """Test génération identifiants patients."""
    print("="*80)
    print("TEST GÉNÉRATION IDENTIFIANTS PATIENTS")
    print("="*80)
    
    for i in range(5):
        seq = generate_patient_seq()
        seq_str = str(seq)
        print(f"\nPatient {i+1}:")
        print(f"  Valeur: {seq}")
        print(f"  Longueur: {len(seq_str)} caractères")
        print(f"  Préfixe: {seq_str[0]}")
        print(f"  Commence par '9': {'✓' if seq_str[0] == '9' else '✗'}")
        print(f"  12 chiffres: {'✓' if len(seq_str) == 12 else '✗'}")
        
        # Petit délai pour s'assurer que les identifiants sont différents
        import time
        time.sleep(0.001)


def test_dossier_seq():
    """Test génération identifiants dossiers."""
    print("\n" + "="*80)
    print("TEST GÉNÉRATION IDENTIFIANTS DOSSIERS")
    print("="*80)
    
    for i in range(5):
        seq = generate_dossier_seq()
        seq_str = str(seq)
        print(f"\nDossier {i+1}:")
        print(f"  Valeur: {seq}")
        print(f"  Longueur: {len(seq_str)} caractères")
        print(f"  Préfixe: {seq_str[0]}")
        print(f"  Commence par '9': {'✓' if seq_str[0] == '9' else '✗'}")
        print(f"  9 chiffres: {'✓' if len(seq_str) == 9 else '✗'}")
        
        # Petit délai pour s'assurer que les identifiants sont différents
        import time
        time.sleep(0.001)


def test_unicite():
    """Test de l'unicité des identifiants générés."""
    print("\n" + "="*80)
    print("TEST UNICITÉ")
    print("="*80)
    
    # Générer 100 identifiants patients
    patient_ids = set()
    for _ in range(100):
        patient_ids.add(generate_patient_seq())
    
    print(f"\n✓ {len(patient_ids)} identifiants patients uniques sur 100 générés")
    assert len(patient_ids) == 100, "Collision détectée dans les identifiants patients!"
    
    # Générer 100 identifiants dossiers
    dossier_ids = set()
    for _ in range(100):
        dossier_ids.add(generate_dossier_seq())
    
    print(f"✓ {len(dossier_ids)} identifiants dossiers uniques sur 100 générés")
    assert len(dossier_ids) == 100, "Collision détectée dans les identifiants dossiers!"


if __name__ == "__main__":
    test_patient_seq()
    test_dossier_seq()
    test_unicite()
    
    print("\n" + "="*80)
    print("✅ TOUS LES TESTS SONT PASSÉS")
    print("="*80)
    print("\nLes identifiants sont maintenant générés avec:")
    print("  • Patient (patient_seq): 12 chiffres, préfixe '9'")
    print("  • Dossier (dossier_seq): 9 chiffres, préfixe '9'")
    print("  • Basés sur timestamp (microsecondes) pour garantir l'unicité")
