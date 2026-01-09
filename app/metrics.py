"""
Middleware et compteurs de métriques applicatives.

Ajoute des compteurs Prometheus pour les résultats de validation HPRIM
et conserve le middleware léger existant pour les requêtes HTTP.
"""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
import time

# Prometheus client (optionnel mais recommandé)
try:
    from prometheus_client import Counter, Histogram
except Exception:  # pragma: no cover - fallback si prom client non installé
    Counter = None
    Histogram = None

# Pont vers le collecteur UI existant
from app.utils.structured_logging import metrics as ui_metrics


class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware qui collecte des métriques sur les requêtes."""
    
    def __init__(self, app):
        super().__init__(app)
        self.request_count = 0
        self.total_duration = 0.0
    
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        response = await call_next(request)
        
        duration = time.time() - start_time
        self.request_count += 1
        self.total_duration += duration
        
        # Ajouter les métriques dans les headers
        response.headers["X-Request-Count"] = str(self.request_count)
        response.headers["X-Avg-Duration"] = f"{self.total_duration / self.request_count:.3f}"
        
        return response


# === Compteurs Prometheus pour la validation HPRIM ===
# Les labels permettent d'agréger par sens (inbound/outbound), schéma, résultat et type d'erreur.
if Counter is not None:
    HPRIM_VALIDATION_TOTAL = Counter(
        "hprim_validation_total",
        "Total des validations HPRIM (succès/erreurs)",
        ["direction", "schema", "result", "error_type"],
    )

    HPRIM_VALIDATION_DURATION_SECONDS = Histogram(
        "hprim_validation_duration_seconds",
        "Durée de validation HPRIM (secondes)",
        ["direction", "schema"],
        buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10),
    )

    HPRIM_XSD_ERRORS_TOTAL = Counter(
        "hprim_xsd_errors_total",
        "Nombre d'erreurs de validation XSD pour HPRIM",
        ["schema"],
    )

    HPRIM_CONTENT_ERRORS_TOTAL = Counter(
        "hprim_content_errors_total",
        "Nombre d'erreurs de validation métier/contenu pour HPRIM",
        ["schema"],
    )

    HPRIM_ENCODING_ERRORS_TOTAL = Counter(
        "hprim_encoding_errors_total",
        "Nombre d'erreurs d'encodage/charset pour HPRIM",
        [],
    )
else:
    # Fallback no-op pour environnements sans prometheus_client
    HPRIM_VALIDATION_TOTAL = None
    HPRIM_VALIDATION_DURATION_SECONDS = None
    HPRIM_XSD_ERRORS_TOTAL = None
    HPRIM_CONTENT_ERRORS_TOTAL = None
    HPRIM_ENCODING_ERRORS_TOTAL = None


def record_hprim_validation(
    succes: bool,
    schema: str | None = None,
    error_type: str | None = None,
    direction: str = "inbound",
    duration_seconds: float | None = None,
):
    """Enregistre le résultat d'une validation HPRIM dans les compteurs Prometheus
    et reflète l'événement dans le tableau de bord UI.
    """
    if Counter is None:
        # Même si Prometheus est indisponible, on alimente le dashboard UI
        ui_metrics.record_operation(
            operation=f"hprim_validation_{direction}",
            duration=duration_seconds or 0.0,
            status=("success" if succes else "error"),
            schema=(schema or "unknown"),
            error_type=(error_type or ("none" if succes else "unknown")),
        )
        return

    schema_label = schema or "unknown"
    result_label = "success" if succes else "error"
    error_label = error_type or ("none" if succes else "unknown")

    # Compteur global
    HPRIM_VALIDATION_TOTAL.labels(
        direction=direction,
        schema=schema_label,
        result=result_label,
        error_type=error_label,
    ).inc()

    # Durée si fournie
    if duration_seconds is not None:
        HPRIM_VALIDATION_DURATION_SECONDS.labels(
            direction=direction,
            schema=schema_label,
        ).observe(duration_seconds)

    # Compteurs spécifiques aux erreurs
    if not succes:
        if (error_type or "").lower() == "xsd":
            HPRIM_XSD_ERRORS_TOTAL.labels(schema_label).inc()
        elif (error_type or "").lower() in {"content", "business"}:
            HPRIM_CONTENT_ERRORS_TOTAL.labels(schema_label).inc()
        elif (error_type or "").lower() in {"encoding", "charset"}:
            HPRIM_ENCODING_ERRORS_TOTAL.inc()

    # Refléter dans le collecteur UI
    ui_metrics.record_operation(
        operation=f"hprim_validation_{direction}",
        duration=duration_seconds or 0.0,
        status=result_label,
        schema=schema_label,
        error_type=error_label,
    )

# === Compteurs pour IHE PAM (HL7 ADT) ===
if Counter is not None:
    PAM_VALIDATION_TOTAL = Counter(
        "pam_messages_total",
        "Total des messages PAM traités (ACK)",
        ["direction", "message_type", "ack_code"],
    )
    PAM_PROCESSING_DURATION_SECONDS = Histogram(
        "pam_processing_duration_seconds",
        "Durée de traitement des messages PAM (secondes)",
        ["direction", "message_type"],
        buckets=(0.005, 0.01, 0.05, 0.1, 0.25, 0.5, 1, 2, 5),
    )
else:
    PAM_VALIDATION_TOTAL = None
    PAM_PROCESSING_DURATION_SECONDS = None


def record_pam_ack(
    direction: str,
    ack_code: str,
    message_type: str,
    duration_seconds: float | None = None,
):
    """Enregistre le résultat (ACK) d'un message IHE PAM (HL7 ADT)."""
    # Déterminer succès/erreur pour le dashboard UI
    ack = (ack_code or "").upper()
    ui_status = "success" if ack in {"AA", "CA"} else "error"

    if Counter is not None:
        mt = message_type or "ADT^unknown"
        PAM_VALIDATION_TOTAL.labels(direction=direction, message_type=mt, ack_code=ack or "").inc()
        if duration_seconds is not None:
            PAM_PROCESSING_DURATION_SECONDS.labels(direction=direction, message_type=mt).observe(duration_seconds)

    # Refléter dans le collecteur UI
    ui_metrics.record_operation(
        operation=f"pam_message_{direction}",
        duration=duration_seconds or 0.0,
        status=ui_status,
        ack_code=ack,
        message_type=(message_type or "ADT"),
    )


