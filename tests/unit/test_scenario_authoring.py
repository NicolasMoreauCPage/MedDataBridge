from sqlmodel import select

from app.models_scenarios import InteropScenario, InteropScenarioStep, ScenarioTemplate, ScenarioTemplateStep
from app.services.scenario_authoring import (
    AUTHORING_DRAFT,
    AUTHORING_READY,
    create_manual_draft,
    create_template_draft,
    duplicate_scenario_draft,
    mark_ready,
    unique_scenario_key,
    validate_authoring,
)


def _template(session) -> ScenarioTemplate:
    template = ScenarioTemplate(
        key="authoring-admission",
        name="Admission guidée",
        description="Admission de démonstration",
        category="IHE PAM",
        protocols_supported="HL7v2,FHIR",
    )
    session.add(template)
    session.flush()
    session.add(
        ScenarioTemplateStep(
            template_id=template.id,
            order_index=1,
            semantic_event_code="ADMISSION_CONFIRMED",
            narrative="Admission confirmée",
            hl7_event_code="ADT^A01",
        )
    )
    session.commit()
    session.refresh(template)
    return template


def test_manual_draft_generates_an_available_key_and_stays_inactive(session):
    first = create_manual_draft(session, name="Admission programmée")
    second = create_manual_draft(session, name="Admission programmée")

    assert first.key == "admission-programmee"
    assert second.key == "admission-programmee-2"
    assert first.authoring_status == AUTHORING_DRAFT
    assert first.is_active is False
    assert any(issue.code == "scenario.steps.required" for issue in validate_authoring(session, first))


def test_template_draft_reuses_materializer_but_keeps_user_identity(session):
    template = _template(session)

    scenario = create_template_draft(
        session,
        template=template,
        name="Admission de recette",
        description="Parcours destiné à la recette",
        requested_key="recette-admission",
        protocol="HL7v2",
    )

    assert scenario.key == "recette-admission"
    assert scenario.name == "Admission de recette"
    assert scenario.description == "Parcours destiné à la recette"
    assert scenario.authoring_status == AUTHORING_DRAFT
    assert scenario.is_active is False
    assert len(scenario.steps) == 1
    assert scenario.steps[0].message_type == "ADT^A01"

    issues = mark_ready(session, scenario)
    assert not [issue for issue in issues if issue.level == "error"]
    assert scenario.authoring_status == AUTHORING_READY
    assert scenario.is_active is True


def test_duplicate_draft_copies_steps_without_activating_the_copy(session):
    source = InteropScenario(key="source-authoring", name="Source", protocol="HL7")
    session.add(source)
    session.flush()
    session.add(
        InteropScenarioStep(
            scenario_id=source.id,
            order_index=1,
            name="Admission",
            message_format="hl7",
            message_type="ADT^A01",
            payload="MSH|^~\\&|SRC|FAC|DST|FAC|202601010000||ADT^A01|1|P|2.5\rPID|||P",
            delay_seconds=60,
        )
    )
    session.commit()
    session.refresh(source)

    duplicate = duplicate_scenario_draft(session, source=source, name="Copie source")

    assert duplicate.key == "copie-source"
    assert duplicate.authoring_status == AUTHORING_DRAFT
    assert duplicate.is_active is False
    copied_steps = session.exec(select(InteropScenarioStep).where(InteropScenarioStep.scenario_id == duplicate.id)).all()
    assert len(copied_steps) == 1
    assert copied_steps[0].payload == source.steps[0].payload


def test_unique_key_normalizes_accents_and_special_characters(session):
    scenario = InteropScenario(key="admission-deja", name="Déjà")
    session.add(scenario)
    session.commit()

    assert unique_scenario_key(session, "Admission déjà !", "ignored") == "admission-deja-2"
