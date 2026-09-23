"""Contrats d'exécution des routes de cartographie."""

import inspect

from app.routers import location_cartography


def test_sqlmodel_cartography_routes_are_sync():
    """Les lectures SQLModel sont exécutées hors de la boucle async FastAPI."""
    routes = (
        location_cartography.get_services,
        location_cartography.get_service_ufs,
        location_cartography.get_uf_hebergement,
        location_cartography.get_uh_chambres,
        location_cartography.get_uf_available_lits,
        location_cartography.get_chambre_lits,
        location_cartography.get_lit_details,
        location_cartography.get_hierarchy_tree,
    )
    assert not any(inspect.iscoroutinefunction(route) for route in routes)