# === Compteurs pour FHIR ===
if Counter is not None:
    FHIR_EVENTS_TOTAL = Counter(
        "fhir_events_total",
        "Total des événements FHIR (import/export)",
        ["direction", "resource", "action", "result", "status"],
    )
    FHIR_PROCESSING_DURATION_SECONDS = Histogram(
        "fhir_processing_duration_seconds",
        "Durée de traitement des événements FHIR (secondes)",
        ["direction", "resource", "action"],
        buckets=(0.005, 0.01, 0.05, 0.1, 0.25, 0.5, 1, 2, 5),
    )
else:
    FHIR_EVENTS_TOTAL = None
    FHIR_PROCESSING_DURATION_SECONDS = None


def record_fhir_event(
    direction: str,
    resource: str,
    action: str,
    success: bool,
    status_code: int | None = None,
    duration_seconds: float | None = None,
):
    """Enregistre un événement FHIR (import/export)."""
    result_label = "success" if success else "error"

    if Counter is not None:
        FHIR_EVENTS_TOTAL.labels(
            direction=direction,
            resource=(resource or "unknown").lower(),
            action=(action or "unknown").lower(),
            result=result_label,
            status=str(status_code or ""),
        ).inc()
        if duration_seconds is not None:
            FHIR_PROCESSING_DURATION_SECONDS.labels(
                direction=direction,
                resource=(resource or "unknown").lower(),
                action=(action or "unknown").lower(),
            ).observe(duration_seconds)

    # Refléter dans le collecteur UI
    ui_metrics.record_operation(
        operation=("fhir_import" if direction == "inbound" else "fhir_export"),
        duration=duration_seconds or 0.0,
        status=result_label,
        resource=(resource or "unknown").lower(),
        action=(action or "unknown").lower(),
        status_code=status_code,
    )
