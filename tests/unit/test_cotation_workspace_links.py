from pathlib import Path


def test_active_cotation_links_target_the_persistent_workspace() -> None:
    templates = {
        "dossier_detail.html": "{{ dossier.id }}",
        "messages_by_dossier.html": "{{ d.dossier_id }}",
    }
    for template_name, dossier_expression in templates.items():
        template = Path("app/templates", template_name).read_text(encoding="utf-8")

        assert f"/dossiers/{dossier_expression}/cotations" not in template
        assert f"/cotations/dossier/{dossier_expression}/saisie" in template


def test_ccam_dashboard_advertises_the_persistent_workspace() -> None:
    source = Path("app/routers/ccam.py").read_text(encoding="utf-8")

    assert '"url": "/cotations/dossier/{dossier_id}/saisie"' in source
