"""
Tests unitaires pour l'utilitaire flash messages (app/utils/flash.py).

Cet utilitaire gère les messages flash pour les notifications utilisateur.
"""

import unittest
from unittest.mock import Mock, patch
from datetime import datetime, timezone
from app.utils.flash import flash, FlashLevel


class TestFlashUtility(unittest.TestCase):
    """Tests pour l'utilitaire flash messages."""

    def test_flash_success_message(self):
        """Test ajout d'un message flash de succès."""
        mock_request = Mock()
        mock_session = {}
        mock_request.session = mock_session

        flash(mock_request, "Opération réussie", "success")

        # Vérifier que le message a été ajouté à la session
        self.assertIn("_messages", mock_session)
        messages = mock_session["_messages"]
        self.assertEqual(len(messages), 1)

        message = messages[0]
        self.assertEqual(message["level"], "success")
        self.assertEqual(message["message"], "Opération réussie")
        self.assertIn("id", message)
        self.assertIn("timestamp", message)

    def test_flash_error_message(self):
        """Test ajout d'un message flash d'erreur."""
        mock_request = Mock()
        mock_session = {}
        mock_request.session = mock_session

        flash(mock_request, "Erreur survenue", "error")

        messages = mock_session["_messages"]
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]["level"], "error")
        self.assertEqual(messages[0]["message"], "Erreur survenue")

    def test_flash_default_level(self):
        """Test niveau par défaut (info)."""
        mock_request = Mock()
        mock_session = {}
        mock_request.session = mock_session

        flash(mock_request, "Message info")

        messages = mock_session["_messages"]
        self.assertEqual(messages[0]["level"], "info")

    def test_flash_multiple_messages(self):
        """Test ajout de plusieurs messages flash."""
        mock_request = Mock()
        mock_session = {}
        mock_request.session = mock_session

        flash(mock_request, "Premier message", "info")
        flash(mock_request, "Deuxième message", "warning")
        flash(mock_request, "Troisième message", "error")

        messages = mock_session["_messages"]
        self.assertEqual(len(messages), 3)

        levels = [msg["level"] for msg in messages]
        self.assertEqual(levels, ["info", "warning", "error"])

    def test_flash_preserves_existing_messages(self):
        """Test que les messages existants sont préservés."""
        mock_request = Mock()
        existing_message = {
            "id": "existing123",
            "level": "info",
            "message": "Message existant",
            "timestamp": "2023-01-01T00:00:00"
        }
        mock_session = {"_messages": [existing_message]}
        mock_request.session = mock_session

        flash(mock_request, "Nouveau message", "success")

        messages = mock_session["_messages"]
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0], existing_message)
        self.assertEqual(messages[1]["level"], "success")

    def test_flash_handles_non_list_messages(self):
        """Test gestion quand _messages n'est pas une liste."""
        mock_request = Mock()
        mock_session = {"_messages": "invalid"}  # Pas une liste
        mock_request.session = mock_session

        flash(mock_request, "Message", "info")

        messages = mock_session["_messages"]
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]["level"], "info")

    def test_flash_no_session(self):
        """Test quand la requête n'a pas de session."""
        mock_request = Mock()
        del mock_request.session  # Pas de session

        # Ne devrait pas planter
        flash(mock_request, "Message", "info")

        # Vérifier qu'aucune session n'a été créée
        self.assertFalse(hasattr(mock_request, "session"))

    def test_flash_timestamp_format(self):
        """Test format du timestamp."""
        mock_request = Mock()
        mock_session = {}
        mock_request.session = mock_session

        flash(mock_request, "Test", "info")

        message = mock_session["_messages"][0]
        # Vérifier que le timestamp est présent et ressemble à une date ISO
        self.assertIn("timestamp", message)
        self.assertRegex(message["timestamp"], r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")

    def test_flash_unique_ids(self):
        """Test que les IDs sont uniques."""
        mock_request = Mock()
        mock_session = {}
        mock_request.session = mock_session

        flash(mock_request, "Message 1", "info")
        flash(mock_request, "Message 2", "info")

        messages = mock_session["_messages"]
        self.assertNotEqual(messages[0]["id"], messages[1]["id"])

    def test_flash_all_levels(self):
        """Test tous les niveaux de flash."""
        levels: list[FlashLevel] = ["info", "success", "warning", "error"]

        for level in levels:
            with self.subTest(level=level):
                mock_request = Mock()
                mock_session = {}
                mock_request.session = mock_session

                flash(mock_request, f"Message {level}", level)

                messages = mock_session["_messages"]
                self.assertEqual(len(messages), 1)
                self.assertEqual(messages[0]["level"], level)


if __name__ == '__main__':
    unittest.main()