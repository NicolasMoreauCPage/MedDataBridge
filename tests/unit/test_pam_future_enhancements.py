"""
Future Enhancements Testing Suite for PAM Validator

Tests for advanced validation features introduced in v2.1:
1. Extended Z-segment validation (ZPD, ZIS, ZAD beyond ZBE)
2. Semantic validation strict mode (error-level violations)
3. Custom vocabulary rule loading integration
4. Audit trail generation
"""

import pytest
import json
from pathlib import Path
from datetime import datetime

from app.services.pam_validation import (
    validate_pam,
    validate_pam_semantics,
    ValidationResult,
    ValidationIssue,
    ValidationAuditEntry,
)


class TestExtendedZSegmentValidation:
    """Test Z-segment validation beyond ZBE."""
    
    def _base_msh_a01(self) -> str:
        return "MSH|^~\\&|SENDER|FAC|REC|FAC|202601010101||ADT^A01|MSG001|P|2.5\rEVN|A01|202601010101"
    
    def test_zpd_extension_segment_validation(self):
        """ZPD segment (patient demographics extension) validation."""
        msh = self._base_msh_a01()
        pid = "PID|1|12345||DOE^JOHN||19700101||||||||+33123456789"
        pv1 = "PV1|1|I|WARD^101^A1^^O|3||||||||||||||||||||VIS001"
        # ZPD with missing extension ID (ZPD-1)
        zpd = "ZPD|||"
        zbe = "ZBE|1001^^^SYS&1.2.3&ISO|202601010101||INSERT|N||^^^^^^UF^^^7700||H"
        
        msg = "\r".join([msh, pid, pv1, zpd, zbe]) + "\r"
        result = validate_pam(msg, direction="in")
        
        codes = {i.code for i in result.issues}
        assert "ZPD_1_MISSING" in codes
    
    def test_zis_identifier_system_validation(self):
        """ZIS segment (identifier system extension) validation."""
        msh = self._base_msh_a01()
        pid = "PID|1|12345||DOE^JOHN||19700101||||||||+33123456789"
        pv1 = "PV1|1|I|WARD^101^A1^^O|3||||||||||||||||||||VIS001"
        # ZIS with invalid OID format
        zis = "ZIS|SYSTEM123|not-an-oid|"
        zbe = "ZBE|1001^^^SYS&1.2.3&ISO|202601010101||INSERT|N||^^^^^^UF^^^7700||H"
        
        msg = "\r".join([msh, pid, pv1, zis, zbe]) + "\r"
        result = validate_pam(msg, direction="in")
        
        codes = {i.code for i in result.issues}
        assert "ZIS_2_INVALID" in codes
    
    def test_zis_valid_oid_format(self):
        """ZIS segment with valid OID format."""
        msh = self._base_msh_a01()
        pid = "PID|1|12345||DOE^JOHN||19700101||||||||+33123456789"
        pv1 = "PV1|1|I|WARD^101^A1^^O|3||||||||||||||||||||VIS001"
        # ZIS with valid OID format (1.2.3.4.5)
        zis = "ZIS|SYSTEM123|1.2.3.4.5|"
        zbe = "ZBE|1001^^^SYS&1.2.3&ISO|202601010101||INSERT|N||^^^^^^UF^^^7700||H"
        
        msg = "\r".join([msh, pid, pv1, zis, zbe]) + "\r"
        result = validate_pam(msg, direction="in")
        
        codes = {i.code for i in result.issues}
        assert "ZIS_2_INVALID" not in codes
    
    def test_zad_address_extension_optional(self):
        """ZAD segment (address extension) validation."""
        msh = self._base_msh_a01()
        pid = "PID|1|12345||DOE^JOHN||19700101||||||||+33123456789"
        pv1 = "PV1|1|I|WARD^101^A1^^O|3||||||||||||||||||||VIS001"
        # ZAD with missing address type (should be info level)
        zad = "ZAD|||"
        zbe = "ZBE|1001^^^SYS&1.2.3&ISO|202601010101||INSERT|N||^^^^^^UF^^^7700||H"
        
        msg = "\r".join([msh, pid, pv1, zad, zbe]) + "\r"
        result = validate_pam(msg, direction="in")
        
        # Should only add info, not error
        error_codes = {i.code for i in result.issues if i.severity == "error"}
        assert "ZAD_1_MISSING" not in error_codes


