from types import SimpleNamespace

from app.services.emission_endpoints import list_eligible_sender_endpoints


class _Result:
    def __init__(self, endpoints):
        self.endpoints = endpoints

    def all(self):
        return self.endpoints


class _Session:
    def __init__(self, endpoints):
        self.endpoints = endpoints
        self.executed = []

    def exec(self, statement):
        self.executed.append(statement)
        return _Result(self.endpoints)


def test_eligible_sender_endpoints_respect_global_ej_and_ght_scope():
    endpoints = [
        SimpleNamespace(id=1, entite_juridique_id=None, ght_context_id=None),
        SimpleNamespace(id=2, entite_juridique_id=20, ght_context_id=None),
        SimpleNamespace(id=3, entite_juridique_id=None, ght_context_id=30),
        SimpleNamespace(id=4, entite_juridique_id=21, ght_context_id=31),
    ]
    session = _Session(endpoints)

    selected = list_eligible_sender_endpoints(
        session,
        SimpleNamespace(entite_juridique_id=20, ght_context_id=30),
    )

    assert [endpoint.id for endpoint in selected] == [1, 2, 3]
    assert len(session.executed) == 1
