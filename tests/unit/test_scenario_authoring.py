from sqlmodel import select

from app.models_endpoints import SystemEndpoint
from app.models_scenarios import InteropScenario, InteropScenarioStep, ScenarioTemplate, ScenarioTemplateStep
from app.services.scenario_authoring import (
    AUTHORING_DRAFT,
    AUTHORING_READY,
    add_guided_step,
    create_manual_draft,
    create_template_draft,
    delete_guided_step,
    duplicate_scenario_draft,
    mark_ready,
    move_guided_step,
    set_common_routing,
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


def test_guided_events_create_playable_steps_and_keep_changes_as_drafts(session):
    scenario = create_manual_draft(session, name="Parcours guidé", protocol="HL7")

    admission = add_guided_step(session, scenario=scenario, event_key="admission")
    discharge = add_guided_step(session, scenario=scenario, event_key="discharge", delay_seconds=120)

    assert admission.name == "Admission du patient"
    assert admission.message_type == "ADT^A01"
    assert admission.payload.startswith("MSH|^~\\&")
    assert discharge.delay_seconds == 120
    assert not [issue for issue in validate_authoring(session, scenario) if issue.level == "error"]

    scenario.authoring_status = AUTHORING_READY
    scenario.is_active = True
    session.add(scenario)
    session.commit()
    assert move_guided_step(session, scenario=scenario, step=discharge, direction="up") is True
    session.refresh(scenario)
    assert scenario.authoring_status == AUTHORING_DRAFT
    assert scenario.is_active is False
    assert sorted(scenario.steps, key=lambda item: item.order_index)[0].id == discharge.id

    delete_guided_step(session, scenario=scenario, step=discharge)
    remaining = session.exec(select(InteropScenarioStep).where(InteropScenarioStep.scenario_id == scenario.id)).all()
    assert len(remaining) == 1
    assert remaining[0].order_index == 1


def test_common_routing_only_accepts_destinations_compatible_with_every_required_step(session):
    scenario = create_manual_draft(session, name="Routage guidé", protocol="HL7")
    add_guided_step(session, scenario=scenario, event_key="admission")
    endpoint = SystemEndpoint(name="MLLP commun", kind="MLLP", role="sender", is_enabled=True)
    fhir_endpoint = SystemEndpoint(name="FHIR seulement", kind="FHIR", role="sender", is_enabled=True)
    session.add_all([endpoint, fhir_endpoint])
    session.commit()

    set_common_routing(session, scenario=scenario, route_mode="explicit", endpoint_ids=[endpoint.id])
    session.refresh(scenario)
    assert scenario.steps[0].route_mode == "explicit"
    assert scenario.steps[0].endpoint_ids_json == f"[{endpoint.id}]"

    try:
        set_common_routing(session, scenario=scenario, route_mode="explicit", endpoint_ids=[fhir_endpoint.id])
    except ValueError as error:
        assert "compatible" in str(error)
    else:
        raise AssertionError("Une destination FHIR ne doit pas être proposée pour une étape HL7.")