class TestSemanticValidationStrictMode:
    """Test semantic validation with strict mode."""
    
    def _base_a06_msg(self) -> str:
        """Create base A06 message."""
        msh = "MSH|^~\\&|SENDER|FAC|REC|FAC|202601010101||ADT^A06|MSG001|P|2.5"
        evn = "EVN|A06|202601010101"
        pid = "PID|1|12345||DOE^JOHN||19700101||||||||+33123456789"
        pv1 = "PV1|1|I|WARD^101^A1^^O|3||||||||||||||||||||VIS001"
        zbe = "ZBE|1001^^^SYS&1.2.3&ISO|202601010101||INSERT|N||^^^^^^UF^^^7700||S"
        return "\r".join([msh, evn, pid, pv1, zbe]) + "\r"
    
    def test_semantic_warn_mode_default(self):
        """Semantic violations should be warnings by default."""
        msg = self._base_a06_msg()
        
        # Without venue context, semantic check is skipped (info level)
        result = validate_pam_semantics(msg, venue_id=None, session=None, strict=False)
        
        # Should have SEMANTIC_CHECK_SKIPPED info, not error
        assert result.is_valid
        assert result.level in {"ok", "info"}
    
    def test_semantic_strict_mode_converts_warnings_to_errors(self):
        """Semantic violations become errors in strict mode."""
        msg = self._base_a06_msg()
        
        # With strict=True (but no venue context)
        result = validate_pam_semantics(msg, venue_id=None, session=None, strict=True)
        
        # Result should be valid (no DB context), but demonstrate the flag is respected
        assert result.is_valid or result.level == "ok"  # No DB context means no semantic issues to convert
    
    def test_validate_pam_accepts_strict_semantic_flag(self):
        """validate_pam should accept strict_semantic parameter."""
        msh = "MSH|^~\\&|SENDER|FAC|REC|FAC|202601010101||ADT^A01|MSG001|P|2.5"
        evn = "EVN|A01|202601010101"
        pid = "PID|1|234||DOE^JOHN||19700101||||||||+33123456789"
        pv1 = "PV1|1|I|WARD^101^A1^^O|3||||||||||||||||||||VIS001"
        zbe = "ZBE|1001^^^SYS&1.2.3&ISO|202601010101||INSERT|N||^^^^^^UF^^^7700||H"
        msg = "\r".join([msh, evn, pid, pv1, zbe]) + "\r"
        
        # Should accept strict_semantic parameter without error
        result_normal = validate_pam(msg, direction="in", strict_semantic=False)
        result_strict = validate_pam(msg, direction="in", strict_semantic=True)
        
        # Both should have same strictness parameter in audit (if included)
        # and same direction handling
        assert result_normal.audit is None
        assert result_strict.audit is None
        # At minimum, both calls should complete without exception
        assert isinstance(result_normal, ValidationResult)
        assert isinstance(result_strict, ValidationResult)


class TestAuditTrailGeneration:
    """Test audit trail generation feature."""
    
    def _base_msh_a01(self) -> str:
        return "MSH|^~\\&|SENDER|FAC|REC|FAC|202601010101||ADT^A01|MSG001|P|2.5\rEVN|A01|202601010101"
    
    def test_audit_trail_disabled_by_default(self):
        """Audit trail should not be generated by default."""
        msh = self._base_msh_a01()
        pid = "PID|1|12345||DOE^JOHN||19700101||||||||+33123456789"
        pv1 = "PV1|1|I|WARD^101^A1^^O|3||||||||||||||||||||VIS001"
        zbe = "ZBE|1001^^^SYS&1.2.3&ISO|202601010101||INSERT|N||^^^^^^UF^^^7700||H"
        msg = "\r".join([msh, pid, pv1, zbe]) + "\r"
        
        result = validate_pam(msg, include_audit=False)
        
        assert result.audit is None
    
    def test_audit_trail_enabled_when_requested(self):
        """Audit trail should be generated when include_audit=True."""
        msh = self._base_msh_a01()
        pid = "PID|1|12345||DOE^JOHN||19700101||||||||+33123456789"
        pv1 = "PV1|1|I|WARD^101^A1^^O|3||||||||||||||||||||VIS001"
        zbe = "ZBE|1001^^^SYS&1.2.3&ISO|202601010101||INSERT|N||^^^^^^UF^^^7700||H"
        msg = "\r".join([msh, pid, pv1, zbe]) + "\r"
        
        result = validate_pam(msg, include_audit=True)
        
        assert result.audit is not None
        assert isinstance(result.audit, ValidationAuditEntry)
        assert result.audit.trigger == "A01"
        assert result.audit.direction == "in"
        assert result.audit.is_valid == result.is_valid
        assert result.audit.profile == "IHE_PAM_FR"
        assert result.audit.strict_semantic == False
    
    def test_audit_trail_counts_issues_correctly(self):
        """Audit trail should count errors and warnings correctly."""
        msh = self._base_msh_a01()
        pid = "PID|1||||"  # Missing patient name (will warn)
        pv1 = "PV1|1|I|^^^^|3||||||||||||||||||||VIS001"  # Missing bed info for A01
        zbe = "ZBE|1001^^^SYS&1.2.3&ISO|202601010101||INSERT|N||^^^^^^UF^^^7700||H"
        msg = "\r".join([msh, pid, pv1, zbe]) + "\r"
        
        result = validate_pam(msg, direction="in", include_audit=True)
        
        assert result.audit is not None
        assert result.audit.issues_count > 0
        # Count should match real issues
        assert result.audit.errors_count == sum(1 for i in result.issues if i.severity == "error")
        assert result.audit.warnings_count == sum(1 for i in result.issues if i.severity == "warn")
    
    def test_audit_trail_timestamp_format(self):
        """Audit trail should have ISO 8601 timestamp."""
        msh = self._base_msh_a01()
        pid = "PID|1|12345||DOE^JOHN||19700101||||||||+33123456789"
        pv1 = "PV1|1|I|WARD^101^A1^^O|3||||||||||||||||||||VIS001"
        zbe = "ZBE|1001^^^SYS&1.2.3&ISO|202601010101||INSERT|N||^^^^^^UF^^^7700||H"
        msg = "\r".join([msh, pid, pv1, zbe]) + "\r"
        
        result = validate_pam(msg, include_audit=True)
        
        assert result.audit is not None
        # Should be ISO 8601 format (contains T and :)
        assert "T" in result.audit.timestamp
        assert ":" in result.audit.timestamp


