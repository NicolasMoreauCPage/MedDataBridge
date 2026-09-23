"""Les scripts d'initialisation applicatifs ne créent pas le schéma en direct."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = (
    ROOT / "scripts/setup/seed_data.py",
    ROOT / "scripts/tools/init_interop_scenarios.py",
    ROOT / "scripts/tools/init_all.py",
    ROOT / "scripts/maintenance/init_db.py",
    ROOT / "scripts/tools/create_test_structure.py",
    ROOT / "scripts/tools/init_complete_demo.py",
    ROOT / "scripts/tools/init_demo_movements.py",
    ROOT / "scripts/tools/init_demo_ght.py",
    ROOT / "scripts/tools/reset_db.py",
)


def test_operational_seed_scripts_delegate_schema_changes_to_alembic():
    for script in SCRIPTS:
        source = script.read_text(encoding="utf-8")
        assert "migrate_database" in source, script
        assert "SQLModel.metadata.create_all" not in source, script
