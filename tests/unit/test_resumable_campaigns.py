import pytest

from app.models_endpoints import SystemEndpoint
from app.models_qualification import QualificationCampaign, QualificationCampaignItem
from app.models_scenarios import InteropScenario, InteropScenarioStep
from app.services.scenario_campaign_service import process_scenario_campaign, queue_scenario_campaign


@pytest.mark.asyncio
async def test_queued_campaign_is_processed_incrementally_and_can_resume(session, tmp_path):
    scenario = InteropScenario(key="resumable-campaign", name="Campagne reprise")
    endpoint = SystemEndpoint(name="Dépôt", kind="FILE", role="sender", outbox_path=str(tmp_path))
    campaign = QualificationCampaign(key="resumable-campaign", name="Campagne reprise")
    session.add_all([scenario, endpoint, campaign]); session.commit()
    session.add(InteropScenarioStep(scenario_id=scenario.id, order_index=1, message_format="hl7", payload="MSH|^~\\&|S|F|R|F|202601010000||ADT^A28|1|P|2.5\rPID|||OLD"))
    session.add(QualificationCampaignItem(campaign_id=campaign.id, scenario_id=scenario.id, endpoint_id=endpoint.id, order_index=1)); session.commit()

    run = queue_scenario_campaign(session, campaign)
    assert run.status == "queued"
    run = await process_scenario_campaign(session, run.id, max_items=1)

    assert (run.status, run.next_item_index, run.passed_items) == ("passed", 1, 1)
    assert '"campaign_item_id"' in run.evidence_json
