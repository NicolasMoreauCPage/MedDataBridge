"""Contrats d'exécution des routes de cartographie."""

import inspect

from app.routers import location_cartography
from app.routers import interface_testing


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


def test_sqlmodel_qualification_detail_routes_are_sync():
    """Les lectures de détail n'ont pas d'opération asynchrone à attendre."""
    assert not inspect.iscoroutinefunction(interface_testing.qualification_run_detail)
    assert not inspect.iscoroutinefunction(interface_testing.campaign_run_detail)
