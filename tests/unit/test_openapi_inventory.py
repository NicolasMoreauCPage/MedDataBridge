from scripts.generate_openapi_inventory import render_inventory


def test_inventory_is_sorted_and_excludes_non_api_methods():
    inventory = render_inventory(
        {
            "paths": {
                "/z": {
                    "get": {"summary": "Dernière", "tags": ["Zeta"]},
                    "options": {"summary": "Prévol", "tags": ["Zeta"]},
                },
                "/a": {
                    "post": {"operationId": "create_first", "tags": ["Alpha"]},
                    "delete": {},
                },
            }
        }
    )

    assert "3 opérations générées automatiquement." in inventory
    assert inventory.index("## Alpha") < inventory.index("## Zeta")
    assert "| `POST` | `/a` | create_first |" in inventory
    assert "| `DELETE` | `/a` | Sans libellé |" in inventory
    assert "Prévol" not in inventory
