import json

from sqlmodel import select

from app.models_scenario_review import ScenarioCatalogReview
from app.models_scenarios import InteropScenario, InteropScenarioStep
from app.services.scenario_catalog_review import apply_catalog_review


def _scenario(session, key: str, payload: str) -> InteropScenario:
    scenario = InteropScenario(key=key, name=key)
    session.add(scenario)
    session.flush()
    session.add(InteropScenarioStep(
        scenario_id=scenario.id,
        order_index=1,
        message_format="hl7",
        message_type="ADT^A01",
        payload=payload,
    ))
    return scenario


def test_catalog_review_activates_only_approved_and_disables_repairable_or_duplicates(session, tmp_path):
    approved = _scenario(session, "legacy.pam.approved", "MSH|approved")
    repairable = _scenario(session, "legacy.pam.repairable", "MSH|repairable")
    manual = _scenario(session, "legacy.hprim.manual", "MSH|manual")
    unassessed = _scenario(session, "local.unassessed", "MSH|unassessed")
    duplicate = _scenario(session, "local.duplicate", "MSH|approved")
    session.commit()

    report_path = tmp_path / "result.json"
    report_path.write_text(json.dumps({"results": [
        {"key": approved.key, "qualification": "conserver"},
        {"key": repairable.key, "qualification": "corriger_sequence_pam"},
        {"key": manual.key, "qualification": "a_qualifier"},
    ]}), encoding="utf-8")

    result = apply_catalog_review(session, report_path)
    session.refresh(approved)
    session.refresh(repairable)
    session.refresh(manual)
    session.refresh(unassessed)
    session.refresh(duplicate)

    assert approved.is_active is True
    assert repairable.is_active is False
    assert manual.is_active is False
    assert unassessed.is_active is False
    assert duplicate.is_active is False
    reviews = {row.scenario_id: row for row in session.exec(select(ScenarioCatalogReview)).all()}
    assert reviews[approved.id].status == "approved"
    assert reviews[repairable.id].status == "repairable"
    assert reviews[manual.id].status == "manual_review"
    assert reviews[duplicate.id].status == "duplicate"
    assert result["active"] == 1


def test_catalog_review_matches_a_report_by_stable_source_checksum(session, tmp_path):
    scenario = _scenario(session, "legacy.old-normalizer-key", "MSH|checksum")
    scenario.source_checksum = "stable-content-checksum"
    session.add(scenario)
    session.commit()
    report_path = tmp_path / "result.json"
    report_path.write_text(json.dumps({"results": [{
        "key": "legacy.new-normalizer-key",
        "source_checksum": "stable-content-checksum",
        "qualification": "conserver",
    }]}), encoding="utf-8")

    apply_catalog_review(session, report_path)
    session.refresh(scenario)
    review = session.exec(select(ScenarioCatalogReview).where(ScenarioCatalogReview.scenario_id == scenario.id)).one()
    assert scenario.is_active is True
    assert review.status == "approved"
