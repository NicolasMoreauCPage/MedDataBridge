#!/usr/bin/env python3
"""
Test script to validate operational status inheritance in hierarchical models.
Uses mock classes to avoid import dependencies.
"""

from typing import Optional
from enum import Enum


class LocationPhysicalType(str, Enum):
    SITE = "site"
    BUILDING = "building"
    WING = "wing"
    WARD = "ward"
    ROOM = "room"
    BED = "bed"
    VEHICLE = "vehicle"
    HOUSE = "house"
    CABINET = "cabinet"
    ROAD = "road"
    AREA = "area"
    JURISDICTION = "jurisdiction"


class MockEntiteGeographique:
    def __init__(self, operational_status=None, status=None, mode=None, physical_type=None):
        self.operational_status = operational_status
        self.status = status
        self.mode = mode
        self.physical_type = physical_type


class MockPole:
    def __init__(self, entite_geo=None):
        self.entite_geo = entite_geo

    def get_inherited_operational_status(self) -> Optional[str]:
        """Statut opérationnel hérité de l'entité géographique parente"""
        if self.entite_geo:
            return self.entite_geo.operational_status
        return None

    def get_inherited_status(self) -> Optional[str]:
        """Statut hérité de l'entité géographique parente"""
        if self.entite_geo:
            return self.entite_geo.status
        return None

    def get_inherited_mode(self) -> Optional[str]:
        """Mode hérité de l'entité géographique parente"""
        if self.entite_geo:
            return self.entite_geo.mode
        return None

    def get_inherited_physical_type(self) -> Optional[LocationPhysicalType]:
        """Type physique hérité de l'entité géographique parente"""
        if self.entite_geo:
            return self.entite_geo.physical_type
        return None


class MockService:
    def __init__(self, pole=None):
        self.pole = pole

    def get_inherited_operational_status(self) -> Optional[str]:
        """Statut opérationnel hérité de l'entité géographique parente"""
        if self.pole and self.pole.entite_geo:
            return self.pole.entite_geo.operational_status
        return None

    def get_inherited_status(self) -> Optional[str]:
        """Statut hérité de l'entité géographique parente"""
        if self.pole and self.pole.entite_geo:
            return self.pole.entite_geo.status
        return None

    def get_inherited_mode(self) -> Optional[str]:
        """Mode hérité de l'entité géographique parente"""
        if self.pole and self.pole.entite_geo:
            return self.pole.entite_geo.mode
        return None

    def get_inherited_physical_type(self) -> Optional[LocationPhysicalType]:
        """Type physique hérité de l'entité géographique parente"""
        if self.pole and self.pole.entite_geo:
            return self.pole.entite_geo.physical_type
        return None


class MockUniteFonctionnelle:
    def __init__(self, service=None):
        self.service = service

    def get_inherited_operational_status(self) -> Optional[str]:
        """Statut opérationnel hérité de l'entité géographique parente"""
        if self.service and self.service.pole and self.service.pole.entite_geo:
            return self.service.pole.entite_geo.operational_status
        return None

    def get_inherited_status(self) -> Optional[str]:
        """Statut hérité de l'entité géographique parente"""
        if self.service and self.service.pole and self.service.pole.entite_geo:
            return self.service.pole.entite_geo.status
        return None

    def get_inherited_mode(self) -> Optional[str]:
        """Mode hérité de l'entité géographique parente"""
        if self.service and self.service.pole and self.service.pole.entite_geo:
            return self.service.pole.entite_geo.mode
        return None

    def get_inherited_physical_type(self) -> Optional[LocationPhysicalType]:
        """Type physique hérité de l'entité géographique parente"""
        if self.service and self.service.pole and self.service.pole.entite_geo:
            return self.service.pole.entite_geo.physical_type
        return None


