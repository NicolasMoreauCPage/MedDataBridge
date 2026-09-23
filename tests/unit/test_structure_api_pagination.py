import inspect

from fastapi import Response
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app.routers import structure
from app.models_structure import EntiteGeographique


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
        assert parameters["response"].annotation is Response


def test_paginated_query_keeps_list_contract_and_exposes_total():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        session.add_all(
            [
                EntiteGeographique(name="B", identifier="eg-b"),
                EntiteGeographique(name="A", identifier="eg-a"),
                EntiteGeographique(name="C", identifier="eg-c"),
            ]
        )
        session.commit()
        response = Response()

        result = structure._execute_paginated(
            session,
            response,
            select(EntiteGeographique),
            order_by=(EntiteGeographique.name, EntiteGeographique.id),
            skip=1,
            limit=1,
        )

    assert [item.name for item in result] == ["B"]
    assert response.headers["X-Total-Count"] == "3"
