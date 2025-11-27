#!/usr/bin/env python3
"""
Test negative case: ZBE-1 without namespace should fail validation.

This test creates a raw HL7 message with ZBE-1 containing only the movement ID
(no namespace components) and confirms that the validator raises ZBE1_NAMESPACE_MISSING error.
"""

import sys
from app.services.pam_validation import validate_pam


def test_zbe1_without_namespace():
    """Test that ZBE-1 without namespace is rejected by validator."""
    
    print("=" * 80)
    print("TEST: ZBE-1 Namespace Validation (Negative Case)")
    print("=" * 80)
    print()
    
    # Create a minimal HL7 message with ZBE-1 containing only ID (no namespace)
    hl7_message = (
        "MSH|^~\\&|POC|HOSP|EXT|HOSP|20251114152752||ADT^A05^ADT_A01|4001|P|2.5^FRA^2.11|||||FRA|8859/1\r"
        "EVN|A05|20251114152752\r"
        "PID|1||1^^^HOSP^PI||Dupont^Jean||1965-01-15|M\r"
        "PV1|1|I||||||||||||||||3001^^^HOSP^VN|||||||||||||||||||URG||||||20251114152752\r"
        "ZBE|4001|20251114152752||INSERT|N||URG^^^^^^^^^URG||H"
    )
    
    print("Generated HL7 Message (with ZBE-1 WITHOUT namespace):")
    print("-" * 80)
    for idx, segment in enumerate(hl7_message.split("\r"), 1):
        print(f"  {idx:2d}. {segment}")
    print("-" * 80)
    print()
    
    # Extract ZBE segment for detailed inspection
    zbe_segment = None
    for segment in hl7_message.split("\r"):
        if segment.startswith("ZBE|"):
            zbe_segment = segment
            break
    
    if zbe_segment:
        print("ZBE Segment Details:")
        print(f"  Full segment: {zbe_segment}")
        parts = zbe_segment.split("|")
        print(f"  ZBE-1 (Movement ID): {parts[1] if len(parts) > 1 else '(empty)'}")
        if len(parts) > 1:
            zbe1_comps = parts[1].split("^")
            print(f"    - Component 1 (ID):          {zbe1_comps[0] if len(zbe1_comps) > 0 else '(empty)'}")
            print(f"    - Component 2 (Namespace):   {zbe1_comps[1] if len(zbe1_comps) > 1 else '(empty)'}")
            print(f"    - Component 3 (OID):         {zbe1_comps[2] if len(zbe1_comps) > 2 else '(empty)'}")
            print(f"    - Component 4 (System):      {zbe1_comps[3] if len(zbe1_comps) > 3 else '(empty)'}")
        print()
    
    # Validate the message
    print("PAM Validation Results:")
    print("-" * 80)
    validation_result = validate_pam(hl7_message, direction="out")
    
    print(f"  Is Valid:      {validation_result.is_valid}")
    print(f"  Level:         {validation_result.level}")
    print(f"  Event:         {validation_result.event}")
    print(f"  Message Type:  {validation_result.message_type}")
    print()
    
    if validation_result.issues:
        print(f"  Issues ({len(validation_result.issues)}):")
        zbe1_namespace_found = False
        for issue in validation_result.issues:
            severity_marker = {
                "error": "❌",
                "warn": "⚠️ ",
                "info": "ℹ️ "
            }.get(issue.severity, "  ")
            print(f"    {severity_marker} [{issue.severity.upper()}] {issue.code}")
            print(f"       {issue.message}")
            if issue.code == "ZBE1_NAMESPACE_MISSING":
                zbe1_namespace_found = True
    else:
        print("  Issues: None")
    
    print()
    print("=" * 80)
    print("Test Result:")
    
    # Success: message should be INVALID (not is_valid) and should contain ZBE1_NAMESPACE_MISSING error
    has_zbe1_error = any(
        issue.code == "ZBE1_NAMESPACE_MISSING" 
        for issue in validation_result.issues
    )
    
    if not validation_result.is_valid and has_zbe1_error:
        print("✓ Negative test PASSED: Validator correctly rejects ZBE-1 without namespace!")
        result = True
    else:
        print("✗ Negative test FAILED: Validator should reject ZBE-1 without namespace")
        result = False
    
    print("=" * 80)
    
    return result


if __name__ == "__main__":
    try:
        success = test_zbe1_without_namespace()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Test failed with exception:")
        print(f"  {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(2)
