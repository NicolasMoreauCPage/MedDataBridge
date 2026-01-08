#!/usr/bin/env python3
"""
Test simplifié de l'héritage des champs de localisation physique
sans utiliser les références forward problématiques.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

# Test basique d'import
try:
    from app.models_structure import EntiteGeographique, Pole
    print("✅ Import des modèles réussi")
except Exception as e:
    print(f"❌ Erreur d'import: {e}")
    sys.exit(1)

def test_basic_inheritance():
    """Test basique de l'héritage Pole -> EntiteGeographique"""

    print("\n=== TEST BASIQUE D'HÉRITAGE ===")

    try:
        # Créer une entité géographique
        eg = EntiteGeographique(
            name="Hôpital Test",
            etage="RDC",
            aile="Aile A",
            type_chambre="Chambre double"
        )

        # Créer un pôle
        pole = Pole(
            name="Pôle Médical",
            entite_geo=eg
        )

        # Tester l'héritage
        tests = [
            ("pole.inherited_etage", pole.inherited_etage, "RDC"),
            ("pole.inherited_aile", pole.inherited_aile, "Aile A"),
            ("pole.inherited_type_chambre", pole.inherited_type_chambre, "Chambre double"),
        ]

        success_count = 0
        for test_name, actual, expected in tests:
            if actual == expected:
                print(f"✅ {test_name} = '{actual}'")
                success_count += 1
            else:
                print(f"❌ {test_name} = '{actual}' (attendu: '{expected}')")

        print(f"\nRésultats: {success_count}/{len(tests)} tests réussis")
        return success_count == len(tests)

    except Exception as e:
        print(f"❌ Erreur: {e}")
        return False

def test_properties_existence():
    """Vérifier que toutes les propriétés d'héritage existent"""

    print("\n=== TEST D'EXISTENCE DES PROPRIÉTÉS ===")

    models_to_test = [EntiteGeographique, Pole]
    properties_to_test = [
        'inherited_etage', 'inherited_aile', 'inherited_type_chambre',
        'inherited_address_line1', 'inherited_address_line2', 'inherited_address_line3',
        'inherited_address_city', 'inherited_address_postalcode', 'inherited_address_country'
    ]

    success_count = 0
    total_tests = 0

    for model in models_to_test:
        for prop in properties_to_test:
            total_tests += 1
            if hasattr(model, prop):
                print(f"✅ {model.__name__}.{prop} existe")
                success_count += 1
            else:
                print(f"❌ {model.__name__}.{prop} manquant")

    print(f"\nRésultats: {success_count}/{total_tests} propriétés trouvées")
    return success_count == total_tests

if __name__ == "__main__":
    success1 = test_properties_existence()
    success2 = test_basic_inheritance()

    if success1 and success2:
        print("\n🎉 Tous les tests d'héritage physique sont passés !")
        sys.exit(0)
    else:
        print("\n❌ Certains tests ont échoué.")
        sys.exit(1)