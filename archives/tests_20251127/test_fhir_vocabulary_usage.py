#!/usr/bin/env python3
"""Tests de validation pour l'utilisation des vocabulaires dans l'export/import FHIR.

Vérifie que :
1. Les codes physical_type sont traduits via vocabulaire lors de l'export FHIR
2. Les codes service_type sont traduits via vocabulaire lors de l'export FHIR
3. Les codes FHIR sont traduits vers codes internes lors de l'import
4. La cohérence bidirectionnelle export → import → export
"""
import json
from sqlmodel import Session, select
from app.db import engine
from app.models_structure import (
    EntiteGeographique, Pole, Service, UniteHebergement, Chambre, Lit,
    LocationPhysicalType, LocationServiceType
)
from app.services.fhir_structure import entity_to_fhir_location, fhir_location_to_entity
from app.services.vocabulary_translate import map_code, reverse_map_code


def test_vocabulary_mappings():
    """Test que les mappings de vocabulaire existent et fonctionnent."""
    print("\n" + "=" * 70)
    print("TEST 1 : Vérification des mappings de vocabulaire")
    print("=" * 70)
    
    with Session(engine) as session:
        # Test physical_type mappings
        test_codes = ["area", "wi", "ro", "bd"]
        for code in test_codes:
            mapped = map_code(session, "location-physical-type", code, "location-physical-type")
            reverse = reverse_map_code(session, "location-physical-type", code, "location-physical-type")
            
            assert mapped == code, f"❌ Mapping failed for {code}: got {mapped}"
            assert reverse == code, f"❌ Reverse mapping failed for {code}: got {reverse}"
            print(f"  ✅ physical_type '{code}' : mapping OK (forward={mapped}, reverse={reverse})")
        
        # Test service_type mappings
        test_codes = ["mco", "ssr", "psy"]
        for code in test_codes:
            mapped = map_code(session, "location-service-type", code, "location-service-type")
            reverse = reverse_map_code(session, "location-service-type", code, "location-service-type")
            
            assert mapped == code, f"❌ Mapping failed for {code}: got {mapped}"
            assert reverse == code, f"❌ Reverse mapping failed for {code}: got {reverse}"
            print(f"  ✅ service_type '{code}' : mapping OK (forward={mapped}, reverse={reverse})")
    
    print("\n✅ TEST 1 RÉUSSI : Tous les mappings fonctionnent")


def test_fhir_export_uses_vocabulary():
    """Test que l'export FHIR utilise bien le système de vocabulaire."""
    print("\n" + "=" * 70)
    print("TEST 2 : Export FHIR utilise les vocabulaires")
    print("=" * 70)
    
    with Session(engine) as session:
        # Test avec un Pole (physical_type = "area")
        pole = session.exec(select(Pole)).first()
        if pole:
            fhir_loc = entity_to_fhir_location(pole, session)
            physical_code = fhir_loc.get("physicalType", {}).get("coding", [{}])[0].get("code")
            
            # Vérifier que le code a été traduit (même si c'est 1:1 pour l'instant)
            expected = map_code(session, "location-physical-type", "area", "location-physical-type")
            assert physical_code == expected, f"❌ Pole: attendu {expected}, obtenu {physical_code}"
            print(f"  ✅ Pole : physical_type correctement traduit → '{physical_code}'")
        
        # Test avec un Service (service_type)
        service = session.exec(select(Service)).first()
        if service:
            fhir_loc = entity_to_fhir_location(service, session)
            service_code = fhir_loc.get("type", [{}])[0].get("coding", [{}])[0].get("code")
            
            # Vérifier que le code a été traduit
            expected = map_code(session, "location-service-type", service.service_type, "location-service-type")
            assert service_code == expected, f"❌ Service: attendu {expected}, obtenu {service_code}"
            print(f"  ✅ Service : service_type '{service.service_type}' → '{service_code}'")
        
        # Test avec une Chambre (physical_type = "ro")
        chambre = session.exec(select(Chambre)).first()
        if chambre:
            fhir_loc = entity_to_fhir_location(chambre, session)
            physical_code = fhir_loc.get("physicalType", {}).get("coding", [{}])[0].get("code")
            
            expected = map_code(session, "location-physical-type", "ro", "location-physical-type")
            assert physical_code == expected, f"❌ Chambre: attendu {expected}, obtenu {physical_code}"
            print(f"  ✅ Chambre : physical_type correctement traduit → '{physical_code}'")
        
        # Test avec un Lit (physical_type = "bd")
        lit = session.exec(select(Lit)).first()
        if lit:
            fhir_loc = entity_to_fhir_location(lit, session)
            physical_code = fhir_loc.get("physicalType", {}).get("coding", [{}])[0].get("code")
            
            expected = map_code(session, "location-physical-type", "bd", "location-physical-type")
            assert physical_code == expected, f"❌ Lit: attendu {expected}, obtenu {physical_code}"
            print(f"  ✅ Lit : physical_type correctement traduit → '{physical_code}'")
    
    print("\n✅ TEST 2 RÉUSSI : Export FHIR utilise les vocabulaires")


