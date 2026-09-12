from sqlmodel import SQLModel, Session, create_engine, select

from app import db  # noqa: F401 - registre exhaustif de modèles
from app.models_qualification import ScenarioTheme, ScenarioThemeAssignment
from app.models_scenario_review import ScenarioCatalogReview
from app.models_scenarios import InteropScenario, InteropScenarioStep
from app.services.scenario_catalog_seed import apply_catalog_seed


def test_qualified_catalog_seed_is_complete_and_idempotent():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with engine.begin() as connection:
        first = apply_catalog_seed(connection)
    with engine.begin() as connection:
        second = apply_catalog_seed(connection)
    with Session(engine) as session:
        totals = [
            len(session.exec(select(model)).all())
            for model in (InteropScenario, InteropScenarioStep, ScenarioCatalogReview, ScenarioTheme, ScenarioThemeAssignment)
        ]
        context_ids = [item.ght_context_id for item in session.exec(select(InteropScenario)).all()]
    assert first == {"scenarios": 289, "steps": 1230, "reviews": 289, "themes": 15, "assignments": 238}
    assert second == {"scenarios": 0, "steps": 0, "reviews": 0, "themes": 0, "assignments": 0}
    assert totals == [289, 1230, 289, 15, 238]
    assert all(item is None for item in context_ids)
