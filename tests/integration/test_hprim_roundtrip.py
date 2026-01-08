# tests/test_hprim_roundtrip.py
"""
Tests roundtrip pour les messages HPRIM XML
Validation que génération -> XML -> parsing -> validation préserve l'intégrité
"""

import pytest
from datetime import datetime
from decimal import Decimal
import sys
import os

# Ajouter le répertoire parent au path pour les imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Importer seulement les modules nécessaires sans charger FastAPI
from app.hprim_models import (
    HprimMessage, HprimEnteteMessage, HprimPatient, HprimProfessionnel,
    HprimActeNGAP, HprimActeCCAM, HprimModificateur, HprimMontant,
    HprimMessageType, HprimAction
)
from app.services.hprim.hprim_service import HprimService


@pytest.fixture
def hprim_service():
    """Fixture pour le service HPRIM"""
    return HprimService()


@pytest.fixture
def sample_patient():
    """Patient de test HPRIM"""
    return HprimPatient(
        identifiant_id="PAT123456",
        identifiant_clef="CLEF123",
        nom="DUPONT",
        prenom="Jean",
        date_naissance="1980-05-15",  # Format string pour HPRIM
        sexe="M"
    )


@pytest.fixture
def sample_professionnel():
    """Professionnel de test HPRIM"""
    return HprimProfessionnel(
        nom="MARTIN",
        prenom="Marie",
        numero_rpps="12345678901",
        numero_adeli="9A7654321",  # Format valide: 9 caractères
        specialite="Médecin généraliste"
    )


@pytest.fixture
def sample_acte_ngap(sample_professionnel):
    """Acte NGAP de test"""
    return HprimActeNGAP(
        identifiant="NGAP_TEST_001",
        lettre_cle="A",
        coefficient=1.5,
        execute_date=datetime(2025, 12, 20, 10, 30),
        denombrement=1,
        position_dentaire="11",
        execute_heure="10:30:00",
        numero_seance=1,
        nabms=[1111, 2222],
        minor_major="Majeur",
        montant=HprimMontant(valeur=25.50, devise="EUR"),
        commentaire="Test acte NGAP",
        prestataire=sample_professionnel,
        action=HprimAction.CREATION
    )


@pytest.fixture
def sample_acte_ccam(sample_professionnel):
    """Acte CCAM de test"""
    return HprimActeCCAM(
        identifiant="CCAM_TEST_001",
        code_acte="AAAA001",
        code_activite="01",
        code_phase="01",
        execute_date=datetime(2025, 12, 20, 10, 30),
        execute_heure="10:30:00",
        modificateurs=[
            HprimModificateur(code="A", statut="nft"),
            HprimModificateur(code="B", statut="nft")
        ],
        quantite=2,
        montant=HprimMontant(valeur=Decimal("150.50"), devise="EUR"),
        commentaire="Test acte CCAM",
        executant=sample_professionnel,
        action=HprimAction.CREATION
    )


