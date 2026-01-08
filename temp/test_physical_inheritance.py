#!/usr/bin/env python3
"""
Test de l'héritage des champs de localisation physique
(etage, aile, type_chambre) dans la hiérarchie des modèles.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app.models_structure import (
    EntiteGeographique, Pole, Service, UniteFonctionnelle,
    UniteHebergement, Chambre, Lit
)

def test_physical_inheritance():
    """Test que l'héritage des champs de localisation physique fonctionne"""

    print("=== TEST DE L'HÉRITAGE DES CHAMPS DE LOCALISATION PHYSIQUE ===\n")

    # Créer une hiérarchie de test
    try:
        # Entité géographique avec valeurs de localisation
        eg = EntiteGeographique(
            name="Hôpital Test",
            etage="RDC",
            aile="Aile A",
            type_chambre="Chambre double"
        )

        # Pôle
        pole = Pole(
            name="Pôle Médical",
            entite_geo=eg
        )

        # Service
        service = Service(
            name="Service de Chirurgie",
            pole=pole
        )

        # Unité fonctionnelle
        uf = UniteFonctionnelle(
            name="Unité de Chirurgie Viscérale",
            service=service
        )

        # Unité d'hébergement
        uh = UniteHebergement(
            name="Unité d'Hospitalisation",
            unite_fonctionnelle=uf
        )

        # Chambre
        chambre = Chambre(
            name="Chambre 101",
            unite_hebergement=uh
        )

        # Lit
        lit = Lit(
            name="Lit 1",
            chambre=chambre
        )

        # Tests d'héritage
        test_cases = [
            ("Pole", pole, "inherited_etage", "RDC"),
            ("Pole", pole, "inherited_aile", "Aile A"),
            ("Pole", pole, "inherited_type_chambre", "Chambre double"),
            ("Service", service, "inherited_etage", "RDC"),
            ("Service", service, "inherited_aile", "Aile A"),
            ("Service", service, "inherited_type_chambre", "Chambre double"),
            ("UniteFonctionnelle", uf, "inherited_etage", "RDC"),
            ("UniteFonctionnelle", uf, "inherited_aile", "Aile A"),
            ("UniteFonctionnelle", uf, "inherited_type_chambre", "Chambre double"),
            ("UniteHebergement", uh, "inherited_etage", "RDC"),
            ("UniteHebergement", uh, "inherited_aile", "Aile A"),
            ("UniteHebergement", uh, "inherited_type_chambre", "Chambre double"),
            ("Chambre", chambre, "inherited_etage", "RDC"),
            ("Chambre", chambre, "inherited_aile", "Aile A"),
            ("Chambre", chambre, "inherited_type_chambre", "Chambre double"),
            ("Lit", lit, "inherited_etage", "RDC"),
            ("Lit", lit, "inherited_aile", "Aile A"),
            ("Lit", lit, "inherited_type_chambre", "Chambre double"),
        ]

        success_count = 0
        total_tests = len(test_cases)

        for model_name, instance, property_name, expected_value in test_cases:
            try:
                actual_value = getattr(instance, property_name)
                if actual_value == expected_value:
                    print(f"✅ {model_name}.{property_name} = '{actual_value}' (attendu: '{expected_value}')")
                    success_count += 1
                else:
                    print(f"❌ {model_name}.{property_name} = '{actual_value}' (attendu: '{expected_value}')")
            except Exception as e:
                print(f"❌ {model_name}.{property_name} - Erreur: {e}")

        print(f"\n=== RÉSULTATS ===")
        print(f"Tests réussis: {success_count}/{total_tests} ({success_count/total_tests*100:.1f}%)")
        if success_count == total_tests:
            print("🎉 Tous les tests d'héritage de localisation physique sont passés !")
            return True
        else:
            print("⚠️ Certains tests ont échoué.")
            return False

    except Exception as e:
        print(f"❌ Erreur lors de la création de la hiérarchie de test: {e}")
        return False

def test_override_behavior():
    """Test que les valeurs locales peuvent overrider l'héritage"""

    print("\n=== TEST DE L'OVERRIDE LOCAL ===\n")

    try:
        # Entité géographique
        eg = EntiteGeographique(
            name="Hôpital Test",
            etage="RDC",
            aile="Aile A",
            type_chambre="Chambre double"
        )

        # Chambre avec valeurs locales qui devraient overrider l'héritage
        chambre = Chambre(
            name="Chambre 101",
            unite_hebergement=UniteHebergement(
                name="UH",
                unite_fonctionnelle=UniteFonctionnelle(
                    name="UF",
                    service=Service(
                        name="Service",
                        pole=Pole(
                            name="Pole",
                            entite_geo=eg
                        )
                    )
                )
            ),
            etage="1er étage",  # Override
            aile="Aile B",      # Override
            type_chambre="Chambre simple"  # Override
        )

        # Les propriétés inherited_ devraient retourner les valeurs de l'entité géographique
        # Les champs directs devraient retourner les valeurs locales
        test_cases = [
            ("inherited_etage", "RDC", "valeur héritée"),
            ("inherited_aile", "Aile A", "valeur héritée"),
            ("inherited_type_chambre", "Chambre double", "valeur héritée"),
            ("etage", "1er étage", "valeur locale"),
            ("aile", "Aile B", "valeur locale"),
            ("type_chambre", "Chambre simple", "valeur locale"),
        ]

        success_count = 0
        for property_name, expected_value, description in test_cases:
            try:
                actual_value = getattr(chambre, property_name)
                if actual_value == expected_value:
                    print(f"✅ Chambre.{property_name} = '{actual_value}' ({description})")
                    success_count += 1
                else:
                    print(f"❌ Chambre.{property_name} = '{actual_value}' (attendu: '{expected_value}')")
            except Exception as e:
                print(f"❌ Chambre.{property_name} - Erreur: {e}")

        print(f"\nTests override: {success_count}/{len(test_cases)}")
        return success_count == len(test_cases)

    except Exception as e:
        print(f"❌ Erreur lors du test d'override: {e}")
        return False

if __name__ == "__main__":
    success1 = test_physical_inheritance()
    success2 = test_override_behavior()

    if success1 and success2:
        print("\n🎉 Tous les tests d'héritage de localisation physique sont passés !")
        sys.exit(0)
    else:
        print("\n❌ Certains tests ont échoué.")
        sys.exit(1)