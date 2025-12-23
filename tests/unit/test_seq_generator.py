"""
Tests unitaires pour le générateur de séquences (app/utils/seq_generator.py).

Ce module génère des identifiants uniques basés sur timestamp pour Patient, Dossier et Venue.
"""

import unittest
from unittest.mock import patch
import time
from app.utils.seq_generator import (
    generate_patient_seq,
    generate_dossier_seq,
    generate_venue_seq
)


class TestSequenceGenerator(unittest.TestCase):
    """Tests pour le générateur de séquences."""

    def setUp(self):
        """Réinitialiser les compteurs avant chaque test."""
        # Remettre les compteurs à zéro pour des tests déterministes
        import app.utils.seq_generator as seq_mod
        seq_mod._patient_counter = 0
        seq_mod._dossier_counter = 0
        seq_mod._venue_counter = 0
        seq_mod._last_patient_timestamp = 0
        seq_mod._last_dossier_timestamp = 0
        seq_mod._last_venue_timestamp = 0

    @patch('app.utils.seq_generator.time.time')
    def test_generate_patient_seq_format(self, mock_time):
        """Test format de l'identifiant patient."""
        mock_time.return_value = 1735173512.345678  # timestamp fixe

        seq = generate_patient_seq()

        # Vérifier le format
        seq_str = str(seq)
        self.assertEqual(len(seq_str), 12, "L'identifiant patient doit faire 12 chiffres")
        self.assertEqual(seq_str[0], '9', "L'identifiant patient doit commencer par '9'")
        self.assertTrue(900000000000 <= seq < 1000000000000, "L'identifiant patient doit être dans la plage 9xxxxxxxxxxx")

    @patch('app.utils.seq_generator.time.time')
    def test_generate_patient_seq_uniqueness(self, mock_time):
        """Test unicité des identifiants patients."""
        mock_time.return_value = 1735173512.345678

        seq1 = generate_patient_seq()
        seq2 = generate_patient_seq()

        self.assertNotEqual(seq1, seq2, "Deux identifiants patients doivent être différents")

    @patch('app.utils.seq_generator.time.time')
    def test_generate_patient_seq_counter_increment(self, mock_time):
        """Test incrémentation du compteur pour même timestamp."""
        # Simuler même timestamp
        mock_time.return_value = 1735173512.345678

        seq1 = generate_patient_seq()
        seq2 = generate_patient_seq()
        seq3 = generate_patient_seq()

        # Les deux derniers chiffres doivent être différents (compteur)
        self.assertNotEqual(str(seq1)[-1], str(seq2)[-1])
        self.assertNotEqual(str(seq2)[-1], str(seq3)[-1])

    @patch('app.utils.seq_generator.time.time')
    def test_generate_dossier_seq_format(self, mock_time):
        """Test format de l'identifiant dossier."""
        mock_time.return_value = 1735173512.345678

        seq = generate_dossier_seq()

        seq_str = str(seq)
        self.assertEqual(len(seq_str), 9, "L'identifiant dossier doit faire 9 chiffres")
        self.assertEqual(seq_str[0], '9', "L'identifiant dossier doit commencer par '9'")
        self.assertTrue(900000000 <= seq < 1000000000, "L'identifiant dossier doit être dans la plage 9xxxxxxxx")

    @patch('app.utils.seq_generator.time.time')
    def test_generate_dossier_seq_uniqueness(self, mock_time):
        """Test unicité des identifiants dossiers."""
        mock_time.return_value = 1735173512.345678

        seq1 = generate_dossier_seq()
        seq2 = generate_dossier_seq()

        self.assertNotEqual(seq1, seq2, "Deux identifiants dossiers doivent être différents")

    @patch('app.utils.seq_generator.time.time')
    def test_generate_venue_seq_format(self, mock_time):
        """Test format de l'identifiant venue."""
        mock_time.return_value = 1735173512.345678

        seq = generate_venue_seq()

        seq_str = str(seq)
        self.assertEqual(len(seq_str), 10, "L'identifiant venue doit faire 10 chiffres")
        self.assertEqual(seq_str[0], '8', "L'identifiant venue doit commencer par '8'")
        self.assertTrue(8000000000 <= seq < 9000000000, "L'identifiant venue doit être dans la plage 8xxxxxxxxx")

    @patch('app.utils.seq_generator.time.time')
    def test_generate_venue_seq_uniqueness(self, mock_time):
        """Test unicité des identifiants venues."""
        mock_time.return_value = 1735173512.345678

        seq1 = generate_venue_seq()
        seq2 = generate_venue_seq()

        self.assertNotEqual(seq1, seq2, "Deux identifiants venues doivent être différents")

    @patch('app.utils.seq_generator.time.time')
    def test_generate_venue_seq_counter_increment(self, mock_time):
        """Test incrémentation du compteur pour même timestamp."""
        mock_time.return_value = 1735173512.345678

        seq1 = generate_venue_seq()
        seq2 = generate_venue_seq()

        # Les derniers chiffres doivent être différents (compteur)
        self.assertNotEqual(str(seq1)[-1], str(seq2)[-1])

    @patch('app.utils.seq_generator.time.time')
    def test_thread_safety_simulation(self, mock_time):
        """Test simulation de sécurité thread (basique)."""
        mock_time.return_value = 1735173512.345678

        # Générer plusieurs séquences rapidement (mais pas plus de 10 pour éviter reset du compteur)
        sequences = [generate_patient_seq() for _ in range(10)]

        # Vérifier qu'ils sont tous uniques
        self.assertEqual(len(sequences), len(set(sequences)), "Toutes les séquences doivent être uniques")

    @patch('app.utils.seq_generator.time.time')
    def test_different_types_have_different_prefixes(self, mock_time):
        """Test que les différents types ont des préfixes différents."""
        mock_time.return_value = 1735173512.345678

        patient_seq = generate_patient_seq()
        dossier_seq = generate_dossier_seq()
        venue_seq = generate_venue_seq()

        self.assertEqual(str(patient_seq)[0], '9')
        self.assertEqual(str(dossier_seq)[0], '9')
        self.assertEqual(str(venue_seq)[0], '8')

        # Patient et dossier commencent par 9 mais ont des longueurs différentes
        self.assertEqual(len(str(patient_seq)), 12)
        self.assertEqual(len(str(dossier_seq)), 9)
        self.assertEqual(len(str(venue_seq)), 10)

    @patch('app.utils.seq_generator.time.time')
    def test_counter_reset_on_new_timestamp(self, mock_time):
        """Test que le compteur se remet à zéro avec un nouveau timestamp."""
        # Premier appel
        mock_time.return_value = 1735173512.345678
        seq1 = generate_patient_seq()

        # Simuler un nouveau timestamp
        mock_time.return_value = 1735173512.345679
        seq2 = generate_patient_seq()

        # Le compteur devrait être remis à zéro, donc dernier chiffre = 0
        self.assertEqual(str(seq2)[-1], '0')


if __name__ == '__main__':
    unittest.main()