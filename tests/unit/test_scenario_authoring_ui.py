from sqlmodel import select

from app.models_scenarios import InteropScenario, ScenarioTemplate, ScenarioTemplateStep


def _template(session):
    template = ScenarioTemplate(key="ui-guided-admission", name="Admission guidée", category="IHE PAM")
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
    return template


def test_new_scenario_page_exposes_guided_authoring_choices(client, session):
    template = _template(session)

    response = client.get("/scenarios/new")

    assert response.status_code == 200
    assert "Construire un scénario sans partir d'un message brut" in response.text
    assert template.name in response.text
    assert "data-scenario-builder" in response.text
    assert "js/scenario-builder.js" in response.text


def test_template_creation_redirects_to_review_as_an_inactive_draft(client, session):
    template = _template(session)

    response = client.post(
        "/scenarios/new",
        data={
            "creation_mode": "template",
            "name": "Admission depuis l'assistant",
            "description": "Créée pour vérifier le nouveau parcours.",
            "template_key": template.key,
            "protocol": "HL7",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"].endswith("/authoring")
    scenario = session.exec(select(InteropScenario).where(InteropScenario.name == "Admission depuis l'assistant")).one()
    assert scenario.authoring_status == "draft"
    assert scenario.is_active is False

    review = client.get(response.headers["location"])
    assert review.status_code == 200
    assert "Toute modification du parcours rend le scénario inactif" in review.text
    assert "Admission confirmée" in review.text


def test_manual_draft_cannot_be_marked_ready_without_steps(client, session):
    client.post(
        "/scenarios/new",
        data={"creation_mode": "manual", "name": "Nouveau manuel", "protocol": "HL7"},
        follow_redirects=False,
    )
    scenario = session.exec(select(InteropScenario).where(InteropScenario.name == "Nouveau manuel")).one()

    ready = client.post(f"/scenarios/{scenario.id}/authoring/ready", follow_redirects=False)

    assert ready.status_code == 303
    assert ready.headers["location"].endswith("/authoring")
    session.refresh(scenario)
    assert scenario.is_active is False
    assert scenario.authoring_status == "draft"


def test_manual_draft_can_add_a_functional_event_from_its_review(client, session):
    client.post(
        "/scenarios/new",
        data={"creation_mode": "manual", "name": "Parcours sans payload", "protocol": "HL7"},
        follow_redirects=False,
    )
    scenario = session.exec(select(InteropScenario).where(InteropScenario.name == "Parcours sans payload")).one()

    response = client.post(
        f"/scenarios/{scenario.id}/authoring/steps",
        data={"event_key": "admission", "delay_seconds": "0"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    session.refresh(scenario)
    assert len(scenario.steps) == 1
    assert scenario.steps[0].name == "Admission du patient"
    assert scenario.steps[0].message_type == "ADT^A01"