class MockUniteHebergement:
    def __init__(self, unite_fonctionnelle=None, operational_status=None, status=None, mode=None, physical_type=None):
        self.unite_fonctionnelle = unite_fonctionnelle
        self.operational_status = operational_status
        self.status = status
        self.mode = mode
        self.physical_type = physical_type

    def get_inherited_operational_status(self) -> Optional[str]:
        """Statut opérationnel hérité de l'entité géographique parente"""
        # Check if this entity has its own value first
        if self.operational_status is not None:
            return self.operational_status
        # Otherwise inherit from parent
        if self.unite_fonctionnelle and self.unite_fonctionnelle.service and self.unite_fonctionnelle.service.pole and self.unite_fonctionnelle.service.pole.entite_geo:
            return self.unite_fonctionnelle.service.pole.entite_geo.operational_status
        return None

    def get_inherited_status(self) -> Optional[str]:
        """Statut hérité de l'entité géographique parente"""
        if self.status is not None:
            return self.status
        if self.unite_fonctionnelle and self.unite_fonctionnelle.service and self.unite_fonctionnelle.service.pole and self.unite_fonctionnelle.service.pole.entite_geo:
            return self.unite_fonctionnelle.service.pole.entite_geo.status
        return None

    def get_inherited_mode(self) -> Optional[str]:
        """Mode hérité de l'entité géographique parente"""
        if self.mode is not None:
            return self.mode
        if self.unite_fonctionnelle and self.unite_fonctionnelle.service and self.unite_fonctionnelle.service.pole and self.unite_fonctionnelle.service.pole.entite_geo:
            return self.unite_fonctionnelle.service.pole.entite_geo.mode
        return None

    def get_inherited_physical_type(self) -> Optional[LocationPhysicalType]:
        """Type physique hérité de l'entité géographique parente"""
        if self.physical_type is not None:
            return self.physical_type
        if self.unite_fonctionnelle and self.unite_fonctionnelle.service and self.unite_fonctionnelle.service.pole and self.unite_fonctionnelle.service.pole.entite_geo:
            return self.unite_fonctionnelle.service.pole.entite_geo.physical_type
        return None


class MockChambre:
    def __init__(self, unite_hebergement=None):
        self.unite_hebergement = unite_hebergement

    def get_inherited_operational_status(self) -> Optional[str]:
        """Statut opérationnel hérité de l'entité géographique parente"""
        if self.unite_hebergement:
            return self.unite_hebergement.get_inherited_operational_status()
        return None

    def get_inherited_status(self) -> Optional[str]:
        """Statut hérité de l'entité géographique parente"""
        if self.unite_hebergement:
            return self.unite_hebergement.get_inherited_status()
        return None

    def get_inherited_mode(self) -> Optional[str]:
        """Mode hérité de l'entité géographique parente"""
        if self.unite_hebergement:
            return self.unite_hebergement.get_inherited_mode()
        return None

    def get_inherited_physical_type(self) -> Optional[LocationPhysicalType]:
        """Type physique hérité de l'entité géographique parente"""
        if self.unite_hebergement:
            return self.unite_hebergement.get_inherited_physical_type()
        return None


