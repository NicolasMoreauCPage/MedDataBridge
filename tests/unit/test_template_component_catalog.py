from pathlib import Path


def test_ui_macro_catalog_has_a_single_modal_implementation():
    template = Path("app/templates/macros/ui.html").read_text(encoding="utf-8")

    assert template.count("{% macro modal(") == 1
    assert "data-dismiss-alert" in template
    assert "this.parentElement.remove()" not in template


def test_list_workspace_uses_shared_behaviors_without_inline_events():
    template = Path("app/templates/list.html").read_text(encoding="utf-8")

    assert "js/list-workspace.js" in template
    assert "data-submit-on-change" in template
    assert "onchange=" not in template
    assert "Gestion des suppressions asynchrones" not in template


def test_base_delegates_shell_behaviors_to_the_shell_script():
    template = Path("app/templates/base.html").read_text(encoding="utf-8")

    assert "js/app-shell.js" in template
    assert 'id="app-shell-config"' in template
    assert "function loadAlertCount" not in template
    assert 'href="/context/select"' in template


def test_core_deletion_forms_use_the_shared_confirmation_dialog():
    templates = (
        "patient_detail.html",
        "dossier_detail.html",
        "venue_detail.html",
        "mouvement_detail.html",
        "endpoint_detail.html",
    )

    for name in templates:
        template = Path("app/templates", name).read_text(encoding="utf-8")
        assert "data-confirm=" in template
        assert "onsubmit=\"return confirm" not in template
