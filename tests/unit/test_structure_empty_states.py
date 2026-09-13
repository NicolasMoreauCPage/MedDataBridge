import pytest

# The `client` fixture seeds one sample entity of each structure type as a side effect
# of its GHT-context bootstrap (visiting /admin/ght/{id}), so a `q` filter guaranteed
# to match nothing is used to exercise the genuinely-empty {% else %} branch.
NO_MATCH_FILTER = "q=zzz-no-such-entity-zzz"


@pytest.mark.parametrize("path", [
    f"/structure/poles?{NO_MATCH_FILTER}",
    f"/structure/services?{NO_MATCH_FILTER}",
    f"/structure/chambres?{NO_MATCH_FILTER}",
    f"/structure/lits?{NO_MATCH_FILTER}",
    f"/structure/eg?{NO_MATCH_FILTER}",
])
def test_structure_list_empty_state_renders(client, session, path):
    resp = client.get(path)
    assert resp.status_code == 200
    assert "assistant de structure" in resp.text
    assert "\\'" not in resp.text
    assert 'href="/structure/wizard"' in resp.text


def test_structure_wizard_selects_its_target_eg_before_generation(client, session):
    response = client.get("/structure/wizard")

    assert response.status_code == 200
    assert 'id="targetEgId"' in response.text
    assert "Entité géographique cible" in response.text
    assert "ID de l'Entité Géographique cible" not in response.text
    assert "data-step-content=\"1\"" in response.text
    assert 'id="structure-wizard-input-dialog"' in response.text
    assert "isTemplateLoading" in response.text
