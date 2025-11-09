"""Tests des validateurs HL7."""
import pytest
from app.validators.hl7_validators import PAMValidator, MFNValidator

def test_pam_validator_required_segments():
    """Test la validation des segments obligatoires PAM."""
    validator = PAMValidator()
    
    # Message minimal valide
    message = "\r".join([
        "MSH|^~\\&|SIH|CH|PAM|CH|20251109101500||ADT^A01|123|P|2.5||",
        "PID|1||123^^^IPP||DOE^John||",
        "PV1|1||CARDIO||||||||||||||||||||VN123|||"
    ])
    
    result = validator.validate_message(message)
    assert result.is_valid
    assert not result.errors
    
    # Message avec segment manquant
    message = "\r".join([
        "MSH|^~\\&|SIH|CH|PAM|CH|20251109101500||ADT^A01|123|P|2.5||",
        "PID|1||123^^^IPP||DOE^John||"
    ])
    
    result = validator.validate_message(message)
    assert not result.is_valid
    assert len(result.errors) == 1
    assert "PV1" in result.errors[0].message

def test_pam_validator_pid_validation():
    """Test la validation du segment PID."""
    validator = PAMValidator()
    
    # PID valide avec nom et prénom
    pid = "PID|1||123^^^IPP||DOE^John||"
    result = validator.validate_pid_segment(pid, 1)
    assert not validator.errors
    
    # PID sans IPP
    validator = PAMValidator()
    pid = "PID|1||||DOE^John||"
    result = validator.validate_pid_segment(pid, 1)
    assert len(validator.errors) == 1
    assert "IPP" in validator.errors[0].message
    
    # PID sans nom
    validator = PAMValidator()
    pid = "PID|1||123^^^IPP||||"
    result = validator.validate_pid_segment(pid, 1)
    assert len(validator.errors) == 1
    assert "Nom" in validator.errors[0].message
    
    # PID avec nom mais sans prénom
    validator = PAMValidator()
    pid = "PID|1||123^^^IPP||DOE||"
    result = validator.validate_pid_segment(pid, 1)
    assert len(validator.warnings) == 1
    assert "Prénom" in validator.warnings[0].message

def test_pam_validator_pv1_validation():
    """Test la validation du segment PV1."""
    validator = PAMValidator()
    
    # PV1 valide
    pv1 = "PV1|1||CARDIO||||||||||||||||||||VN123|||"
    result = validator.validate_pv1_segment(pv1, 1)
    assert not validator.errors
    
    # PV1 sans numéro de venue
    validator = PAMValidator()
    pv1 = "PV1|1||CARDIO|||||||||||||||||||||||"
    result = validator.validate_pv1_segment(pv1, 1)
    assert len(validator.errors) == 1
    assert "venue" in validator.errors[0].message
    
    # PV1 sans UF
    validator = PAMValidator()
    pv1 = "PV1|1||||||||||||||||||||||VN123|||"
    result = validator.validate_pv1_segment(pv1, 1)
    assert len(validator.warnings) == 1
    assert "UF" in validator.warnings[0].message

def test_pam_validator_zbe_validation():
    """Test la validation du segment ZBE."""
    validator = PAMValidator()
    
    # ZBE valide
    zbe = "ZBE|ADMIT|||||20251109101500||"
    result = validator.validate_zbe_segment(zbe, 1)
    assert not validator.errors
    
    # ZBE sans code mouvement
    validator = PAMValidator()
    zbe = "ZBE||||||20251109101500||"
    result = validator.validate_zbe_segment(zbe, 1)
    assert len(validator.errors) == 1
    assert "mouvement" in validator.errors[0].message
    
    # ZBE avec code mouvement invalide
    validator = PAMValidator()
    zbe = "ZBE|INVALID|||||20251109101500||"
    result = validator.validate_zbe_segment(zbe, 1)
    assert len(validator.warnings) == 1
    assert "inconnu" in validator.warnings[0].message
    
    # ZBE avec date invalide
    validator = PAMValidator()
    zbe = "ZBE|ADMIT|||||INVALID_DATE||"
    result = validator.validate_zbe_segment(zbe, 1)
    assert len(validator.errors) == 1
    assert "date" in validator.errors[0].message

def test_mfn_validator_required_segments():
    """Test la validation des segments obligatoires MFN."""
    validator = MFNValidator()
    
    # Message minimal valide
    message = "\r".join([
        "MSH|^~\\&|SIH|CH|PAM|CH|20251109101500||MFN^M05|123|P|2.5||",
        "MFI|LOC|MF|TEST|||UPD|"
    ])
    
    result = validator.validate_message(message)
    assert result.is_valid
    assert not result.errors
    
    # Message avec segment manquant
    message = "\r".join([
        "MSH|^~\\&|SIH|CH|PAM|CH|20251109101500||MFN^M05|123|P|2.5||"
    ])
    
    result = validator.validate_message(message)
    assert not result.is_valid
    assert len(result.errors) == 1
    assert "MFI" in result.errors[0].message

def test_mfn_validator_loc_validation():
    """Test la validation du segment LOC."""
    validator = MFNValidator()
    
    # LOC valide
    loc = "LOC|123|1|ETBL_GRPQ|Test Hospital|"
    result = validator.validate_loc_segment(loc, 1)
    assert not validator.errors
    assert result == "ETBL_GRPQ"
    
    # LOC sans identifiant
    validator = MFNValidator()
    loc = "LOC||1|ETBL_GRPQ|Test Hospital|"
    result = validator.validate_loc_segment(loc, 1)
    assert len(validator.errors) == 1
    assert "Identifiant" in validator.errors[0].message
    assert result is None
    
    # LOC avec type invalide
    validator = MFNValidator()
    loc = "LOC|123|1|INVALID|Test Hospital|"
    result = validator.validate_loc_segment(loc, 1)
    assert len(validator.errors) == 1
    assert "Type" in validator.errors[0].message
    assert "invalide" in validator.errors[0].message
    assert result is None

def test_mfn_validator_lch_validation():
    """Test la validation du segment LCH."""
    validator = MFNValidator()
    
    # LCH valide avec LOC parent
    loc = "LOC|123|1|ETBL_GRPQ|Test Hospital|"
    current_loc = validator.validate_loc_segment(loc, 1)
    
    lch = "LCH|1|1|LBL^Label|^Test Label|"
    validator.validate_lch_segment(lch, 2, current_loc)
    assert not validator.errors
    
    # LCH sans LOC parent
    validator = MFNValidator()
    lch = "LCH|1|1|LBL^Label|^Test Label|"
    validator.validate_lch_segment(lch, 1, None)
    assert len(validator.errors) == 1
    assert "sans LOC parent" in validator.errors[0].message
    
    # LCH avec code attribut mal formaté
    validator = MFNValidator()
    loc = "LOC|123|1|ETBL_GRPQ|Test Hospital|"
    current_loc = validator.validate_loc_segment(loc, 1)
    
    lch = "LCH|1|1|LBL|^Test Label|"
    validator.validate_lch_segment(lch, 2, current_loc)
    assert len(validator.warnings) == 1
    assert "mal formaté" in validator.warnings[0].message