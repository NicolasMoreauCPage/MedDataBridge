import inspect

from app.routers import structure


LIST_ENDPOINTS = (
    structure.list_entites_geographiques_api,
    structure.list_poles_api,
    structure.list_services_api,
    structure.list_unites_fonctionnelles_api,
    structure.list_unites_hebergement_api,
    structure.list_chambres_api,
    structure.list_lits_api,
)


def _bound(query, attribute):
    return next(
        getattr(metadata, attribute)
        for metadata in query.metadata
        if hasattr(metadata, attribute)
    )


def test_structure_list_endpoints_share_bounded_offset_pagination():
    for endpoint in LIST_ENDPOINTS:
        parameters = inspect.signature(endpoint).parameters
        skip = parameters["skip"].default
        limit = parameters["limit"].default

        assert skip.default == 0
        assert _bound(skip, "ge") == 0
        assert limit.default == structure.DEFAULT_API_PAGE_SIZE
        assert _bound(limit, "ge") == 1
        assert _bound(limit, "le") == structure.MAX_API_PAGE_SIZE
