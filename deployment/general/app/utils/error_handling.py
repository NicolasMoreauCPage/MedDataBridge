"""Gestion centralisée des erreurs pour MedDataBridge."""
from typing import Optional, Dict, Any
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from app.utils.structured_logging import StructuredLogger


logger = StructuredLogger(__name__)


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
        **exc.details
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "type": type(exc).__name__,
                "message": exc.message,
                "details": exc.details
            }
        }
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
        method=request.method
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "type": "HTTPException",
                "message": exc.detail
            }
        }
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
        errors_count=len(errors)
    )
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": {
                "type": "ValidationError",
                "message": "Erreur de validation des données",
                "details": {
                    "errors": errors
                }
            }
        }
    )


async def generic_exception_handler(
    request: Request,
    exc: Exception
) -> JSONResponse:
    """Handler pour toutes les autres exceptions."""
    logger.error(
        f"Unexpected error: {str(exc)}",
        error_type=type(exc).__name__,
        path=request.url.path,
        method=request.method,
        exc_info=True
    )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "type": "InternalServerError",
                "message": "Une erreur interne s'est produite"
            }
        }
    )


def register_exception_handlers(app):
    """Enregistre tous les handlers d'exceptions."""
    app.add_exception_handler(MedBridgeError, medbridge_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)