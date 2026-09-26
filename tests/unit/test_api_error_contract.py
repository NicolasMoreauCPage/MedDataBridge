"""Contrat commun des erreurs HTTP publiques."""

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.middleware.error_handler import RequestLoggingMiddleware
from app.utils.error_handling import NotFoundError, register_exception_handlers


def _client() -> TestClient:
    app = FastAPI()
    register_exception_handlers(app)
    app.add_middleware(RequestLoggingMiddleware)

    @app.get("/missing")
    def missing():
        raise HTTPException(status_code=404, detail="Ressource absente")

    @app.get("/items/{item_id}")
    def item(item_id: int):
        return {"id": item_id}

    @app.get("/business")
    def business_error():
        raise NotFoundError("Patient", 42)

    @app.get("/crash")
    def unexpected_error():
        raise RuntimeError("PATIENT-SECRET-MARKER")

    return TestClient(app)


def test_http_and_validation_errors_share_the_stable_envelope():
    client = _client()
    correlation_id = "contract-test-42"

    response = client.get("/missing", headers={"X-Correlation-ID": correlation_id})
    body = response.json()["error"]
    assert response.status_code == 404
    assert response.headers["X-Correlation-ID"] == correlation_id
    assert response.json()["detail"] == "Ressource absente"
    assert body == {
        "code": "HTTP_404",
        "message": "Ressource absente",
        "details": {},
        "correlation_id": correlation_id,
        "type": "HTTPException",
    }

    validation = client.get("/items/not-an-integer")
    validation_error = validation.json()["error"]
    assert validation.status_code == 422
    assert validation_error["code"] == "VALIDATION_ERROR"
    assert validation_error["message"] == "Erreur de validation des données"
    assert validation_error["details"]["errors"]
    assert validation_error["correlation_id"] == validation.headers["X-Correlation-ID"]
    assert validation.json()["detail"][0]["loc"] == ["path", "item_id"]


def test_business_errors_keep_the_same_contract():
    response = _client().get("/business")

    error = response.json()["error"]
    assert response.status_code == 404
    assert error["code"] == "NOTFOUND"
    assert error["details"] == {}
    assert error["correlation_id"] == response.headers["X-Correlation-ID"]
    assert response.json()["detail"] == "Patient avec l'ID 42 non trouvé"


def test_unexpected_errors_keep_the_same_contract_and_correlation(caplog):
    correlation_id = "unexpected-error-42"
    with TestClient(_client().app, raise_server_exceptions=False) as client:
        response = client.get("/crash", headers={"X-Correlation-ID": correlation_id})

    assert response.status_code == 500
    assert response.headers["X-Correlation-ID"] == correlation_id
    assert response.json()["detail"] == "Une erreur interne s'est produite"
    assert response.json()["error"] == {
        "code": "INTERNAL_ERROR",
        "message": "Une erreur interne s'est produite",
        "details": {},
        "correlation_id": correlation_id,
        "type": "InternalServerError",
    }
    assert "PATIENT-SECRET-MARKER" not in caplog.text
