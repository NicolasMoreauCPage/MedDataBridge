"""Tests d'intégration pour les validateurs HL7."""
import pytest
from app.validators.hl7_validators import PAMValidator, MFNValidator


class TestPAMValidatorIntegration:
    """Tests d'intégration du validateur PAM."""
    
    def test_valid_a01_message(self):
        """Test validation d'un message A01 valide."""
        message = """MSH|^~\\&|SENDING_APP|SENDING_FAC|RECEIVING_APP|RECEIVING_FAC|20230101120000||ADT^A01|MSG0001|P|2.5|||AL||FR
EVN|A01|20230101120000
PID|1||123456^^^FACILITY^PI||DOE^JOHN||19800101|M
PV1|1|I|SERVICE^ROOM^BED^FACILITY||||DOCTOR1^John^Smith|||MED||||||ADMIT||||||||||||||||||||FACILITY|||||2023

0101120000
"""
        validator = PAMValidator(message)
        assert validator.validate()
        assert validator.is_valid
        assert not validator.errors
    
    def test_a01_missing_pv1(self):
        """Test validation A01 sans segment PV1."""
        message = """MSH|^~\\&|SENDING_APP|SENDING_FAC|RECEIVING_APP|RECEIVING_FAC|20230101120000||ADT^A01|MSG0001|P|2.5|||AL||FR
EVN|A01|20230101120000
PID|1||123456^^^FACILITY^PI||DOE^JOHN||19800101|M
"""
        validator = PAMValidator(message)
        assert not validator.validate()
        assert not validator.is_valid
        assert "Segment PV1 obligatoire manquant" in validator.errors
    
    def test_a03_with_discharge_time(self):
        """Test validation A03 avec date de sortie."""
        message = """MSH|^~\\&|SENDING_APP|SENDING_FAC|RECEIVING_APP|RECEIVING_FAC|20230101180000||ADT^A03|MSG0002|P|2.5|||AL||FR
EVN|A03|20230101180000
PID|1||123456^^^FACILITY^PI||DOE^JOHN||19800101|M
PV1|1|I|SERVICE^ROOM^BED^FACILITY||||DOCTOR1^John^Smith|||MED||||||ADMIT||||||||||||||||||||FACILITY|||||2023

0101120000||20230101180000
"""
        validator = PAMValidator(message)
        assert validator.validate()
        assert validator.is_valid
    
    def test_a08_update_patient(self):
        """Test validation A08 mise à jour patient."""
        message = """MSH|^~\\&|SENDING_APP|SENDING_FAC|RECEIVING_APP|RECEIVING_FAC|20230101140000||ADT^A08|MSG0003|P|2.5|||AL||FR
EVN|A08|20230101140000
PID|1||123456^^^FACILITY^PI||DOE^JOHN^WILLIAM||19800101|M|||123 MAIN ST^^CITY^^12345
PV1|1|I|SERVICE^ROOM^BED^FACILITY||||DOCTOR1^John^Smith|||MED||||||ADMIT||||||||||||||||||||FACILITY|||||2023

0101120000
"""
        validator = PAMValidator(message)
        assert validator.validate()
        assert validator.is_valid


