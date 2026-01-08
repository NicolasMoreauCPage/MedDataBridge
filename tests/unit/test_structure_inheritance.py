"""
Tests unitaires pour les méthodes d'héritage intelligent des modèles de structure.

Ces tests valident que l'héritage fonctionne correctement selon les règles métier :
- Statuts opérationnels cascadent depuis la racine
- Informations physiques héritent avec possibilité d'override
- Dates cascadent selon la hiérarchie
- Valeurs None sont correctement gérées
"""

import unittest
from datetime import datetime, date
from unittest.mock import Mock, patch

from app.models_structure import (
    EntiteGeographique,
    Pole,
    Service,
    UniteFonctionnelle,
    UniteHebergement,
    Chambre,
    Lit,
    LocationStatus,
    LocationMode,
    LocationPhysicalType,
)


class TestStructureInheritance(unittest.TestCase):
    """Tests pour les méthodes d'héritage des modèles de structure."""

    def setUp(self):
        """Configuration commune pour tous les tests."""
        # Créer une entité géographique racine
        self.eg = EntiteGeographique(
            id=1,
            identifier="EG001",
            name="Hôpital Central",
            operational_status="active",
            status=LocationStatus.ACTIVE,
            mode=LocationMode.INSTANCE,
            physical_type=LocationPhysicalType.BU,
            etage="RDC",
            aile="A",
            opening_date=date(2020, 1, 1),
            activation_date=date(2020, 1, 15),
            closing_date=None,
            deactivation_date=None
        )

        # Créer un pôle
        self.pole = Pole(
            id=1,
            identifier="POLE001",
            name="Pôle Médical",
            entite_geo_id=self.eg.id,
            entite_geo=self.eg,
            # Pole n'a pas de champs operational_status, etage, aile - ils héritent seulement
            opening_date=None,  # Hérite de EG
            activation_date=None,  # Hérite de EG
            closing_date=None,
            deactivation_date=None
        )

        # Créer un service
        self.service = Service(
            id=1,
            identifier="SERV001",
            name="Service de Médecine",
            pole_id=self.pole.id,
            pole=self.pole,
            # Service n'a pas de champs operational_status, etage, aile - ils héritent seulement
            opening_date=None,  # Hérite de pôle/EG
            activation_date=None,  # Hérite de pôle/EG
            closing_date=None,
            deactivation_date=None
        )

        # Créer une UF
        self.uf = UniteFonctionnelle(
            id=1,
            identifier="UF001",
            name="UF Médecine Interne",
            service_id=self.service.id,
            service=self.service,
            # UF n'a pas de champs operational_status, etage, aile - ils héritent seulement
            opening_date=None,  # Hérite de service/pôle/EG
            activation_date=None,  # Hérite de service/pôle/EG
            closing_date=None,
            deactivation_date=None
        )

        # Créer une UH
        self.uh = UniteHebergement(
            id=1,
            identifier="UH001",
            name="UH Médecine A",
            unite_fonctionnelle_id=self.uf.id,
            unite_fonctionnelle=self.uf,
            # UH n'a pas de champs operational_status, etage, aile - ils héritent seulement
            opening_date=None,  # Hérite de UF/service/pôle/EG
            activation_date=None,  # Hérite de UF/service/pôle/EG
            closing_date=None,
            deactivation_date=None
        )

        # Créer une chambre
        self.chambre = Chambre(
            id=1,
            identifier="CH001",
            name="Chambre 101",
            unite_hebergement_id=self.uh.id,
            unite_hebergement=self.uh,
            # Chambre n'a pas de champs operational_status, etage, aile - ils héritent seulement
            opening_date=None,  # Hérite de UH/UF/service/pôle/EG
            activation_date=None,  # Hérite de UH/UF/service/pôle/EG
            closing_date=None,
            deactivation_date=None
        )

        # Créer un lit
        self.lit = Lit(
            id=1,
            identifier="LIT001",
            name="Lit 1",
            chambre_id=self.chambre.id,
            chambre=self.chambre,
            # Lit n'a pas de champs operational_status, etage, aile - ils héritent seulement
            opening_date=None,  # Hérite de chambre/UH/UF/service/pôle/EG
            activation_date=None,  # Hérite de chambre/UH/UF/service/pôle/EG
            closing_date=None,
            deactivation_date=None
        )

    def test_pole_inheritance_from_eg(self):
        """Test que les pôles héritent correctement des entités géographiques."""
        # Test héritage statut opérationnel
        self.assertEqual(
            self.pole.get_effective_operational_status(),
            "active"
        )

        # Test héritage statut
        self.assertEqual(
            self.pole.get_effective_status(),
            LocationStatus.ACTIVE
        )

        # Test héritage mode
        self.assertEqual(
            self.pole.get_effective_mode(),
            LocationMode.INSTANCE
        )

        # Test héritage étage
        self.assertEqual(self.pole.get_effective_etage(), "RDC")

        # Test héritage aile
        self.assertEqual(self.pole.get_effective_aile(), "A")

        # Test héritage dates
        self.assertEqual(self.pole.get_effective_opening_date(), date(2020, 1, 1))
        self.assertEqual(self.pole.get_effective_activation_date(), date(2020, 1, 15))

    def test_service_inheritance_from_pole(self):
        """Test que les services héritent correctement des pôles."""
        # Le service hérite de l'EG via le pôle
        self.assertEqual(
            self.service.get_effective_operational_status(),
            "active"
        )
        self.assertEqual(self.service.get_effective_etage(), "RDC")
        self.assertEqual(self.service.get_effective_opening_date(), date(2020, 1, 1))

    def test_uf_inheritance_from_service(self):
        """Test que les UFs héritent correctement des services."""
        # L'UF hérite de l'EG via service/pôle
        self.assertEqual(
            self.uf.get_effective_operational_status(),
            "active"
        )
        self.assertEqual(self.uf.get_effective_etage(), "RDC")
        self.assertEqual(self.uf.get_effective_opening_date(), date(2020, 1, 1))

    def test_uh_inheritance_from_uf(self):
        """Test que les UHs héritent correctement des UFs."""
        # L'UH hérite de l'EG via UF/service/pôle
        self.assertEqual(
            self.uh.get_effective_operational_status(),
            "active"
        )
        self.assertEqual(self.uh.get_effective_etage(), "RDC")
        self.assertEqual(self.uh.get_effective_opening_date(), date(2020, 1, 1))

    def test_chambre_inheritance_from_uh(self):
        """Test que les chambres héritent correctement des UHs."""
        # La chambre hérite de l'EG via UH/UF/service/pôle
        self.assertEqual(
            self.chambre.get_effective_operational_status(),
            "active"
        )
        self.assertEqual(self.chambre.get_effective_etage(), "RDC")
        self.assertEqual(self.chambre.get_effective_opening_date(), date(2020, 1, 1))

    def test_lit_inheritance_from_chambre(self):
        """Test que les lits héritent correctement des chambres."""
        # Le lit hérite de l'EG via chambre/UH/UF/service/pôle
        self.assertEqual(
            self.lit.get_effective_operational_status(),
            "active"
        )
        self.assertEqual(self.lit.get_effective_etage(), "RDC")
        self.assertEqual(self.lit.get_effective_opening_date(), date(2020, 1, 1))

    def test_override_inheritance(self):
        """Test que les valeurs locales override l'héritage pour les champs qui le permettent."""
        # Modifier le pôle pour overrider certaines valeurs (seulement celles qui existent sur Pole)
        self.pole.opening_date = date(2021, 6, 1)
        self.pole.activation_date = date(2021, 6, 15)

        # Vérifier que les valeurs locales sont utilisées pour les dates
        self.assertEqual(self.pole.get_effective_opening_date(), date(2021, 6, 1))
        self.assertEqual(self.pole.get_effective_activation_date(), date(2021, 6, 15))

        # operational_status et etage ne peuvent pas être overriden au niveau Pole
        # Ils héritent toujours de EG
        self.assertEqual(self.pole.get_effective_operational_status(), "active")
        self.assertEqual(self.pole.get_effective_etage(), "RDC")

        # Vérifier que les services héritent des valeurs du pôle (pour les dates) et de EG (pour operational_status)
        self.assertEqual(self.service.get_effective_operational_status(), "active")
        self.assertEqual(self.service.get_effective_etage(), "RDC")
        self.assertEqual(self.service.get_effective_opening_date(), date(2021, 6, 1))

    def test_none_values_handling(self):
        """Test que les valeurs None sont correctement gérées."""
        # Créer un pôle sans entité géographique et sans valeurs locales
        pole_orphan = Pole(
            id=2,
            identifier="POLE002",
            name="Pôle Orphelin",
            status=None,  # Forcer à None pour tester l'héritage
            mode=None,    # Forcer à None pour tester l'héritage
            opening_date=None,
            activation_date=None,
            closing_date=None,
            deactivation_date=None
        )

        # Les méthodes doivent retourner None quand il n'y a pas de parent
        self.assertIsNone(pole_orphan.get_effective_operational_status())
        self.assertIsNone(pole_orphan.get_effective_status())
        self.assertIsNone(pole_orphan.get_effective_mode())
        self.assertIsNone(pole_orphan.get_effective_etage())
        self.assertIsNone(pole_orphan.get_effective_aile())
        self.assertIsNone(pole_orphan.get_effective_opening_date())

    def test_deep_inheritance_chain(self):
        """Test une chaîne d'héritage complète."""
        # Modifier l'EG
        self.eg.operational_status = "suspended"
        self.eg.etage = "Sous-sol"
        self.eg.closing_date = date(2025, 12, 31)

        # Vérifier que tous les niveaux héritent
        entities = [self.pole, self.service, self.uf, self.uh, self.chambre, self.lit]

        for entity in entities:
            with self.subTest(entity=entity.__class__.__name__):
                self.assertEqual(
                    entity.get_effective_operational_status(),
                    "suspended"
                )
                self.assertEqual(entity.get_effective_etage(), "Sous-sol")
                self.assertEqual(entity.get_effective_closing_date(), date(2025, 12, 31))

    def test_date_cascade_logic(self):
        """Test la logique de cascade des dates."""
        # Les dates doivent cascader: ouverture -> activation -> fermeture -> désactivation

        # Test cascade d'ouverture
        self.eg.opening_date = date(2020, 1, 1)
        self.assertEqual(self.lit.get_effective_opening_date(), date(2020, 1, 1))

        # Test cascade d'activation
        self.eg.activation_date = date(2020, 1, 15)
        self.assertEqual(self.lit.get_effective_activation_date(), date(2020, 1, 15))

        # Test cascade de fermeture
        self.eg.closing_date = date(2025, 12, 31)
        self.assertEqual(self.lit.get_effective_closing_date(), date(2025, 12, 31))

        # Test cascade de désactivation
        self.eg.deactivation_date = date(2026, 1, 15)
        self.assertEqual(self.lit.get_effective_deactivation_date(), date(2026, 1, 15))