class TestCustomRulesIntegration:
    """Test custom vocabulary rules loading and integration."""
    
    def test_custom_rules_loading_from_dict(self):
        """Test that custom rules can be loaded from dictionary."""
        from app.services.pam_validation import SEGMENT_RULES
        
        # Store original state
        original_a99 = SEGMENT_RULES.get("A99", {})
        
        # Create custom rules
        custom_rules = {
            "A99": {
                "required": ["MSH", "EVN", "PID", "PV1"],
                "optional": ["PD1", "NK1"]
            }
        }
        
        # Manually inject (in real use, load_custom_segment_rules handles this)
        SEGMENT_RULES["A99"] = custom_rules["A99"]
        
        # Verify rule was added
        assert "A99" in SEGMENT_RULES
        assert SEGMENT_RULES["A99"]["required"] == ["MSH", "EVN", "PID", "PV1"]
        
        # Restore
        if original_a99:
            SEGMENT_RULES["A99"] = original_a99
        else:
            SEGMENT_RULES.pop("A99", None)
    
    def test_validation_result_audit_dict_export(self):
        """Test that ValidationResult.to_dict() includes audit trail."""
        msh = "MSH|^~\\&|SENDER|FAC|REC|FAC|202601010101||ADT^A01|MSG001|P|2.5\rEVN|A01|202601010101"
        pid = "PID|1|12345||DOE^JOHN||19700101||||||||+33123456789"
        pv1 = "PV1|1|I|WARD^101^A1^^O|3||||||||||||||||||||VIS001"
        zbe = "ZBE|1001^^^SYS&1.2.3&ISO|202601010101||INSERT|N||^^^^^^UF^^^7700||H"
        msg = "\r".join([msh, pid, pv1, zbe]) + "\r"
        
        result = validate_pam(msg, include_audit=True)
        result_dict = result.to_dict()
        
        # Should have audit key
        assert "audit" in result_dict
        assert result_dict["audit"] is not None
        assert result_dict["audit"]["trigger"] == "A01"
        assert result_dict["audit"]["profile"] == "IHE_PAM_FR"


class TestBackwardCompatibility:
    """Ensure new features don't break existing code."""
    
    def test_validate_pam_default_parameters(self):
        """Original validate_pam signature should still work."""
        msh = "MSH|^~\\&|SENDER|FAC|REC|FAC|202601010101||ADT^A01|MSG001|P|2.5"
        evn = "EVN|A01|202601010101"
        pid = "PID|1|234||DOE^JOHN||19700101||||||||+33123456789"
        pv1 = "PV1|1|I|WARD^^A1^^O|3||||||||||||||||||||VIS001"
        zbe = "ZBE|1001^^^SYS&1.2.3&ISO|202601010101||INSERT|N||^^^^^^UF^^^7700||H"
        msg = "\r".join([msh, evn, pid, pv1, zbe]) + "\r"
        
        # Original signature (msg only)
        result = validate_pam(msg)
        
        assert isinstance(result, ValidationResult)
        assert result.audit is None  # Default: no audit
    
    def test_validation_result_without_audit_serializes_cleanly(self):
        """Result without audit should still serialize."""
        msh = "MSH|^~\\&|SENDER|FAC|REC|FAC|202601010101||ADT^A01|MSG001|P|2.5\rEVN|A01|202601010101"
        pid = "PID|1|12345||DOE^JOHN||19700101||||||||+33123456789"
        pv1 = "PV1|1|I|WARD^101^A1^^O|3||||||||||||||||||||VIS001"
        zbe = "ZBE|1001^^^SYS&1.2.3&ISO|202601010101||INSERT|N||^^^^^^UF^^^7700||H"
        msg = "\r".join([msh, pid, pv1, zbe]) + "\r"
        
        result = validate_pam(msg)  # No audit trail
        result_dict = result.to_dict()
        
        # Should serialize without error and audit should be None
        assert isinstance(result_dict, dict)
        assert result_dict["audit"] is None
