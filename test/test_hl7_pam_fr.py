import pytest
from adapters.hl7_pam_fr import build_message_for_movement

class Dummy:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

def test_build_message_minimal():
    patient = Dummy(identifier="12345", family="DUPONT", given="JEAN", birth_date="19800101", gender="M", identity_reliability_code="VALI")
    venue = Dummy(patient_class="I", code="CHU-A", hospital_service="CARDIO", visit_number="VN123", uf_medicale="UF1", uf_soins="UF2")
    dossier = Dummy(uf_responsabilite="UF1")
    movement = Dummy(type="A01", mouvement_seq="M123", nature="HMS")
    msg = build_message_for_movement(dossier=dossier, venue=venue, movement=movement, patient=patient)
    assert "MSH|^~\\&|POC|POC|DST|DST|" in msg
    assert "EVN|A01" in msg
    assert "PID|1||12345||DUPONT^JEAN" in msg
    assert "PV1||I|CHU-A" in msg
    assert "ZBE|M123" in msg
    assert "VALI" in msg  # PID-32

def test_build_message_with_mrg_nk1_pd1():
    patient = Dummy(identifier="54321", family="MARTIN", given="ANNE", birth_date="19900202", gender="F", identity_reliability_code="PROV", contact_name="MARTIN PERE", contact_relationship="FATHER", contact_address="1 rue X", contact_phone="0102030405", lifestyle="SPORT", data_protection="OUI")
    venue = Dummy(patient_class="I", code="CHU-B", hospital_service="NEURO", visit_number="VN456", uf_medicale="UF3", uf_soins="UF4")
    dossier = Dummy(uf_responsabilite="UF3")
    movement = Dummy(type="A40", mouvement_seq="M456", nature="HMS", merge_identifiers="OLDID", previous_name="MARTIN-OLD")
    msg = build_message_for_movement(dossier=dossier, venue=venue, movement=movement, patient=patient)
    assert "MRG|OLDID" in msg
    assert "NK1|1|MARTIN PERE|FATHER|1 rue X|0102030405" in msg
    assert "PD1" in msg
    assert "PROV" in msg  # PID-32
