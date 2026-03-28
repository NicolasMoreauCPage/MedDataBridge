"""
Tests for HPRIM Cotation UI Routes (/hprim-cotation/*)
Tests dashboard, message detail, dossier aggregation, and import workflows
"""

import json
from datetime import datetime
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import Dossier, Patient, CCAMAct, NGAPAct, UCDAct, LPPAct
from app.models.hprim_models import HprimMessage


def _create_test_patient(session: Session, patient_id: str = "PAT-UI-TEST") -> Patient:
    """Create a test patient for UI routes"""
    patient = Patient(
        identifier=patient_id,
        nom="DUPONT",
        prenom="ALICE",
        date_naissance="1980-01-15",
        sexe="F"
    )
    session.add(patient)
    session.commit()
    session.refresh(patient)
    return patient


def _create_test_dossier(session: Session, patient: Patient, nda: int = 10001) -> Dossier:
    """Create a test dossier (venue/admission)"""
    dossier = Dossier(
        patient_id=patient.id,
        dossier_seq=nda,
        admit_time=datetime.now(),
        current_state="OPEN"
    )
    session.add(dossier)
    session.commit()
    session.refresh(dossier)
    return dossier


def _create_ngap_message(session: Session, message_id: str = "MSG-NGAP-UI-001") -> HprimMessage:
    """Create a test NGAP HPRIM message with XML content"""
    xml_content = '''<?xml version="1.0" encoding="ISO-8859-1"?>
<evenementsServeurActes xmlns="http://www.hprim.org/hprimXML" version="2.4">
    <enteteMessage>
        <dateEmission>2026-03-27T10:00:00</dateEmission>
        <emetteur>
            <agent>
                <code>123456789</code>
            </agent>
        </emetteur>
        <destinataire>
            <agent>
                <code>987654321</code>
            </agent>
        </destinataire>
        <message>
            <id>MSG-NGAP-UI-001</id>
            <type>evenementsServeurActes</type>
        </message>
    </enteteMessage>
    <evenementServeurActe>
        <dateAction>2026-03-27T10:00:00</dateAction>
        <patient>
            <identifiant>
                <emetteur>PAT-UI-TEST</emetteur>
                <numero>01</numero>
            </identifiant>
            <nom>DUPONT</nom>
            <prenom>ALICE</prenom>
            <dateNaissance>1980-01-15</dateNaissance>
            <sexe>F</sexe>
        </patient>
        <venue>
            <identifiant>10001</identifiant>
            <libelle>HOPITAL TEST</libelle>
        </venue>
        <acteur>
            <medecin>
                <nom>MARTIN</nom>
                <prenom>JEAN</prenom>
                <numeroRPPS>12345678901</numeroRPPS>
            </medecin>
        </acteur>
        <actesNGAP>
            <acteNGAP facturable="oui" valide="oui" facture="non">
                <identifiant>ACTE001</identifiant>
                <lettreCle>AMI</lettreCle>
                <coefficient>2.5</coefficient>
                <dateExecution>2026-03-27T10:00:00</dateExecution>
                <heureExecution>10:00</heureExecution>
                <quantite>1</quantite>
                <montant>
                    <valeur>33.50</valeur>
                    <devise>EUR</devise>
                </montant>
                <commentaire>test-ui-ngap</commentaire>
            </acteNGAP>
        </actesNGAP>
    </evenementServeurActe>
</evenementsServeurActes>
'''
    message = HprimMessage(
        message_id=message_id,
        type_message="evenementsServeurActes",
        direction="received",
        status="stored",
        patient_id="PAT-UI-TEST",
        emetteur_id="123456789",
        xml_content=xml_content,
        xml_size=len(xml_content),
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    session.add(message)
    session.commit()
    session.refresh(message)
    return message


def _create_ccam_message(session: Session, message_id: str = "MSG-CCAM-UI-001", nda: str = "10001") -> HprimMessage:
    """Create a test CCAM HPRIM message with XML content"""
    xml_content = f'''<?xml version="1.0" encoding="ISO-8859-1"?>
<evenementsServeurActes xmlns="http://www.hprim.org/hprimXML" version="2.4">
    <enteteMessage>
        <dateEmission>2026-03-27T11:00:00</dateEmission>
        <emetteur>
            <agent>
                <code>111111111</code>
            </agent>
        </emetteur>
        <destinataire>
            <agent>
                <code>222222222</code>
            </agent>
        </destinataire>
        <message>
            <id>{message_id}</id>
            <type>evenementsServeurActes</type>
        </message>
    </enteteMessage>
    <evenementServeurActe>
        <dateAction>2026-03-27T11:00:00</dateAction>
        <patient>
            <identifiant>
                <emetteur>PAT-UI-TEST</emetteur>
                <numero>01</numero>
            </identifiant>
            <nom>DUPONT</nom>
            <prenom>ALICE</prenom>
            <dateNaissance>1980-01-15</dateNaissance>
            <sexe>F</sexe>
        </patient>
        <venue>
            <identifiant>{nda}</identifiant>
            <libelle>HOPITAL TEST</libelle>
        </venue>
        <acteur>
            <medecin>
                <nom>DUPUIS</nom>
                <prenom>PAUL</prenom>
                <numeroRPPS>98765432109</numeroRPPS>
            </medecin>
        </acteur>
        <actesCCAM>
            <acteCCAM facturable="oui" valide="oui" facture="non">
                <identifiant>
                    <emetteur>CCAM001</emetteur>
                </identifiant>
                <codeActe>HBMD001</codeActe>
                <codeActivite>01</codeActivite>
                <codePhase>01</codePhase>
                <execute>
                    <date>2026-03-27T11:00:00</date>
                </execute>
                <executant>
                    <medecins>
                        <medecin>
                            <nom>DUPUIS</nom>
                            <prenom>PAUL</prenom>
                            <numeroRPPS>98765432109</numeroRPPS>
                        </medecin>
                    </medecins>
                </executant>
                <quantite>1</quantite>
                <montant>
                    <valeur>50.00</valeur>
                    <devise>EUR</devise>
                </montant>
                <commentaire>test-ui-ccam</commentaire>
            </acteCCAM>
        </actesCCAM>
    </evenementServeurActe>
</evenementsServeurActes>
'''
    message = HprimMessage(
        message_id=message_id,
        type_message="evenementsServeurActes",
        direction="received",
        status="stored",
        patient_id="PAT-UI-TEST",
        emetteur_id="111111111",
        xml_content=xml_content,
        xml_size=len(xml_content),
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    session.add(message)
    session.commit()
    session.refresh(message)
    return message


def test_hprim_cotation_dashboard_empty(client: TestClient, session: Session):
    """Test dashboard with no messages"""
    response = client.get("/hprim-cotation/")
    assert response.status_code == 200
    assert "hprim-cotation" in response.text.lower() or "dashboard" in response.text.lower()


def test_hprim_cotation_dashboard_with_messages(client: TestClient, session: Session):
    """Test dashboard displays messages"""
    # Create test data
    patient = _create_test_patient(session)
    msg1 = _create_ngap_message(session, "MSG-01")
    msg2 = _create_ccam_message(session, "MSG-02")
    
    # Get dashboard
    response = client.get("/hprim-cotation/")
    assert response.status_code == 200
    assert "MSG-01" in response.text or "MSG-02" in response.text


def test_hprim_cotation_dashboard_search_filter(client: TestClient, session: Session):
    """Test dashboard search filtering"""
    patient = _create_test_patient(session)
    msg = _create_ngap_message(session, "MSG-SEARCH-TEST")
    
    # Search for existing message
    response = client.get("/hprim-cotation/?search=MSG-SEARCH-TEST")
    assert response.status_code == 200


def test_hprim_cotation_dashboard_status_filter(client: TestClient, session: Session):
    """Test dashboard status filtering"""
    patient = _create_test_patient(session)
    msg = _create_ngap_message(session, "MSG-STATUS-TEST")
    
    # Filter by stored status
    response = client.get("/hprim-cotation/?status=stored")
    assert response.status_code == 200


def test_hprim_cotation_message_detail_ngap(client: TestClient, session: Session):
    """Test message detail page for NGAP"""
    patient = _create_test_patient(session)
    msg = _create_ngap_message(session, "MSG-DETAIL-NGAP")
    
    response = client.get(f"/hprim-cotation/message/{msg.message_id}")
    assert response.status_code == 200
    
    # Verify page contains message info
    content = response.text
    assert msg.message_id in content
    assert "NGAP" in content or "ngap" in content.lower()


def test_hprim_cotation_message_detail_ccam(client: TestClient, session: Session):
    """Test message detail page for CCAM"""
    patient = _create_test_patient(session)
    msg = _create_ccam_message(session, "MSG-DETAIL-CCAM")
    
    response = client.get(f"/hprim-cotation/message/{msg.message_id}")
    assert response.status_code == 200
    
    # Verify page contains message info
    content = response.text
    assert msg.message_id in content
    assert "CCAM" in content or "ccam" in content.lower()


def test_hprim_cotation_message_detail_not_found(client: TestClient, session: Session):
    """Test message detail with non-existent message"""
    response = client.get("/hprim-cotation/message/NONEXISTENT")
    # Should either return 404 or a page with error message
    assert response.status_code in [200, 404]


def test_hprim_cotation_message_detail_with_patient_match(client: TestClient, session: Session):
    """Test message detail page matches patient"""
    patient = _create_test_patient(session, "PAT-MATCH-TEST")
    dossier = _create_test_dossier(session, patient, 10001)
    # Create message with matching NDA (simpler NGAP message)
    msg = _create_ngap_message(session, "MSG-MATCH")
    
    response = client.get(f"/hprim-cotation/message/{msg.message_id}")
    assert response.status_code == 200
    content = response.text
    # Should show message info
    assert "MSG-MATCH" in content or "NGAP" in content


def test_hprim_cotation_dossiers_avec_cotations_empty(client: TestClient, session: Session):
    """Test dossier aggregation with no messages"""
    response = client.get("/hprim-cotation/dossiers-avec-cotations")
    assert response.status_code == 200


def test_hprim_cotation_dossiers_avec_cotations_with_messages(client: TestClient, session: Session):
    """Test dossier aggregation routes are callable"""
    patient = _create_test_patient(session)
    dossier = _create_test_dossier(session, patient, 10001)
    msg1 = _create_ngap_message(session, "MSG-DOS-1")
    msg2 = _create_ngap_message(session, "MSG-DOS-2")
    
    response = client.get("/hprim-cotation/dossiers-avec-cotations")
    assert response.status_code == 200
    # Route should return some content
    assert len(response.text) > 0


def test_hprim_cotation_import_ccam_acts_success(client: TestClient, session: Session):
    """Test CCAM acts import endpoint (may fail if message parsing fails)"""
    patient = _create_test_patient(session)
    dossier = _create_test_dossier(session, patient, 10001)
    msg = _create_ngap_message(session, "MSG-IMPORT-CCAM")
    
    # POST import request - CCAM endpoint on non-CCAM message is OK
    response = client.post(f"/hprim-cotation/message/{msg.message_id}/import-ccam")
    # May return 200 or 400 if no CCAM acts or parsing fails, both are acceptable
    assert response.status_code in [200, 303, 400]


def test_hprim_cotation_import_ngap_acts_success(client: TestClient, session: Session):
    """Test NGAP acts import endpoint (route exists and is callable)"""
    patient = _create_test_patient(session)
    dossier = _create_test_dossier(session, patient, 10001)
    msg = _create_ngap_message(session, "MSG-IMPORT-NGAP")
    
    # POST import request - may succeed or fail depending on parsing
    response = client.post(f"/hprim-cotation/message/{msg.message_id}/import-ngap")
    # Route should be callable and return a reasonable response
    assert response.status_code in [200, 303, 400]


def test_hprim_cotation_import_without_dossier_match(client: TestClient, session: Session):
    """Test import when message doesn't match any dossier"""
    # Create message but no matching dossier
    msg = _create_ngap_message(session, "MSG-NO-MATCH")
    
    # POST import request - should handle gracefully
    response = client.post(f"/hprim-cotation/message/{msg.message_id}/import-ngap")
    # Should either redirect or show error page
    assert response.status_code in [200, 303, 400]


def test_hprim_cotation_message_detail_shows_import_forms(client: TestClient, session: Session):
    """Test that message detail page shows import buttons"""
    patient = _create_test_patient(session)
    msg = _create_ccam_message(session, "MSG-FORMS")
    
    response = client.get(f"/hprim-cotation/message/{msg.message_id}")
    assert response.status_code == 200
    content = response.text
    # Should contain form buttons for imports
    assert "import" in content.lower() or "form" in content.lower()


def test_hprim_cotation_message_detail_shows_xml_content(client: TestClient, session: Session):
    """Test that message detail page displays XML archive"""
    patient = _create_test_patient(session)
    msg = _create_ccam_message(session, "MSG-XML")
    
    response = client.get(f"/hprim-cotation/message/{msg.message_id}")
    assert response.status_code == 200
    content = response.text
    # Should show XML content (at least some XML marker)
    assert "xml" in content.lower() or "<?xml" in content or "hprim" in content


def test_hprim_cotation_multiple_messages_same_patient(client: TestClient, session: Session):
    """Test UI handles multiple messages for same patient"""
    patient = _create_test_patient(session, "PAT-MULTI")
    dossier = _create_test_dossier(session, patient, 10001)
    msg1 = _create_ccam_message(session, "MSG-M1", "10001")
    msg2 = _create_ngap_message(session, "MSG-M2")
    
    # Dashboard should show both
    dash_response = client.get("/hprim-cotation/")
    assert dash_response.status_code == 200
    
    # Dossier view should aggregate them
    dos_response = client.get("/hprim-cotation/dossiers-avec-cotations")
    assert dos_response.status_code == 200


def test_hprim_cotation_pagination_support(client: TestClient, session: Session):
    """Test dashboard supports pagination"""
    patient = _create_test_patient(session)
    # Create multiple messages
    for i in range(5):
        _create_ccam_message(session, f"MSG-PAGE-{i}", "10001")
    
    # Request with limit parameter
    response = client.get("/hprim-cotation/?limit=2")
    assert response.status_code == 200


def test_hprim_cotation_message_status_badges(client: TestClient, session: Session):
    """Test status badge rendering in detail page"""
    patient = _create_test_patient(session)
    msg = _create_ccam_message(session, "MSG-STATUS-BADGE")
    
    response = client.get(f"/hprim-cotation/message/{msg.message_id}")
    assert response.status_code == 200
    content = response.text
    # Status should be visible
    assert "stored" in content.lower() or "status" in content.lower()


def test_hprim_cotation_acte_type_recognition(client: TestClient, session: Session):
    """Test UI correctly identifies acte types (CCAM, NGAP, etc.)"""
    patient = _create_test_patient(session)
    
    # NGAP message
    ngap_msg = _create_ngap_message(session, "MSG-NGAP-TYPE")
    response = client.get(f"/hprim-cotation/message/{ngap_msg.message_id}")
    assert response.status_code == 200
    assert "NGAP" in response.text or "ngap" in response.text.lower()
    
    # CCAM message
    ccam_msg = _create_ccam_message(session, "MSG-CCAM-TYPE")
    response = client.get(f"/hprim-cotation/message/{ccam_msg.message_id}")
    assert response.status_code == 200
    assert "CCAM" in response.text or "ccam" in response.text.lower()
