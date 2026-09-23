from scripts.generate_openapi_inventory import render_inventory


def test_inventory_is_sorted_and_excludes_non_api_methods():
    inventory = render_inventory(
        {
            "paths": {
                "/z": {
                    "get": {
                        "summary": "Dernière | stable",
                        "tags": ["Zeta"],
                        "responses": {"200": {"content": {"text/html": {}}}},
                    },
                    "options": {"summary": "Prévol", "tags": ["Zeta"]},
                },
                "/a": {
                    "post": {
                        "operationId": "create_first",
                        "tags": ["Alpha"],
                        "x-owner": "Équipe interop",
                        "x-consumer": "Partenaire X",
                    },
                    "delete": {"deprecated": True},
                },
            }
        }
    )

    assert "3 opérations générées automatiquement." in inventory
    assert inventory.index("## Alpha") < inventory.index("## Zeta")
    assert "| Méthode | Chemin | Opération | Propriétaire | Statut | Consommateur |" in inventory
    assert "| `POST` | `/a` | create_first | Équipe interop | Active | Partenaire X |" in inventory
    assert "| `DELETE` | `/a` | Sans libellé | Domaine Sans tag | Dépréciée | À qualifier |" in inventory
    assert "Dernière \\| stable | Domaine Zeta | Active | Interface web" in inventory
    assert "Prévol" not in inventory
