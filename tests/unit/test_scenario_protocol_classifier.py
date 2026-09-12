from app.services.scenario_protocol_classifier import classify_hl7_scenario, is_siu_message


def test_recognizes_siu_from_msh_9_and_legacy_trigger_code():
    assert is_siu_message("SIU^S12")
    assert is_siu_message("S15")
    assert is_siu_message(None, "MSH|^~\\&|SRC|DST|A|B|202609120900||SIU^S13^SIU_S12|1|P|2.5")


def test_classifies_pure_siu_and_mixed_adt_siu_scenarios():
    assert classify_hl7_scenario([{"message_format": "hl7", "message_type": "S12"}]) == "siu"
    assert classify_hl7_scenario([
        {"message_format": "hl7", "message_type": "A01"},
        {"message_format": "hl7", "message_type": "SIU^S12"},
    ]) == "mixed_siu"
    assert classify_hl7_scenario([{"message_format": "hl7", "message_type": "A01"}]) is None
