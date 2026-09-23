import logging

import pytest

from app.services.fhir_transport import post_fhir_bundle


@pytest.mark.asyncio
async def test_fhir_transport_keeps_status_when_the_response_is_not_json(monkeypatch, caplog):
    class Response:
        status_code = 202

        def json(self):
            raise ValueError("not json")

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, *_args, **_kwargs):
            return Response()

    monkeypatch.setattr("app.services.fhir_transport.httpx.AsyncClient", lambda **_kwargs: Client())

    with caplog.at_level(logging.DEBUG):
        status, body = await post_fhir_bundle("https://fhir.example.test", {"resourceType": "Bundle"})

    assert (status, body) == (202, {})
    assert "FHIR endpoint returned a non-JSON response" in caplog.text
