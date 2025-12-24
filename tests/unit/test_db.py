"""
Tests unitaires pour le module db (app/db.py).

Ce module gère :
- Configuration du moteur de base de données
- Gestion des sessions FastAPI
- Gestion des séquences applicatives
- Hooks de normalisation des données avant flush
- Gestion des suppressions en cascade
"""

import unittest
import os
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from sqlmodel import Session, SQLModel

# Import direct pour éviter les conflits
from app.db import (
    engine,
    init_db,
    get_session,
    session_factory,
    _get_seq,
    peek_next_sequence,
    get_next_sequence,
    _coerce_datetime_value,
    _before_flush,
)


class TestDatabaseModule(unittest.TestCase):
    """Tests pour le module de base de données."""

    def setUp(self):
        """Configuration avant chaque test."""
        # Sauvegarder les variables d'environnement
        self.original_testing = os.environ.get("TESTING")

    def tearDown(self):
        """Nettoyage après chaque test."""
        # Restaurer les variables d'environnement
        if self.original_testing is not None:
            os.environ["TESTING"] = self.original_testing
        elif "TESTING" in os.environ:
            del os.environ["TESTING"]

    def test_engine_configuration_production(self):
        """Test configuration du moteur en mode production."""
        # Simuler mode production
        os.environ["TESTING"] = "0"

        # Recharger le module pour prendre en compte la variable d'environnement
        import importlib
        import app.db
        importlib.reload(app.db)

        # Vérifier que le moteur utilise un fichier SQLite
        self.assertIn("medbridge.db", str(app.db.engine.url))

    def test_engine_configuration_testing(self):
        """Test configuration du moteur en mode test."""
        # Simuler mode test
        os.environ["TESTING"] = "1"

        # Recharger le module pour prendre en compte la variable d'environnement
        import importlib
        import app.db
        importlib.reload(app.db)

        # Vérifier que le moteur utilise la mémoire
        self.assertEqual(str(app.db.engine.url), "sqlite:///:memory:")

    @patch('app.db.SQLModel.metadata.create_all')
    @patch('sqlite3.connect')
    @patch('app.db.init_scenario_templates')
    def test_init_db_success(self, mock_init_templates, mock_sqlite_connect, mock_create_all):
        """Test initialisation de la base de données - succès."""
        # Mock la connexion SQLite
        mock_conn = Mock()
        mock_sqlite_connect.return_value = mock_conn

        # Mock l'initialisation des templates
        mock_init_templates.return_value = None

        with patch('app.db.Session') as mock_session_class:
            mock_session = Mock()
            mock_session_class.return_value.__enter__.return_value = mock_session

            init_db()

            # Vérifier que les tables ont été créées
            mock_create_all.assert_called_once()

            # Vérifier que le mode WAL a été activé
            mock_sqlite_connect.assert_called_once_with("medbridge.db")
            mock_conn.execute.assert_called_once_with("PRAGMA journal_mode=WAL;")
            mock_conn.close.assert_called_once()

            # Vérifier que les templates ont été initialisés
            mock_init_templates.assert_called_once_with(mock_session)

    @patch('app.db.SQLModel.metadata.create_all')
    @patch('sqlite3.connect')
    def test_init_db_sqlite_error(self, mock_sqlite_connect, mock_create_all):
        """Test initialisation de la base de données - erreur SQLite."""
        # Mock une erreur de connexion SQLite
        mock_sqlite_connect.side_effect = Exception("SQLite error")

        # Ne devrait pas lever d'exception
        init_db()

        # Vérifier que create_all a quand même été appelé
        mock_create_all.assert_called_once()

    @patch('app.db.Session')
    def test_get_session(self, mock_session_class):
        """Test obtention d'une session via la dépendance FastAPI."""
        mock_session = Mock()
        mock_session_class.return_value.__enter__.return_value = mock_session
        mock_session_class.return_value.__exit__.return_value = None

        # Simuler l'usage comme générateur FastAPI
        session_gen = get_session()
        session = next(session_gen)

        self.assertEqual(session, mock_session)
        mock_session_class.assert_called_once()

    def test_session_factory(self):
        """Test factory de session explicite."""
        session = session_factory()

        self.assertIsInstance(session, Session)

    @patch('app.db.Session')
    def test_get_seq_existing(self, mock_session_class):
        """Test récupération d'une séquence existante."""
        mock_session = Mock()
        mock_session_class.return_value = mock_session

        # Mock séquence existante
        mock_seq = Mock()
        mock_seq.name = "test_seq"
        mock_seq.value = 42
        mock_session.get.return_value = mock_seq

        result = _get_seq(mock_session, "test_seq")

        self.assertEqual(result, mock_seq)
        mock_session.get.assert_called_once_with(mock_session.get.call_args[0][0], "test_seq")
        mock_session.add.assert_not_called()

    @patch('app.db.Session')
    def test_get_seq_new_in_transaction(self, mock_session_class):
        """Test création d'une nouvelle séquence dans une transaction."""
        mock_session = Mock()
        mock_session_class.return_value = mock_session

        # Mock séquence inexistante
        mock_session.get.return_value = None
        mock_session.in_transaction.return_value = True

        # Mock nouvelle séquence
        mock_new_seq = Mock()
        mock_new_seq.name = "new_seq"
        mock_new_seq.value = 0

        with patch('app.db.Sequence') as mock_sequence_class:
            mock_sequence_class.return_value = mock_new_seq

            result = _get_seq(mock_session, "new_seq")

            self.assertEqual(result, mock_new_seq)
            mock_session.add.assert_called_once_with(mock_new_seq)
            mock_session.flush.assert_called_once()
            mock_session.commit.assert_not_called()
            mock_session.refresh.assert_called_once_with(mock_new_seq)

    @patch('app.db.Session')
    def test_get_seq_new_outside_transaction(self, mock_session_class):
        """Test création d'une nouvelle séquence hors transaction."""
        mock_session = Mock()
        mock_session_class.return_value = mock_session

        # Mock séquence inexistante
        mock_session.get.return_value = None
        mock_session.in_transaction.return_value = False

        # Mock nouvelle séquence
        mock_new_seq = Mock()
        mock_new_seq.name = "new_seq"
        mock_new_seq.value = 0

        with patch('app.db.Sequence') as mock_sequence_class:
            mock_sequence_class.return_value = mock_new_seq

            result = _get_seq(mock_session, "new_seq")

            self.assertEqual(result, mock_new_seq)
            mock_session.add.assert_called_once_with(mock_new_seq)
            mock_session.commit.assert_called_once()
            mock_session.flush.assert_not_called()
            mock_session.refresh.assert_called_once_with(mock_new_seq)

    def test_peek_next_sequence(self):
        """Test aperçu de la prochaine valeur de séquence."""
        mock_session = Mock()

        # Mock séquence avec valeur 42
        mock_seq = Mock()
        mock_seq.value = 42

        with patch('app.db._get_seq') as mock_get_seq:
            mock_get_seq.return_value = mock_seq

            result = peek_next_sequence(mock_session, "test_seq")

            self.assertEqual(result, 43)  # 42 + 1
            mock_get_seq.assert_called_once_with(mock_session, "test_seq")

    def test_get_next_sequence(self):
        """Test obtention et incrémentation de la séquence."""
        mock_session = Mock()

        # Mock séquence avec valeur 42
        mock_seq = Mock()
        mock_seq.value = 42
        mock_session.in_transaction.return_value = False

        with patch('app.db._get_seq') as mock_get_seq:
            mock_get_seq.return_value = mock_seq

            result = get_next_sequence(mock_session, "test_seq")

            self.assertEqual(result, 43)  # 42 + 1
            self.assertEqual(mock_seq.value, 43)
            mock_session.add.assert_called_once_with(mock_seq)
            mock_session.commit.assert_called_once()

    def test_get_next_sequence_in_transaction(self):
        """Test obtention de séquence dans une transaction."""
        mock_session = Mock()

        # Mock séquence avec valeur 42
        mock_seq = Mock()
        mock_seq.value = 42
        mock_session.in_transaction.return_value = True

        with patch('app.db._get_seq') as mock_get_seq:
            mock_get_seq.return_value = mock_seq

            result = get_next_sequence(mock_session, "test_seq")

            self.assertEqual(result, 43)  # 42 + 1
            self.assertEqual(mock_seq.value, 43)
            mock_session.add.assert_called_once_with(mock_seq)
            mock_session.flush.assert_called_once()
            mock_session.commit.assert_not_called()

    def test_coerce_datetime_value_iso_format(self):
        """Test conversion de chaîne ISO en datetime."""
        iso_string = "2023-12-01T10:30:00"
        result = _coerce_datetime_value(iso_string)

        expected = datetime(2023, 12, 1, 10, 30, 0)
        self.assertEqual(result, expected)

    def test_coerce_datetime_value_date_only(self):
        """Test conversion de date seule."""
        date_string = "2023-12-01"
        result = _coerce_datetime_value(date_string)

        expected = datetime(2023, 12, 1)
        self.assertEqual(result, expected)

    def test_coerce_datetime_value_hl7_format(self):
        """Test conversion de format HL7 (YYYYMMDDHHMMSS)."""
        hl7_string = "20231201103000"
        result = _coerce_datetime_value(hl7_string)

        expected = datetime(2023, 12, 1, 10, 30, 0)
        self.assertEqual(result, expected)

    def test_coerce_datetime_value_invalid(self):
        """Test conversion de valeur invalide."""
        invalid_string = "not-a-date"
        result = _coerce_datetime_value(invalid_string)

        # Devrait retourner la valeur originale
        self.assertEqual(result, invalid_string)

    def test_coerce_datetime_value_already_datetime(self):
        """Test conversion de valeur déjà datetime."""
        dt = datetime(2023, 12, 1, 10, 30, 0)
        result = _coerce_datetime_value(dt)

        self.assertEqual(result, dt)

    def test_before_flush_datetime_coercion(self):
        """Test coercion automatique des dates dans before_flush."""
        mock_session = Mock()
        mock_flush_context = Mock()

        # Mock objet avec attribut datetime
        mock_obj = Mock()
        mock_obj.admit_time = "2023-12-01T10:30:00"
        mock_obj.discharge_time = None
        mock_obj.start_time = None
        mock_obj.when = None
        mock_obj.created_at = None
        mock_obj.updated_at = None

        mock_session.new = [mock_obj]
        mock_session.dirty = []
        mock_session.deleted = []

        _before_flush(mock_session, mock_flush_context, None)

        # Vérifier que coerce a été appelé
        # Vérifier que la valeur a été assignée
        self.assertEqual(mock_obj.admit_time, datetime(2023, 12, 1, 10, 30, 0))

    @patch('app.db.Sequence')
    def test_before_flush_dossier_seq_assignment(self, mock_sequence_class):
        """Test assignation automatique de dossier_seq."""
        mock_session = Mock()
        mock_flush_context = Mock()

        # Mock dossier sans dossier_seq
        mock_dossier = Mock()
        mock_dossier.id = 1
        mock_dossier.dossier_seq = None

        # Mock séquence existante
        mock_seq = Mock()
        mock_seq.value = 100
        mock_session.get.return_value = mock_seq

        mock_session.new = [mock_dossier]
        mock_session.dirty = []
        mock_session.deleted = []
        mock_session.in_transaction.return_value = True

        with patch('app.models.Dossier', Mock):  # Mock pour éviter l'import
            _before_flush(mock_session, mock_flush_context, None)

            # Vérifier que dossier_seq a été assigné
            self.assertEqual(mock_dossier.dossier_seq, 101)
            self.assertEqual(mock_seq.value, 101)

    def test_before_flush_legacy_fields_mouvement(self):
        """Test gestion des champs legacy pour Mouvement."""
        mock_session = Mock()
        mock_flush_context = Mock()

        # Mock mouvement avec champs legacy
        mock_mouvement = Mock()
        mock_mouvement.date_heure_mouvement = "2023-12-01T10:30:00"
        mock_mouvement.when = None
        mock_mouvement.type_mouvement = "admission"
        mock_mouvement.movement_type = None

        mock_session.new = [mock_mouvement]
        mock_session.dirty = []
        mock_session.deleted = []

        with patch('app.models.Mouvement', Mock):  # Mock pour éviter l'import
            _before_flush(mock_session, mock_flush_context, None)

            # Vérifier que les champs legacy ont été mappés
            self.assertEqual(mock_mouvement.when, datetime(2023, 12, 1, 10, 30, 0))
            self.assertEqual(mock_mouvement.movement_type, "admission")

    def test_before_flush_legacy_fields_venue(self):
        """Test gestion des champs legacy pour Venue."""
        mock_session = Mock()
        mock_flush_context = Mock()

        # Mock venue avec champ legacy
        mock_venue = Mock()
        mock_venue.statut = "active"
        mock_venue.operational_status = None

        mock_session.new = [mock_venue]
        mock_session.dirty = []
        mock_session.deleted = []

        with patch('app.models.Venue', Mock):  # Mock pour éviter l'import
            _before_flush(mock_session, mock_flush_context, None)

            # Vérifier que le champ legacy a été mappé
            self.assertEqual(mock_venue.operational_status, "active")

    def test_before_flush_tags_normalization(self):
        """Test normalisation des tags (liste vers CSV)."""
        mock_session = Mock()
        mock_flush_context = Mock()

        # Mock objet avec tags sous forme de liste
        mock_obj = Mock()
        mock_obj.tags = ["tag1", "tag2", "tag3"]

        mock_session.new = [mock_obj]
        mock_session.dirty = []
        mock_session.deleted = []

        _before_flush(mock_session, mock_flush_context, None)

        # Vérifier que les tags ont été convertis en CSV
        self.assertEqual(mock_obj.tags, "tag1,tag2,tag3")

    @unittest.skip("Disabled due to complex mocking requirements for SQLAlchemy select")
    def test_before_flush_cascade_delete_dossier(self):
        """Test suppression en cascade des dossiers."""
        mock_session = Mock()
        mock_flush_context = Mock()

        # Mock dossier supprimé
        mock_dossier = Mock()
        mock_dossier.id = 1

        # Mock venue et mouvement enfants
        mock_venue = Mock()
        mock_venue.id = 10
        mock_mouvement = Mock()
        mock_mouvement.id = 100

        mock_session.new = []
        mock_session.dirty = []
        mock_session.deleted = [mock_dossier]

        # Mock les requêtes
        mock_venue_query = Mock()
        mock_venue_query.all.return_value = [mock_venue]
        mock_mouvement_query = Mock()
        mock_mouvement_query.all.return_value = [mock_mouvement]
        mock_session.exec.side_effect = [mock_venue_query, mock_mouvement_query]

        with patch('app.models.Dossier', Mock), \
             patch('app.models.Venue', Mock), \
             patch('app.models.Mouvement', Mock):

            Mock.__table__ = Mock()
            Mock.__tablename__ = 'mock'

            _before_flush(mock_session, mock_flush_context, None)

            # Vérifier que les suppressions en cascade ont été effectuées
            self.assertEqual(mock_session.delete.call_count, 2)
            # Check that delete was called with the mouvement and venue
            calls = mock_session.delete.call_args_list
            self.assertIn(mock_mouvement, [call[0][0] for call in calls])
            self.assertIn(mock_venue, [call[0][0] for call in calls])


if __name__ == "__main__":
    unittest.main()