class TestMFNValidatorIntegration:
    """Tests d'intégration du validateur MFN."""
    
    def test_valid_m02_message(self):
        """Test validation d'un message M02 valide."""
        message = """MSH|^~\\&|SENDING_APP|SENDING_FAC|RECEIVING_APP|RECEIVING_FAC|20230101120000||MFN^M02|MSG0001|P|2.5|||AL||FR
MFI|LCH^M02^HL70175|UPD|||AL
MFE|MAD|12345|20230101120000|LCH
LCH|1001|PL|CARDIO|20230101120000|20991231235959|A
LCC|1001|L1|BED^Lit
LCD|1001|PL|CARDIO|||||||||20230101120000|20991231235959
"""
        validator = MFNValidator(message)
        assert validator.validate()
        assert validator.is_valid
        assert not validator.errors
    
    def test_m02_missing_lch(self):
        """Test validation M02 sans segment LCH."""
        message = """MSH|^~\\&|SENDING_APP|SENDING_FAC|RECEIVING_APP|RECEIVING_FAC|20230101120000||MFN^M02|MSG0001|P|2.5|||AL||FR
MFI|LCH^M02^HL70175|UPD|||AL
MFE|MAD|12345|20230101120000|LCH
"""
        validator = MFNValidator(message)
        assert not validator.validate()
        assert not validator.is_valid
        assert any("Segment LCH obligatoire manquant" in err for err in validator.errors)
    
    def test_m02_invalid_location_code_format(self):
        """Test validation M02 avec format de code invalide."""
        message = """MSH|^~\\&|SENDING_APP|SENDING_FAC|RECEIVING_APP|RECEIVING_FAC|20230101120000||MFN^M02|MSG0001|P|2.5|||AL||FR
MFI|LCH^M02^HL70175|UPD|||AL
MFE|MAD|12345|20230101120000|LCH
LCH|INVALID CODE|PL|CARDIO|20230101120000|20991231235959|A
"""
        validator = MFNValidator(message)
        validator.validate()
        # Le validateur devrait émettre un avertissement
        assert validator.warnings
    
    def test_m05_bed_update(self):
        """Test validation M05 mise à jour d'un lit."""
        message = """MSH|^~\\&|SENDING_APP|SENDING_FAC|RECEIVING_APP|RECEIVING_FAC|20230101120000||MFN^M05|MSG0002|P|2.5|||AL||FR
MFI|LOC^M05^HL70175|UPD|||AL
MFE|MAD|BED001|20230101120000|LOC
LOC|BED001|BED|Lit 001||^^^^12345|||A|Bed||||||||BED|20230101120000|20991231235959
"""
        validator = MFNValidator(message)
        assert validator.validate()
        assert validator.is_valid


class TestPAMValidatorWithZBE:
    """Tests du validateur PAM avec segments ZBE."""
    
    def test_a01_with_zbe(self):
        """Test validation A01 avec segment ZBE."""
        message = """MSH|^~\\&|SENDING_APP|SENDING_FAC|RECEIVING_APP|RECEIVING_FAC|20230101120000||ADT^A01|MSG0001|P|2.5|||AL||FR
EVN|A01|20230101120000
PID|1||123456^^^FACILITY^PI||DOE^JOHN||19800101|M
PV1|1|I|SERVICE^ROOM^BED^FACILITY||||DOCTOR1^John^Smith|||MED||||||ADMIT||||||||||||||||||||FACILITY|||||2023

0101120000
ZBE|MVT001|20230101120000|ADMIT|UF001
"""
        validator = PAMValidator(message)
        assert validator.validate()
        assert validator.is_valid
    
    def test_a02_transfer_with_zbe(self):
        """Test validation A02 transfert avec ZBE."""
        message = """MSH|^~\\&|SENDING_APP|SENDING_FAC|RECEIVING_APP|RECEIVING_FAC|20230101150000||ADT^A02|MSG0002|P|2.5|||AL||FR
EVN|A02|20230101150000
PID|1||123456^^^FACILITY^PI||DOE^JOHN||19800101|M
PV1|1|I|SERVICE2^ROOM2^BED2^FACILITY||||DOCTOR1^John^Smith|||MED||||||ADMIT||||||||||||||||||||FACILITY|||||2023

0101120000
ZBE|MVT002|20230101150000|TRANSFER|UF002|UF001
"""
        validator = PAMValidator(message)
        assert validator.validate()
        assert validator.is_valid


class TestValidatorErrorHandling:
    """Tests de gestion d'erreurs des validateurs."""
    
    def test_invalid_message_format(self):
        """Test validation avec format de message invalide."""
        message = "This is not a valid HL7 message"
        validator = PAMValidator(message)
        assert not validator.validate()
        assert not validator.is_valid
        assert validator.errors
    
    def test_missing_msh_segment(self):
        """Test validation sans segment MSH."""
        message = """EVN|A01|20230101120000
PID|1||123456^^^FACILITY^PI||DOE^JOHN||19800101|M
"""
        validator = PAMValidator(message)
        assert not validator.validate()
        assert not validator.is_valid
    
    def test_empty_message(self):
        """Test validation avec message vide."""
        validator = PAMValidator("")
        assert not validator.validate()
        assert not validator.is_valid
        assert validator.errors