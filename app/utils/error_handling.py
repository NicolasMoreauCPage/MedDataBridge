"""Gestion centralisée des erreurs pour MedDataBridge."""
from typing import Optional, Dict, Any
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from app.utils.structured_logging import StructuredLogger


logger = StructuredLogger(__name__)


def _correlation_id(request: Request) -> str | None:
    """Retrouve l'identifiant généré par le middleware de requête."""
    return getattr(request.state, "correlation_id", None)


def _legacy_detail(message: str, details: Optional[Dict[str, Any]]) -> str | list[dict[str, Any]]:
    """Préserve la forme ``detail`` attendue par les anciens clients FastAPI."""
    validation_errors = (details or {}).get("errors")
    if not isinstance(validation_errors, list):
        return message
    return [
        {
            "loc": str(item.get("field", "")).split(" -> "),
            "msg": item.get("message", ""),
            "type": item.get("type", ""),
        }
        for item in validation_errors
        if isinstance(item, dict)
    ]


def _error_content(
    *,
    code: str,
    message: str,
    details: Optional[Dict[str, Any]] = None,
    error_type: Optional[str] = None,
    correlation_id: str | None = None,
) -> dict:
    """Enveloppe d'erreur stable pour tous les consommateurs HTTP."""
    error = {
        "code": code,
        "message": message,
        "details": details or {},
        "correlation_id": correlation_id,
    }
    # ``type`` est conservé durant la transition pour les clients existants.
    if error_type:
        error["type"] = error_type
    # ``detail`` est l'alias historique FastAPI. Le conserver au niveau racine
    # permet aux écrans et intégrations plus anciens de migrer progressivement
    # vers ``error.message`` sans casser leur traitement des erreurs.
    return {"error": error, "detail": _legacy_detail(message, details)}


def _error_response(
    request: Request,
    *,
    status_code: int,
    code: str,
    message: str,
    details: Optional[Dict[str, Any]] = None,
    error_type: Optional[str] = None,
) -> JSONResponse:
    correlation_id = _correlation_id(request)
    response = JSONResponse(
        status_code=status_code,
        content=_error_content(
            code=code,
            message=message,
            details=details,
            error_type=error_type,
            correlation_id=correlation_id,
        ),
    )
    if correlation_id:
        response.headers["X-Correlation-ID"] = correlation_id
    return response


class MedBridgeError(Exception):
    """Classe de base pour les erreurs MedDataBridge."""
    
    def __init__(
        self,
        message: str,
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


class ValidationError(MedBridgeError):
    """Erreur de validation des données."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status.HTTP_422_UNPROCESSABLE_ENTITY, details)


class NotFoundError(MedBridgeError):
    """Ressource non trouvée."""
    
    def __init__(self, resource_type: str, resource_id: Any):
        message = f"{resource_type} avec l'ID {resource_id} non trouvé"
        super().__init__(message, status.HTTP_404_NOT_FOUND)


class ConflictError(MedBridgeError):
    """Conflit avec l'état actuel (ex: doublon)."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status.HTTP_409_CONFLICT, details)


class FHIRError(MedBridgeError):
    """Erreur liée au traitement FHIR."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status.HTTP_400_BAD_REQUEST, details)


class HL7Error(MedBridgeError):
    """Erreur liée au traitement HL7."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status.HTTP_400_BAD_REQUEST, details)


async def medbridge_exception_handler(
    request: Request,
    exc: MedBridgeError
) -> JSONResponse:
    """Handler pour les exceptions MedDataBridge."""
    logger.error(
        f"MedBridge error: {exc.message}",
        status_code=exc.status_code,
        error_type=type(exc).__name__,
        path=request.url.path,
        method=request.method,
        correlation_id=_correlation_id(request),
        **exc.details
    )
    
    return _error_response(
        request,
        status_code=exc.status_code,
        code=type(exc).__name__.replace("Error", "").upper() or "MEDBRIDGE_ERROR",
        message=exc.message,
        details=exc.details,
        error_type=type(exc).__name__,
    )


async def http_exception_handler(
    request: Request,
    exc: StarletteHTTPException
) -> JSONResponse:
    """Handler pour les exceptions HTTP standard."""
    logger.warning(
        f"HTTP error: {exc.detail}",
        status_code=exc.status_code,
        path=request.url.path,
        method=request.method,
        correlation_id=_correlation_id(request),
    )
    
    return _error_response(
        request,
        status_code=exc.status_code,
        code=f"HTTP_{exc.status_code}",
        message=str(exc.detail),
        error_type="HTTPException",
    )


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError
) -> JSONResponse:
    """Handler pour les erreurs de validation Pydantic."""
    errors = []
    for error in exc.errors():
        errors.append({
            "field": " -> ".join(str(x) for x in error["loc"]),
            "message": error["msg"],
            "type": error["type"]
        })
    
    logger.warning(
        "Validation error",
        path=request.url.path,
        method=request.method,
        errors_count=len(errors),
        correlation_id=_correlation_id(request),
    )
    
    return _error_response(
        request,
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        code="VALIDATION_ERROR",
        message="Erreur de validation des données",
        details={"errors": errors},
        error_type="ValidationError",
    )


async def generic_exception_handler(
    request: Request,
    exc: Exception
) -> JSONResponse:
    """Handler pour toutes les autres exceptions."""
    logger.error(
        "Unexpected error",
        error_type=type(exc).__name__,
        path=request.url.path,
        method=request.method,
        correlation_id=_correlation_id(request),
    )
    
    return _error_response(
        request,
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        code="INTERNAL_ERROR",
        message="Une erreur interne s'est produite",
        error_type="InternalServerError",
    )


def register_exception_handlers(app):
    """Enregistre tous les handlers d'exceptions."""
    app.add_exception_handler(MedBridgeError, medbridge_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)
