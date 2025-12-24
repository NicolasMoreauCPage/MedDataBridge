"""
Tests unitaires pour le service venues (app/services/venues_service.py).

Ce service gère :
- Création de venues avec génération de séquence
- Mise à jour de venues
- Validation des dossiers associés
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from sqlmodel import Session

# Import direct pour éviter les conflits
from app.services.venues_service import (
    create_venue,
    update_venue,
    VenueCreateSchema,
    VenueUpdateSchema,
)


class TestVenuesService(unittest.TestCase):
    """Tests pour le service venues."""

    def test_create_venue_success(self):
        """Test création venue - succès."""
        mock_session = Mock()

        # Mock dossier existant
        mock_dossier = Mock()
        mock_dossier.id = 123
        mock_session.get.return_value = mock_dossier

        # Mock données de création
        create_data = VenueCreateSchema(
            dossier_id=123,
            uf_responsabilite="CARDIO",
            start_time=datetime(2023, 12, 1, 10, 30, 0),
            hospital_service="Cardiologie",
            assigned_location="Chambre 101",
            attending_provider="Dr. Smith",
            code="HOSP",
            label="Hospitalisation programmée"
        )

        with patch('app.services.venues_service.get_next_sequence') as mock_get_next_seq:
            mock_get_next_seq.return_value = 456

            result = create_venue(mock_session, create_data)

            self.assertIsNotNone(result)
            self.assertEqual(result.dossier_id, 123)
            self.assertEqual(result.uf_responsabilite, "CARDIO")
            self.assertEqual(result.start_time, datetime(2023, 12, 1, 10, 30, 0))
            self.assertEqual(result.venue_seq, 456)
            self.assertEqual(result.hospital_service, "Cardiologie")
            self.assertEqual(result.assigned_location, "Chambre 101")
            self.assertEqual(result.attending_provider, "Dr. Smith")
            self.assertEqual(result.code, "HOSP")
            self.assertEqual(result.label, "Hospitalisation programmée")

            mock_session.add.assert_called_once()
            mock_session.commit.assert_called_once()
            mock_session.refresh.assert_called_once()

    def test_create_venue_with_provided_seq(self):
        """Test création venue avec séquence fournie."""
        mock_session = Mock()

        # Mock dossier existant
        mock_dossier = Mock()
        mock_dossier.id = 123
        mock_session.get.return_value = mock_dossier

        # Mock données de création avec séquence
        create_data = VenueCreateSchema(
            dossier_id=123,
            uf_responsabilite="CARDIO",
            start_time=datetime(2023, 12, 1, 10, 30, 0),
            venue_seq=789
        )

        result = create_venue(mock_session, create_data)

        self.assertEqual(result.venue_seq, 789)
        # get_next_sequence ne devrait pas être appelé
        with patch('app.services.venues_service.get_next_sequence') as mock_get_next_seq:
            mock_get_next_seq.assert_not_called()

    def test_create_venue_dossier_not_found(self):
        """Test création venue - dossier non trouvé."""
        mock_session = Mock()
        mock_session.get.return_value = None

        create_data = VenueCreateSchema(
            dossier_id=999,
            uf_responsabilite="CARDIO",
            start_time=datetime(2023, 12, 1, 10, 30, 0)
        )

        with self.assertRaises(ValueError) as context:
            create_venue(mock_session, create_data)

        self.assertIn("Le dossier avec l'ID 999 n'existe pas", str(context.exception))

    def test_create_venue_error_rollback(self):
        """Test création venue - erreur avec rollback."""
        mock_session = Mock()

        # Mock dossier existant
        mock_dossier = Mock()
        mock_dossier.id = 123
        mock_session.get.return_value = mock_dossier

        # Simuler une erreur lors de l'ajout
        mock_session.add.side_effect = Exception("Database error")

        create_data = VenueCreateSchema(
            dossier_id=123,
            uf_responsabilite="CARDIO",
            start_time=datetime(2023, 12, 1, 10, 30, 0)
        )

        with patch('app.services.venues_service.get_next_sequence') as mock_get_next_seq:
            mock_get_next_seq.return_value = 456

            with self.assertRaises(Exception) as context:
                create_venue(mock_session, create_data)

            self.assertEqual(str(context.exception), "Database error")
            mock_session.rollback.assert_called_once()

    def test_update_venue_success(self):
        """Test mise à jour venue - succès."""
        mock_session = Mock()

        # Mock venue existante
        mock_venue = Mock()
        mock_venue.id = 456

        # Mock données de mise à jour
        update_data = VenueUpdateSchema(
            dossier_id=123,
            uf_responsabilite="NEURO",
            start_time=datetime(2023, 12, 2, 14, 0, 0),
            venue_seq=789
        )

        with patch('app.services.venues_service.attributes.flag_modified'):
            result = update_venue(mock_session, mock_venue, update_data)

            self.assertEqual(result, mock_venue)

            # Vérifier que les attributs ont été mis à jour
            self.assertEqual(mock_venue.dossier_id, 123)
            self.assertEqual(mock_venue.uf_responsabilite, "NEURO")
            self.assertEqual(mock_venue.start_time, datetime(2023, 12, 2, 14, 0, 0))
            self.assertEqual(mock_venue.venue_seq, 789)

            mock_session.add.assert_called_once_with(mock_venue)
            mock_session.commit.assert_called_once()
            mock_session.refresh.assert_called_once_with(mock_venue)

    def test_update_venue_error_rollback(self):
        """Test mise à jour venue - erreur avec rollback."""
        mock_session = Mock()

        # Mock venue
        mock_venue = Mock()
        mock_venue.id = 456

        # Simuler une erreur lors du commit
        mock_session.commit.side_effect = Exception("Database error")

        update_data = VenueUpdateSchema(
            dossier_id=123,
            uf_responsabilite="NEURO",
            start_time=datetime(2023, 12, 2, 14, 0, 0),
            venue_seq=789
        )

        with patch('app.services.venues_service.attributes.flag_modified'):
            with self.assertRaises(Exception) as context:
                update_venue(mock_session, mock_venue, update_data)

            self.assertEqual(str(context.exception), "Database error")
            mock_session.rollback.assert_called_once()

    def test_venue_create_schema_minimal(self):
        """Test schéma de création avec données minimales."""
        schema = VenueCreateSchema(
            dossier_id=123,
            uf_responsabilite="CARDIO",
            start_time=datetime(2023, 12, 1, 10, 30, 0)
        )

        self.assertEqual(schema.dossier_id, 123)
        self.assertEqual(schema.uf_responsabilite, "CARDIO")
        self.assertEqual(schema.start_time, datetime(2023, 12, 1, 10, 30, 0))
        self.assertIsNone(schema.venue_seq)
        self.assertIsNone(schema.hospital_service)
        self.assertIsNone(schema.assigned_location)
        self.assertIsNone(schema.attending_provider)
        self.assertIsNone(schema.code)
        self.assertIsNone(schema.label)

    def test_venue_create_schema_complete(self):
        """Test schéma de création avec toutes les données."""
        schema = VenueCreateSchema(
            dossier_id=123,
            uf_responsabilite="CARDIO",
            start_time=datetime(2023, 12, 1, 10, 30, 0),
            venue_seq=456,
            hospital_service="Cardiologie",
            assigned_location="Chambre 101",
            attending_provider="Dr. Smith",
            code="HOSP",
            label="Hospitalisation programmée"
        )

        self.assertEqual(schema.dossier_id, 123)
        self.assertEqual(schema.uf_responsabilite, "CARDIO")
        self.assertEqual(schema.start_time, datetime(2023, 12, 1, 10, 30, 0))
        self.assertEqual(schema.venue_seq, 456)
        self.assertEqual(schema.hospital_service, "Cardiologie")
        self.assertEqual(schema.assigned_location, "Chambre 101")
        self.assertEqual(schema.attending_provider, "Dr. Smith")
        self.assertEqual(schema.code, "HOSP")
        self.assertEqual(schema.label, "Hospitalisation programmée")

    def test_venue_update_schema_validation(self):
        """Test schéma de mise à jour."""
        schema = VenueUpdateSchema(
            dossier_id=123,
            uf_responsabilite="NEURO",
            start_time=datetime(2023, 12, 2, 14, 0, 0),
            venue_seq=789
        )

        self.assertEqual(schema.dossier_id, 123)
        self.assertEqual(schema.uf_responsabilite, "NEURO")
        self.assertEqual(schema.start_time, datetime(2023, 12, 2, 14, 0, 0))
        self.assertEqual(schema.venue_seq, 789)


if __name__ == "__main__":
    unittest.main()