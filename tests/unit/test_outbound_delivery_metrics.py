import app.metrics as app_metrics


def test_outbound_delivery_metrics_keep_dimensions_low_cardinality(monkeypatch):
    captured = []
    monkeypatch.setattr(
        app_metrics.ui_metrics,
        "record_operation",
        lambda **kwargs: captured.append(kwargs),
    )

    app_metrics.record_outbound_delivery(
        protocol="fhir",
        status="error",
        duration_seconds=0.125,
        endpoint_id=42,
        correlation_id="patient-42-update",
        error_type="HTTP_STATUS",
    )

    assert captured == [
        {
            "operation": "outbound_delivery_fhir",
            "duration": 0.125,
            "status": "error",
            "endpoint_id": 42,
            "correlation_id": "patient-42-update",
            "error_type": "HTTP_STATUS",
        }
    ]