class MockLit:
    def __init__(self, chambre=None):
        self.chambre = chambre

    def get_inherited_operational_status(self) -> Optional[str]:
        """Statut opérationnel hérité de l'entité géographique parente"""
        if self.chambre and self.chambre.unite_hebergement and self.chambre.unite_hebergement.unite_fonctionnelle and self.chambre.unite_hebergement.unite_fonctionnelle.service and self.chambre.unite_hebergement.unite_fonctionnelle.service.pole and self.chambre.unite_hebergement.unite_fonctionnelle.service.pole.entite_geo:
            return self.chambre.unite_hebergement.unite_fonctionnelle.service.pole.entite_geo.operational_status
        return None

    def get_inherited_status(self) -> Optional[str]:
        """Statut hérité de l'entité géographique parente"""
        if self.chambre and self.chambre.unite_hebergement and self.chambre.unite_hebergement.unite_fonctionnelle and self.chambre.unite_hebergement.unite_fonctionnelle.service and self.chambre.unite_hebergement.unite_fonctionnelle.service.pole and self.chambre.unite_hebergement.unite_fonctionnelle.service.pole.entite_geo:
            return self.chambre.unite_hebergement.unite_fonctionnelle.service.pole.entite_geo.status
        return None

    def get_inherited_mode(self) -> Optional[str]:
        """Mode hérité de l'entité géographique parente"""
        if self.chambre and self.chambre.unite_hebergement and self.chambre.unite_hebergement.unite_fonctionnelle and self.chambre.unite_hebergement.unite_fonctionnelle.service and self.chambre.unite_hebergement.unite_fonctionnelle.service.pole and self.chambre.unite_hebergement.unite_fonctionnelle.service.pole.entite_geo:
            return self.chambre.unite_hebergement.unite_fonctionnelle.service.pole.entite_geo.mode
        return None

    def get_inherited_physical_type(self) -> Optional[LocationPhysicalType]:
        """Type physique hérité de l'entité géographique parente"""
        if self.chambre and self.chambre.unite_hebergement and self.chambre.unite_hebergement.unite_fonctionnelle and self.chambre.unite_hebergement.unite_fonctionnelle.service and self.chambre.unite_hebergement.unite_fonctionnelle.service.pole and self.chambre.unite_hebergement.unite_fonctionnelle.service.pole.entite_geo:
            return self.chambre.unite_hebergement.unite_fonctionnelle.service.pole.entite_geo.physical_type
        return None


