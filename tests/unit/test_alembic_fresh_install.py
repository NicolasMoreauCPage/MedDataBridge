import logging

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


def test_alembic_head_bootstraps_complete_scenario_schema(tmp_path, caplog):
    database = tmp_path / "fresh.db"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database}")

    command.upgrade(config, "head")

    inspector = inspect(create_engine(f"sqlite:///{database}"))
    step_columns = {column["name"] for column in inspector.get_columns("interopscenariostep")}
    delivery_columns = {column["name"] for column in inspector.get_columns("scenariodelivery")}
    assert {"is_required", "route_mode", "endpoint_ids_json", "target_system_key"} <= step_columns
    assert {"scheduled_at", "validation_status", "validation_json", "is_required"} <= delivery_columns

    command.downgrade(config, "fa7d1e4c9b20")
    downgraded = inspect(create_engine(f"sqlite:///{database}"))
    assert "route_mode" not in {
        column["name"] for column in downgraded.get_columns("interopscenariostep")
    }

    command.upgrade(config, "head")
    upgraded = inspect(create_engine(f"sqlite:///{database}"))
    assert "route_mode" in {
        column["name"] for column in upgraded.get_columns("interopscenariostep")
    }

    with caplog.at_level(logging.INFO):
        logging.getLogger(__name__).info("host logging remains configured")
    assert "host logging remains configured" in caplog.text
