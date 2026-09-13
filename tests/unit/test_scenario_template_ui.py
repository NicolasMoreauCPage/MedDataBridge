from app.models_endpoints import SystemEndpoint
from app.models_scenarios import ScenarioTemplate, ScenarioTemplateStep


def test_template_detail_uses_the_accessible_template_workspace(client, session):
    template = ScenarioTemplate(
        key="template-ui-workspace",
        name="Admission de démonstration",
        description="Parcours de test réutilisable.",
    )
    session.add(template)
    session.flush()
    session.add(ScenarioTemplateStep(
        template_id=template.id,
        order_index=1,
        semantic_event_code="ADMISSION_CONFIRMED",
        narrative="Admission confirmée.",
        hl7_event_code="ADT^A01",
    ))
    mllp_sender = SystemEndpoint(name="MLLP HL7", kind="MLLP", role="sender")
    session.add_all([
        SystemEndpoint(name="Endpoint partagé", kind="FILE", role="both"),
        SystemEndpoint(name="Réception seule", kind="MLLP", role="receiver"),
        mllp_sender,
    ])
    session.commit()

    response = client.get(f"/scenarios/templates/{template.key}")

    assert response.status_code == 200
    assert "Admission de démonstration" in response.text
    assert "Étapes du scénario ()" not in response.text
    assert "data-scenario-template-workspace" in response.text
    assert "js/scenario-template-workspace.js" in response.text
    assert "Créer un scénario depuis le modèle" in response.text
    assert "onclick=\"materializeOnly()\"" not in response.text
    assert "Endpoint partagé" in response.text
    assert "Réception seule" not in response.text
    assert "data-template-endpoint" in response.text

    incompatible = client.post(
        f"/scenarios/templates/{template.key}/play",
        data={"protocol": "FHIR", "endpoint_id": str(mllp_sender.id)},
    )

    assert incompatible.status_code == 422
    assert "n'est pas compatible" in incompatible.json()["detail"]

    invalid_protocol = client.post(
        f"/scenarios/templates/{template.key}/materialize",
        json={"protocol": "HPRIM"},
    )

    assert invalid_protocol.status_code == 422
    assert "Protocole de modèle invalide" in invalid_protocol.json()["detail"]
