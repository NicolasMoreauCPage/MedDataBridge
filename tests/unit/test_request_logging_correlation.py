import logging

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.middleware.error_handler import ErrorHandlingMiddleware, RequestLoggingMiddleware


def test_request_logs_and_unhandled_error_share_the_correlation_id(caplog):
    app = FastAPI()
    app.add_middleware(ErrorHandlingMiddleware)
    app.add_middleware(RequestLoggingMiddleware)

    @app.get("/boom")
    def boom():
        raise RuntimeError("boom")

    correlation_id = "request-log-42"
    with TestClient(app, raise_server_exceptions=False) as client, caplog.at_level(logging.INFO):
        response = client.get("/boom", headers={"X-Correlation-ID": correlation_id})

    assert response.status_code == 500
    assert response.json()["error"]["correlation_id"] == correlation_id
    assert response.headers["X-Correlation-ID"] == correlation_id
    messages = [record.getMessage() for record in caplog.records]
    assert "HTTP request received" in messages
    assert "HTTP request completed" in messages
    assert any(getattr(record, "correlation_id", None) == correlation_id for record in caplog.records)
