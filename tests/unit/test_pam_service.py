"""Tests pour le service PAM (Patient Administration Management).

Ce module teste les fonctionnalités de traitement des messages HL7 PAM,
la validation des timings de mouvements, et la génération de messages PAM.
"""

import pytest
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch
from sqlmodel import Session, select

from app.services.pam import (
    validate_movement_timing,
    process_pam_message,
    generate_pam_messages_for_dossier,
    _extract_pv1_segment,
    _parse_zbe_segment
)
from app.models import Dossier, Patient, Venue, Mouvement
from app.models_structure import EntiteJuridique


class TestPAMService:
    """Tests pour le service PAM."""

    def test_validate_movement_timing_success(self, session: Session):
        """Test validation timing mouvement - succès (écart > 1 min)."""
        # Créer une venue de test
        ej = EntiteJuridique(id=1, nom="Test EJ", finess="123456789")
        patient = Patient(
            id=2,
            family="Doe",
            given="John",
            birth_date=datetime(1990, 1, 1).date()
        )
        dossier = Dossier(
            id=2,
            dossier_seq=int(uuid.uuid4().hex[:8], 16) % 1000000,
            patient_id=2,
            admit_time=datetime(2024, 1, 1, 10, 0),  # naive datetime
            entite_juridique_id=1
        )
        venue = Venue(
            id=2,
            venue_seq=int(uuid.uuid4().hex[:8], 16) % 1000000,
            code="TEST001",
            dossier_id=2,
            entite_juridique_id=1,
            start_time=datetime(2024, 1, 1, 10, 0)  # naive datetime
        )

        session.add(ej)
        session.add(patient)
        session.add(dossier)
        session.add(venue)

        # Créer un mouvement existant il y a 5 minutes
        existing_movement = Mouvement(
            id=2,
            mouvement_seq=int(uuid.uuid4().hex[:8], 16) % 1000000,
            venue_id=2,
            entite_juridique_id=1,
            when=datetime(2024, 1, 1, 9, 55),  # naive datetime
            trigger_event="A01"
        )
        session.add(existing_movement)
        session.commit()

        # Tester avec un nouveau mouvement 10 minutes plus tard (devrait réussir)
        new_datetime = datetime(2024, 1, 1, 10, 5)  # naive datetime
        validate_movement_timing(session, venue.id, new_datetime)

    def test_validate_movement_timing_too_close(self, session: Session):
        """Test validation timing mouvement - échec (écart < 1 min)."""
        # Créer une venue de test
        ej = EntiteJuridique(id=1, nom="Test EJ", finess="123456789")
        patient = Patient(
            id=3,
            family="Doe",
            given="John",
            birth_date=datetime(1990, 1, 1).date()
        )
        dossier = Dossier(
            id=3,
            dossier_seq=int(uuid.uuid4().hex[:8], 16) % 1000000,
            patient_id=3,
            admit_time=datetime(2024, 1, 1, 10, 0),  # naive datetime
            entite_juridique_id=1
        )
        venue = Venue(
            id=3,
            venue_seq=int(uuid.uuid4().hex[:8], 16) % 1000000,
            code="TEST002",
            dossier_id=3,
            entite_juridique_id=1,
            start_time=datetime(2024, 1, 1, 10, 0)  # naive datetime
        )

        session.add(ej)
        session.add(patient)
        session.add(dossier)
        session.add(venue)

        # Créer un mouvement existant
        existing_movement = Mouvement(
            id=3,
            mouvement_seq=int(uuid.uuid4().hex[:8], 16) % 1000000,
            venue_id=3,
            entite_juridique_id=1,
            when=datetime(2024, 1, 1, 10, 0),  # naive datetime
            trigger_event="A01"
        )
        session.add(existing_movement)
        session.commit()

        # Tester avec un nouveau mouvement 30 secondes plus tard (devrait échouer)
        new_datetime = datetime(2024, 1, 1, 10, 0, 30)  # naive datetime

        with pytest.raises(ValueError, match="au moins 1 minute"):
            validate_movement_timing(session, venue.id, new_datetime)

    def test_extract_pv1_segment_found(self):
        """Test extraction segment PV1 - trouvé."""
        message = """MSH|^~\\&|APP|FAC|DEST|DEST|20240101120000||ADT^A01|123|P|2.5
PID|1||123456^^^MPI||DOE^JOHN||19900101|M
PV1|1|I|WARD^ROOM^BEDSIDE||||DR^HOUSE|||SUR||||ADM|||20240101120000
ZBE|1|20240101120000|||INSERT|N|||WARD|MED"""

        result = _extract_pv1_segment(message)
        assert result == "PV1|1|I|WARD^ROOM^BEDSIDE||||DR^HOUSE|||SUR||||ADM|||20240101120000"

    def test_extract_pv1_segment_not_found(self):
        """Test extraction segment PV1 - non trouvé."""
        message = """MSH|^~\\&|APP|FAC|DEST|DEST|20240101120000||ADT^A01|123|P|2.5
PID|1||123456^^^MPI||DOE^JOHN||19900101|M"""

        result = _extract_pv1_segment(message)
        assert result is None

    def test_parse_zbe_segment_valid(self):
        """Test parsing segment ZBE - valide."""
        zbe_line = "ZBE|1|20240101120000||INSERT|N||||WARD|MED"

        result = _parse_zbe_segment(zbe_line)
        expected = {
            'movement_id': '1',
            'movement_datetime': '20240101120000',
            'action_type': 'INSERT',
            'cancel_flag': 'N',
            'origin_event': None,
            'uf_responsable': None,
            'mode_traitement': None,
            'nature': 'WARD'
        }
        assert result == expected

    def test_parse_zbe_segment_invalid(self):
        """Test parsing segment ZBE - invalide."""
        zbe_line = "INVALID|DATA"

        result = _parse_zbe_segment(zbe_line)
        assert result is None

    @patch('app.services.pam.extract_and_store_medecin_from_pv1')
    @patch('app.services.pam.create_identifiers_from_hl7_with_namespace_check')
    def test_process_pam_message_adt_a01(self, mock_identifiers, mock_medecin, session: Session):
        """Test traitement message PAM ADT^A01."""
        # Créer les données de test
        ej = EntiteJuridique(id=1, nom="Test EJ", finess="123456789")
        patient = Patient(
            id=4,
            family="DOE",
            given="JOHN",
            birth_date=datetime(1990, 1, 1).date()
        )
        session.add(ej)
        session.add(patient)
        session.commit()

        # Message ADT^A01 valide
        message = """MSH|^~\\&|APP|FAC|DEST|DEST|20240101120000||ADT^A01|123|P|2.5
PID|1||123456^^^MPI||DOE^JOHN||19900101|M
PV1|1|I|WARD^ROOM^BEDSIDE||||DR^HOUSE|||SUR||||ADM|||20240101120000
ZBE|1|20240101120000|||INSERT|N|||CARDIO|MED"""

        # Mock des dépendances
        mock_identifiers.return_value = []
        mock_medecin.return_value = None

        result = process_pam_message(session, message)

        # Vérifications - fonction retourne parsing basique sans création d'entités
        assert result['trigger'] == 'ADT^A01'
        assert result['patient_identifier'] == '123456'
        assert result['patient_name']['family'] == 'DOE'
        assert result['patient_name']['given'] == 'JOHN'
        assert result['venue_location'] == 'WARD^ROOM^BEDSIDE'
        assert result['segments']['MSH'] is True
        assert result['segments']['PID'] is True
        assert result['segments']['PV1'] is True

    def test_process_pam_message_invalid_format(self, session: Session):
        """Test traitement message PAM - format invalide."""
        message = "INVALID MESSAGE FORMAT"

        with pytest.raises(ValueError, match="Message HL7 invalide"):
            process_pam_message(session, message)

    def test_generate_pam_messages_for_dossier(self, session: Session):
        """Test génération messages PAM pour un dossier."""
        # Créer les données de test
        ej = EntiteJuridique(id=1, nom="Test EJ", finess="123456789")
        patient = Patient(
            id=5,
            family="DOE",
            given="JOHN",
            birth_date=datetime(1990, 1, 1).date()
        )
        dossier = Dossier(
            id=5,
            dossier_seq=int(uuid.uuid4().hex[:8], 16) % 1000000,
            patient_id=5,
            admit_time=datetime(2024, 1, 1, 10, 0),  # naive datetime
            entite_juridique_id=1
        )
        venue = Venue(
            id=5,
            venue_seq=int(uuid.uuid4().hex[:8], 16) % 1000000,
            code="TEST001",
            dossier_id=5,
            entite_juridique_id=1,
            start_time=datetime(2024, 1, 1, 10, 0)  # naive datetime
        )
        mouvement = Mouvement(
            id=5,
            mouvement_seq=int(uuid.uuid4().hex[:8], 16) % 1000000,
            venue_id=5,
            entite_juridique_id=1,
            when=datetime(2024, 1, 1, 10, 0),  # naive datetime
            trigger_event="A01"
        )

        session.add(ej)
        session.add(patient)
        session.add(dossier)
        session.add(venue)
        session.add(mouvement)
        session.commit()

        # Tester la génération (nécessite l'adaptateur HL7 PAM FR)
        messages = generate_pam_messages_for_dossier(dossier)

        # Si l'adaptateur n'est pas disponible, la liste devrait être vide
        assert isinstance(messages, list)

    def test_process_pam_message_missing_patient(self, session: Session):
        """Test traitement message PAM - patient manquant."""
        # Créer l'EJ mais pas le patient
        ej = EntiteJuridique(id=1, nom="Test EJ", finess="123456789")
        session.add(ej)
        session.commit()

        message = """MSH|^~\\&|APP|FAC|DEST|DEST|20240101120000||ADT^A01|123|P|2.5
PID|1||999999^^^MPI||DOE^JOHN||19900101|M
PV1|1|I|WARD^ROOM^BEDSIDE||||DR^HOUSE|||SUR||||ADM|||20240101120000"""

        result = process_pam_message(session, message)

        # Fonction ne crée pas d'entités, juste parsing
        assert result['trigger'] == 'ADT^A01'
        assert result['patient_identifier'] == '999999'
        assert result['patient_name']['family'] == 'DOE'
        assert result['patient_name']['given'] == 'JOHN'