class TestHprimRoundtrip:
    """Tests de roundtrip génération XML -> parsing -> validation"""

    def test_ngap_message_roundtrip(self, hprim_service, sample_patient, sample_professionnel, sample_acte_ngap):
        """Test roundtrip complet pour message NGAP"""
        # Créer le message
        message = HprimMessage(
            entete=HprimEnteteMessage(
                emetteur_id="123456789",
                emetteur_nom="Hôpital Test",
                destinataire_id="987654321",
                destinataire_nom="Destinataire Test",
                date_emission=datetime(2025, 12, 20, 10, 0),
                message_id="MSG_NGAP_TEST_001",
                message_type=HprimMessageType.EVENEMENTS_SERVEUR_ACTES
            ),
            patient=sample_patient,
            acteur=sample_professionnel,
            actes_ngap=[sample_acte_ngap]
        )

        # Valider le message original
        erreurs_original = hprim_service.valider_message(message)
        assert len(erreurs_original) == 0, f"Erreurs validation originale: {erreurs_original}"

        # Générer le XML
        xml_content = hprim_service.generer_xml(message, valider=False)
        assert xml_content is not None
        assert len(xml_content) > 0
        assert isinstance(xml_content, str)

        # Parser le XML
        message_parse = hprim_service.xml_service.parse_xml(xml_content)
        assert message_parse is not None

        # Valider le message parsé
        erreurs_parse = hprim_service.valider_message(message_parse)
        assert len(erreurs_parse) == 0, f"Erreurs validation parsée: {erreurs_parse}"

        # Vérifier l'intégrité des données
        self._compare_messages(message, message_parse)

    def test_ccam_message_roundtrip(self, hprim_service, sample_patient, sample_professionnel, sample_acte_ccam):
        """Test roundtrip complet pour message CCAM"""
        # Créer le message
        message = HprimMessage(
            entete=HprimEnteteMessage(
                emetteur_id="123456789",
                emetteur_nom="Hôpital Test",
                destinataire_id="987654321",
                destinataire_nom="Destinataire Test",
                date_emission=datetime(2025, 12, 20, 10, 0),
                message_id="MSG_CCAM_TEST_001",
                message_type=HprimMessageType.EVENEMENTS_SERVEUR_ACTES
            ),
            patient=sample_patient,
            acteur=sample_professionnel,
            actes_ccam=[sample_acte_ccam]
        )

        # Valider le message original
        erreurs_original = hprim_service.valider_message(message)
        assert len(erreurs_original) == 0, f"Erreurs validation originale: {erreurs_original}"

        # Générer le XML
        xml_content = hprim_service.generer_xml(message)

        # Vérifier que le XML est valide
        assert xml_content is not None
        assert len(xml_content) > 0
        assert "evenementsServeurActes" in xml_content

        # Parser le XML
        message_parse = hprim_service.xml_service.parse_xml(xml_content)
        assert message_parse is not None

        # Valider le message parsé
        erreurs_parse = hprim_service.valider_message(message_parse)
        assert len(erreurs_parse) == 0, f"Erreurs validation parsée: {erreurs_parse}"

        # Vérifier l'intégrité des données
        self._compare_messages(message, message_parse)

    def test_xml_encoding_preservation(self, hprim_service, sample_patient, sample_professionnel, sample_acte_ngap):
        """Test que l'encodage ISO-8859-1 est préservé"""
        message = HprimMessage(
            entete=HprimEnteteMessage(
                emetteur_id="123456789",
                emetteur_nom="Hôpital Test",
                destinataire_id="987654321",
                destinataire_nom="Destinataire Test",
                date_emission=datetime(2025, 12, 20, 10, 0),
                message_id="MSG_ENCODING_TEST_001",
                message_type=HprimMessageType.EVENEMENTS_SERVEUR_ACTES
            ),
            patient=sample_patient,
            acteur=sample_professionnel,
            actes_ngap=[sample_acte_ngap]
        )

        # Générer XML
        xml_content = hprim_service.generer_xml(message, valider=False)

        # Vérifier l'encodage dans le header XML
        assert '<?xml version="1.0" encoding="ISO-8859-1"?>' in xml_content

        # Parser et vérifier que ça fonctionne
        message_parse = hprim_service.xml_service.parse_xml(xml_content)
        assert message_parse is not None

    def test_validation_error_preservation(self, hprim_service, sample_patient, sample_professionnel):
        """Test que les erreurs de validation sont correctement détectées après roundtrip"""
        # Créer un acte NGAP invalide (lettre-clé invalide)
        acte_invalide = HprimActeNGAP(
            identifiant="NGAP_INVALID_001",
            lettre_cle="9",  # Invalide, doit être A-Z
            coefficient=1.5,
            execute_date=datetime(2025, 12, 20, 10, 30),
            prestataire=sample_professionnel,
            action=HprimAction.CREATION
        )

        message = HprimMessage(
            entete=HprimEnteteMessage(
                emetteur_id="123456789",
                emetteur_nom="Hôpital Test",
                destinataire_id="987654321",
                destinataire_nom="Destinataire Test",
                date_emission=datetime(2025, 12, 20, 10, 0),
                message_id="MSG_INVALID_001",
                message_type=HprimMessageType.EVENEMENTS_SERVEUR_ACTES
            ),
            patient=sample_patient,
            acteur=sample_professionnel,
            actes_ngap=[acte_invalide]
        )

        # Valider l'original - doit avoir des erreurs
        erreurs_original = hprim_service.valider_message(message)
        assert len(erreurs_original) > 0

        # Générer quand même le XML (valider=False)
        xml_content = hprim_service.generer_xml(message, valider=False)

        # Parser
        message_parse = hprim_service.xml_service.parse_xml(xml_content)

        # Debug: vérifier que les actes sont parsés
        print(f"Original actes_ngap: {len(message.actes_ngap)}")
        print(f"Parsed actes_ngap: {len(message_parse.actes_ngap)}")
        if message_parse.actes_ngap:
            print(f"Parsed lettre_cle: {message_parse.actes_ngap[0].lettre_cle}")

        # Valider le parsé - doit avoir au moins l'erreur de lettre-clé
        erreurs_parse = hprim_service.valider_message(message_parse)
        print(f"Erreurs parse: {[e.code for e in erreurs_parse]}")
        assert len(erreurs_parse) >= 1  # Au moins l'erreur de lettre-clé

        # Vérifier que l'erreur spécifique est préservée
        erreurs_codes = [e.code for e in erreurs_parse]
        assert "NGAP_CLE_001" in erreurs_codes

        # Vérifier que l'erreur spécifique est préservée
        erreurs_codes = [e.code for e in erreurs_parse]
        assert "NGAP_CLE_001" in erreurs_codes

        # Vérifier que les données patient/professionnel sont correctement parsées
        assert message_parse.patient.identifiant_id == sample_patient.identifiant_id
        assert message_parse.patient.nom == sample_patient.nom
        assert message_parse.patient.prenom == sample_patient.prenom
        assert message_parse.acteur.nom == sample_professionnel.nom
        assert message_parse.acteur.numero_rpps == sample_professionnel.numero_rpps

    def _compare_messages(self, original, parsed):
        """Compare deux messages pour vérifier l'intégrité des données"""
        # En-tête
        assert original.entete.emetteur_id == parsed.entete.emetteur_id
        assert original.entete.emetteur_nom == parsed.entete.emetteur_nom
        assert original.entete.destinataire_id == parsed.entete.destinataire_id
        assert original.entete.destinataire_nom == parsed.entete.destinataire_nom
        assert original.entete.message_id == parsed.entete.message_id
        assert original.entete.message_type == parsed.entete.message_type

        # Patient
        assert original.patient.identifiant_id == parsed.patient.identifiant_id
        assert original.patient.nom == parsed.patient.nom
        assert original.patient.prenom == parsed.patient.prenom
        assert original.patient.sexe == parsed.patient.sexe

        # Acteur
        assert original.acteur.nom == parsed.acteur.nom
        assert original.acteur.prenom == parsed.acteur.prenom
        assert original.acteur.numero_rpps == parsed.acteur.numero_rpps

        # Actes NGAP
        if original.actes_ngap and parsed.actes_ngap:
            assert len(original.actes_ngap) == len(parsed.actes_ngap)
            for orig_acte, parsed_acte in zip(original.actes_ngap, parsed.actes_ngap):
                assert orig_acte.lettre_cle == parsed_acte.lettre_cle
                assert orig_acte.coefficient == parsed_acte.coefficient
                assert orig_acte.execute_date == parsed_acte.execute_date
                assert orig_acte.montant == parsed_acte.montant
                assert orig_acte.commentaire == parsed_acte.commentaire
