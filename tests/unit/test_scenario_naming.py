from app.services.scenario_naming import humanize_scenario_name


def test_humanize_compact_pam_name():
    assert humanize_scenario_name(
        "IHE PAM - Correctionchangementstatutextvershospit"
    ) == "IHE PAM – Correction de changement de statut externe vers hospitalisation"


def test_humanize_hprim_file_name():
    assert humanize_scenario_name(
        "Ajout_Acte_CCAM_intervention_existante.txt"
    ) == "Ajout d’acte CCAM intervention existante"


def test_humanize_does_not_change_technical_name_to_empty_value():
    assert humanize_scenario_name(None) == "Scénario sans nom"
