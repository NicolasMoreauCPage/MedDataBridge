from sqlmodel import Session, SQLModel, create_engine, select

from app.models_appointments import Appointment
from app.services.scenario_validation import validate_scenario
from app.services.siu import integrate_siu, validate_siu


def _message(trigger: str = "S12", appointment_id: str = "RDV-42") -> str:
    return "\r".join([
        f"MSH|^~\\&|SCHED|HOSP|BRIDGE|HOSP|20260912100000||SIU^{trigger}^SIU_{trigger}|CTRL-{trigger}|P|2.5",
        f"SCH|{appointment_id}^^^SCHED|FILLER-{appointment_id}^^^SCHED|||||||||1^MIN^30^20260915100000^20260915103000",
        "PID|1||PAT-1^^^SCHED^PI||DOE^Jane||19900101|F",
        "RGS|1|A",
        "AIS|1|A|CONSULT",
        "AIL|1|A|UF-CARDIO",
        "AIP|1|A|12345678901^CARDIO^Alice",
    ])


def test_siu_validation_is_distinct_from_pam_validation():
    result = validate_siu(_message())
    assert result.is_valid
    assert result.message_type == "SIU^S12^SIU_S12"
    assert validate_siu(_message().replace("SCH|RDV-42", "SCH|")).is_valid is False


def test_siu_creates_then_cancels_same_appointment():
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        created = integrate_siu(_message(), session)
        assert created.external_id == "RDV-42"
        assert created.status == "booked"
        assert created.start_at.strftime("%Y%m%d%H%M") == "202609151000"

        cancelled = integrate_siu(_message("S15"), session)
        assert cancelled.id == created.id
        assert cancelled.status == "cancelled"
        assert session.exec(select(Appointment)).all() == [cancelled]


def test_scenario_validator_does_not_apply_pam_rules_to_siu():
    result = validate_scenario(_message())
    assert result.is_valid
    assert result.messages[0].message_type.startswith("SIU^")