def test_operational_status_inheritance():
    """Test that operational status fields are properly inherited down the hierarchy."""

    # Create root entity with operational status
    entite_geo = MockEntiteGeographique(
        operational_status="active",
        status="active",
        mode="instance",
        physical_type=LocationPhysicalType.SITE
    )

    # Create pole (inherits from entite_geo)
    pole = MockPole(entite_geo=entite_geo)

    # Create service (inherits from pole)
    service = MockService(pole=pole)

    # Create unite fonctionnelle (inherits from service)
    uf = MockUniteFonctionnelle(service=service)

    # Create unite hebergement (inherits from uf)
    uh = MockUniteHebergement(unite_fonctionnelle=uf)

    # Create chambre (inherits from uh)
    chambre = MockChambre(unite_hebergement=uh)

    # Create lit (inherits from chambre)
    lit = MockLit(chambre=chambre)

    # Test inheritance at each level
    print("Testing operational status inheritance...")

    # Test Pole inheritance
    assert pole.get_inherited_operational_status() == "active", f"Pole operational_status: expected 'active', got {pole.get_inherited_operational_status()}"
    assert pole.get_inherited_status() == "active", f"Pole status: expected 'active', got {pole.get_inherited_status()}"
    assert pole.get_inherited_mode() == "instance", f"Pole mode: expected 'instance', got {pole.get_inherited_mode()}"
    assert pole.get_inherited_physical_type() == LocationPhysicalType.SITE, f"Pole physical_type: expected SITE, got {pole.get_inherited_physical_type()}"
    print("✓ Pole inheritance working")

    # Test Service inheritance
    assert service.get_inherited_operational_status() == "active", f"Service operational_status: expected 'active', got {service.get_inherited_operational_status()}"
    assert service.get_inherited_status() == "active", f"Service status: expected 'active', got {service.get_inherited_status()}"
    assert service.get_inherited_mode() == "instance", f"Service mode: expected 'instance', got {service.get_inherited_mode()}"
    assert service.get_inherited_physical_type() == LocationPhysicalType.SITE, f"Service physical_type: expected SITE, got {service.get_inherited_physical_type()}"
    print("✓ Service inheritance working")

    # Test UniteFonctionnelle inheritance
    assert uf.get_inherited_operational_status() == "active", f"UF operational_status: expected 'active', got {uf.get_inherited_operational_status()}"
    assert uf.get_inherited_status() == "active", f"UF status: expected 'active', got {uf.get_inherited_status()}"
    assert uf.get_inherited_mode() == "instance", f"UF mode: expected 'instance', got {uf.get_inherited_mode()}"
    assert uf.get_inherited_physical_type() == LocationPhysicalType.SITE, f"UF physical_type: expected SITE, got {uf.get_inherited_physical_type()}"
    print("✓ UniteFonctionnelle inheritance working")

    # Test UniteHebergement inheritance
    assert uh.get_inherited_operational_status() == "active", f"UH operational_status: expected 'active', got {uh.get_inherited_operational_status()}"
    assert uh.get_inherited_status() == "active", f"UH status: expected 'active', got {uh.get_inherited_status()}"
    assert uh.get_inherited_mode() == "instance", f"UH mode: expected 'instance', got {uh.get_inherited_mode()}"
    assert uh.get_inherited_physical_type() == LocationPhysicalType.SITE, f"UH physical_type: expected SITE, got {uh.get_inherited_physical_type()}"
    print("✓ UniteHebergement inheritance working")

    # Test Chambre inheritance
    assert chambre.get_inherited_operational_status() == "active", f"Chambre operational_status: expected 'active', got {chambre.get_inherited_operational_status()}"
    assert chambre.get_inherited_status() == "active", f"Chambre status: expected 'active', got {chambre.get_inherited_status()}"
    assert chambre.get_inherited_mode() == "instance", f"Chambre mode: expected 'instance', got {chambre.get_inherited_mode()}"
    assert chambre.get_inherited_physical_type() == LocationPhysicalType.SITE, f"Chambre physical_type: expected SITE, got {chambre.get_inherited_physical_type()}"
    print("✓ Chambre inheritance working")

    # Test Lit inheritance
    assert lit.get_inherited_operational_status() == "active", f"Lit operational_status: expected 'active', got {lit.get_inherited_operational_status()}"
    assert lit.get_inherited_status() == "active", f"Lit status: expected 'active', got {lit.get_inherited_status()}"
    assert lit.get_inherited_mode() == "instance", f"Lit mode: expected 'instance', got {lit.get_inherited_mode()}"
    assert lit.get_inherited_physical_type() == LocationPhysicalType.SITE, f"Lit physical_type: expected SITE, got {lit.get_inherited_physical_type()}"
    print("✓ Lit inheritance working")

    print("\n🎉 All operational status inheritance tests passed!")

def test_override_behavior():
    """Test that child entities can override inherited values."""

    # Create root entity
    entite_geo = MockEntiteGeographique(
        operational_status="active",
        status="active",
        mode="instance",
        physical_type=LocationPhysicalType.SITE
    )

    # Create unite hebergement with its own operational_status
    uf = MockUniteFonctionnelle()  # No service for this test
    uh = MockUniteHebergement(
        unite_fonctionnelle=uf,
        operational_status="suspended",  # Override
        status="suspended",  # Override
        mode="kind",  # Override
        physical_type=LocationPhysicalType.WING  # Override
    )

    chambre = MockChambre(unite_hebergement=uh)

    # Test that chambre uses its parent's override values
    assert chambre.get_inherited_operational_status() == "suspended", f"Chambre should inherit 'suspended', got {chambre.get_inherited_operational_status()}"
    assert chambre.get_inherited_status() == "suspended", f"Chambre should inherit 'suspended', got {chambre.get_inherited_status()}"
    assert chambre.get_inherited_mode() == "kind", f"Chambre should inherit 'kind', got {chambre.get_inherited_mode()}"
    assert chambre.get_inherited_physical_type() == LocationPhysicalType.WING, f"Chambre should inherit WING, got {chambre.get_inherited_physical_type()}"

    print("✓ Override behavior test passed!")

if __name__ == "__main__":
    try:
        test_operational_status_inheritance()
        test_override_behavior()
        print("\n✅ All tests completed successfully!")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        exit(1)