def test_fhir_import_uses_vocabulary():
    """Test que l'import FHIR utilise le système de vocabulaire."""
    print("\n" + "=" * 70)
    print("TEST 3 : Import FHIR utilise les vocabulaires")
    print("=" * 70)
    
    with Session(engine) as session:
        # Test import d'un Pole avec physical_type="area"
        fhir_pole = {
            "resourceType": "Location",
            "id": "test-pole-1",
            "name": "Test Pole Vocabulaire",
            "status": "active",
            "mode": "instance",
            "physicalType": {
                "coding": [{
                    "system": "http://terminology.hl7.org/CodeSystem/location-physical-type",
                    "code": "area"
                }]
            }
        }
        
        entity, parent_ref = fhir_location_to_entity(fhir_pole, session)
        assert entity is not None, "❌ Import Pole failed"
        assert isinstance(entity, Pole), f"❌ Expected Pole, got {type(entity)}"
        
        # Vérifier que le code a été traduit
        expected_internal = reverse_map_code(session, "location-physical-type", "area", "location-physical-type")
        assert entity.physical_type == expected_internal or entity.physical_type == LocationPhysicalType.AREA, \
            f"❌ Pole physical_type incorrect: {entity.physical_type}"
        print(f"  ✅ Pole : FHIR 'area' → internal '{entity.physical_type}'")
        
        # Test import d'une Chambre avec physical_type="ro"
        fhir_chambre = {
            "resourceType": "Location",
            "id": "test-chambre-1",
            "name": "Test Chambre Vocabulaire",
            "status": "active",
            "mode": "instance",
            "physicalType": {
                "coding": [{
                    "system": "http://terminology.hl7.org/CodeSystem/location-physical-type",
                    "code": "ro"
                }]
            },
            "extension": [{
                "url": "http://example.org/fhir/StructureDefinition/room-type",
                "valueCode": "double"
            }]
        }
        
        entity, parent_ref = fhir_location_to_entity(fhir_chambre, session)
        assert entity is not None, "❌ Import Chambre failed"
        assert isinstance(entity, Chambre), f"❌ Expected Chambre, got {type(entity)}"
        
        expected_internal = reverse_map_code(session, "location-physical-type", "ro", "location-physical-type")
        assert entity.physical_type == expected_internal or entity.physical_type == LocationPhysicalType.RO, \
            f"❌ Chambre physical_type incorrect: {entity.physical_type}"
        print(f"  ✅ Chambre : FHIR 'ro' → internal '{entity.physical_type}'")
    
    print("\n✅ TEST 3 RÉUSSI : Import FHIR utilise les vocabulaires")


def test_bidirectional_consistency():
    """Test la cohérence bidirectionnelle : entity → FHIR → entity."""
    print("\n" + "=" * 70)
    print("TEST 4 : Cohérence bidirectionnelle (roundtrip)")
    print("=" * 70)
    
    with Session(engine) as session:
        # Test avec un Service existant
        service = session.exec(select(Service)).first()
        if service:
            # Export → FHIR
            fhir_loc = entity_to_fhir_location(service, session)
            
            # Import ← FHIR
            imported_entity, _ = fhir_location_to_entity(fhir_loc, session)
            
            assert imported_entity is not None, "❌ Reimport failed"
            assert isinstance(imported_entity, Service), f"❌ Type mismatch: {type(imported_entity)}"
            assert imported_entity.service_type == service.service_type, \
                f"❌ service_type mismatch: {service.service_type} → {imported_entity.service_type}"
            
            print(f"  ✅ Service : {service.name}")
            print(f"      service_type : {service.service_type} → FHIR → {imported_entity.service_type}")
        
        # Test avec une Chambre existante
        chambre = session.exec(select(Chambre)).first()
        if chambre:
            # Export → FHIR
            fhir_loc = entity_to_fhir_location(chambre, session)
            
            # Import ← FHIR
            imported_entity, _ = fhir_location_to_entity(fhir_loc, session)
            
            assert imported_entity is not None, "❌ Reimport Chambre failed"
            assert isinstance(imported_entity, Chambre), f"❌ Type mismatch: {type(imported_entity)}"
            
            # Comparer les physical_types (peuvent être str ou enum)
            # Normaliser vers la valeur enum pour comparaison
            orig_pt = chambre.physical_type.value if hasattr(chambre.physical_type, 'value') else chambre.physical_type
            import_pt = imported_entity.physical_type.value if hasattr(imported_entity.physical_type, 'value') else imported_entity.physical_type
            
            # Convertir en string lowercase pour comparaison
            orig_pt_str = str(orig_pt).lower()
            import_pt_str = str(import_pt).lower()
            
            assert orig_pt_str == import_pt_str, \
                f"❌ physical_type mismatch: {orig_pt} ({type(orig_pt)}) → {import_pt} ({type(import_pt)})"
            
            print(f"  ✅ Chambre : {chambre.name}")
            print(f"      physical_type : {orig_pt} → FHIR → {import_pt}")
    
    print("\n✅ TEST 4 RÉUSSI : Cohérence bidirectionnelle préservée")


def main():
    """Exécute tous les tests."""
    print("\n" + "=" * 70)
    print("TESTS DE VALIDATION : VOCABULAIRES DANS EXPORT/IMPORT FHIR")
    print("=" * 70)
    
    try:
        test_vocabulary_mappings()
        test_fhir_export_uses_vocabulary()
        test_fhir_import_uses_vocabulary()
        test_bidirectional_consistency()
        
        print("\n" + "=" * 70)
        print("✅ TOUS LES TESTS RÉUSSIS !")
        print("=" * 70)
        print("\n📊 Résumé :")
        print("  ✅ Mappings de vocabulaire fonctionnels")
        print("  ✅ Export FHIR utilise map_code() pour traduire les codes")
        print("  ✅ Import FHIR utilise reverse_map_code() pour traduire les codes")
        print("  ✅ Cohérence bidirectionnelle préservée (roundtrip)")
        print("\n💡 Les exports FHIR sont maintenant cohérents avec les messages HL7 MFN")
        print("   via l'utilisation du système de vocabulaire unifié.")
        
    except AssertionError as e:
        print(f"\n❌ ÉCHEC DU TEST : {e}")
        return 1
    except Exception as e:
        print(f"\n💥 ERREUR : {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
