from app.services.structure_seed import DEMO_STRUCTURE, EXTENDED_GHT_DATA
from app.services.structure_seed_data import (
    DEMO_STRUCTURE as DATA_DEMO_STRUCTURE,
    EXTENDED_GHT_DATA as DATA_EXTENDED_GHT_DATA,
)


def test_seed_datasets_are_reexported_by_service() -> None:
    assert DEMO_STRUCTURE is DATA_DEMO_STRUCTURE
    assert EXTENDED_GHT_DATA is DATA_EXTENDED_GHT_DATA


def test_seed_datasets_expose_expected_roots() -> None:
    assert DEMO_STRUCTURE["entite_juridique"]["finess_ej"]
    assert DEMO_STRUCTURE["sites"]
    assert EXTENDED_GHT_DATA["juridical_entities"]
