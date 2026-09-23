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


def test_safe_fhir_metric_logs_its_optional_failure(monkeypatch, caplog):
    def unavailable(**_kwargs):
        raise RuntimeError("metrics unavailable")

    monkeypatch.setattr(app_metrics, "record_fhir_event", unavailable)

    app_metrics.record_fhir_event_safely("inbound", "patient", "import", False, 500)

    assert "FHIR metric recording failed" in caplog.text


def test_safe_outbound_metric_logs_its_optional_failure(monkeypatch, caplog):
    def unavailable(**_kwargs):
        raise RuntimeError("metrics unavailable")

    monkeypatch.setattr(app_metrics, "record_outbound_delivery", unavailable)

    app_metrics.record_outbound_delivery_safely(
        protocol="MLLP",
        status="error",
        duration_seconds=0.01,
    )

    assert "Outbound delivery metric recording failed" in caplog.text
