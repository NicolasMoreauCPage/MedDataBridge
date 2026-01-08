from app.services.scenario_identity_generator import (
    apply_patient_identity_to_hl7,
    generate_patient_identity,
)


def _get_pid_segment(message: str) -> str:
    for line in message.replace('\r', '\n').split('\n'):
        if line.startswith('PID|'):
            return line
    raise AssertionError('PID segment missing')


def test_generate_identity_is_deterministic_with_seed():
    identity_a = generate_patient_identity(seed=42)
    identity_b = generate_patient_identity(seed=42)

    assert identity_a == identity_b
    assert identity_a.family
    assert identity_a.given
    assert identity_a.birth_date.isoformat().startswith('19') or identity_a.birth_date.isoformat().startswith('20')


def test_apply_identity_to_hl7_overrides_core_pid_fields():
    identity = generate_patient_identity(seed=13)
    hl7_message = (
        "MSH|^~\\&|SRC|FAC|DST|FAC|202401011200||ADT^A04|MSG0001|P|2.5\r"
        "PID|1||123456^^^HOSP^PI||DOE^JOHN||19700101|M|||12 rue Test^^Paris^IDF^75001^FRA||0102030405~0611223344|0304050607|S|"\
        "|||FRANCE|PARIS|U|||FRA|F||\r"
        "PV1|1|I|||||^^^^^|\r"
    )

    updated = apply_patient_identity_to_hl7(hl7_message, identity)
    pid_segment = _get_pid_segment(updated)
    fields = pid_segment.split('|')

    assert identity.family in fields[5]
    assert identity.given in fields[5]
    assert fields[7] == identity.birth_date.strftime('%Y%m%d')
    assert fields[8] == identity.gender
    assert identity.city in fields[11]
    assert identity.phone in fields[13]
    assert identity.nir == fields[19]
    assert identity.nationality == fields[28]
    assert identity.identity_reliability_code == fields[32]
