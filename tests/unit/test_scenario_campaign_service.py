import pytest

from app.models_endpoints import SystemEndpoint
from app.models_qualification import QualificationCampaign, QualificationCampaignItem
from app.models_scenarios import InteropScenario, InteropScenarioStep
from app.services.scenario_campaign_service import run_scenario_campaign


@pytest.mark.asyncio
async def test_durable_campaign_creates_a_play_for_each_item(session, tmp_path):
    scenario = InteropScenario(key="campaign-play", name="Campagne durable")
    session.add(scenario)
    session.commit()
    session.add(InteropScenarioStep(scenario_id=scenario.id, order_index=1, message_format="hl7", payload="MSH|^~\\&|S|F|R|F|202601010000||ADT^A01|1|P|2.5\rPID|||OLD"))
    endpoint = SystemEndpoint(name="Dépôt campagne", kind="FILE", role="sender", outbox_path=str(tmp_path))
    campaign = QualificationCampaign(key="campaign-play", name="Campagne durable")
    session.add_all([endpoint, campaign])
    session.commit()
    session.add(QualificationCampaignItem(campaign_id=campaign.id, scenario_id=scenario.id, endpoint_id=endpoint.id, order_index=1))
    session.commit()

    result = await run_scenario_campaign(session, campaign)

    assert (result.status, result.passed_items, result.failed_items) == ("passed", 1, 0)
    assert '"play_id"' in result.evidence_json
