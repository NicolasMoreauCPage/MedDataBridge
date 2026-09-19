import inspect

from app.routers.structure import get_structure_tree


def test_structure_tree_receives_request_through_fastapi_signature():
    parameters = inspect.signature(get_structure_tree).parameters

    assert "request" in parameters
    assert "inspect.stack" not in inspect.getsource(get_structure_tree)
