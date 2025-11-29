import json
from sqlmodel import Session, select

from app.db import init_db, session_factory
from app.services.scenario_template_init import init_scenario_templates
from app.services.scenario_template_materializer import materialize_template, MaterializationOptions
from app.models_scenarios import ScenarioTemplate


def test_materialize_hl7():
    init_db()
    session: Session = session_factory()
    init_scenario_templates(session)
    tmpl = session.exec(select(ScenarioTemplate).where(ScenarioTemplate.key == "ihe.hospitSimple")).first()
    assert tmpl is not None
    scenario = materialize_template(session, tmpl, options=MaterializationOptions(protocol="HL7v2"))
    assert scenario.steps
    first = scenario.steps[0]
    assert "MSH" in first.payload and "PID" in first.payload


def test_materialize_fhir():
    init_db()
    session: Session = session_factory()
    init_scenario_templates(session)
    tmpl = session.exec(select(ScenarioTemplate).where(ScenarioTemplate.key == "ihe.hospitSimple")).first()
    assert tmpl is not None
    scenario = materialize_template(session, tmpl, options=MaterializationOptions(protocol="FHIR"))
    assert scenario.steps
    first = scenario.steps[0]
    data = json.loads(first.payload)
    assert data["resourceType"] == "Bundle"
    assert data["entry"][0]["resource"]["resourceType"] == "Patient"
