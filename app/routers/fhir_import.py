"""API REST pour l'import FHIR."""
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlmodel import Session
from typing import Dict, Any
from app.db import get_session
from app.models_structure import EntiteJuridique
from app.converters.fhir_import_converter import (
    FHIRBundleImporter,
    FHIRToPatientConverter,
    FHIRToLocationConverter,
    FHIRToEncounterConverter,
    FHIRImportError
)
from pydantic import BaseModel
from app.services.fhir_profile_validator import FHIRProfileValidator


router = APIRouter(prefix="/api/fhir", tags=["FHIR Import"])


class FHIRBundleRequest(BaseModel):
    """Modèle pour la requête d'import de bundle FHIR."""
    bundle: Dict[str, Any]
    ej_id: int


class ImportResult(BaseModel):
    """Modèle pour le résultat d'import."""
    status: str
    message: str
    resources_created: int
    resources_updated: int
    errors: list[str] = []


@router.post("/import/bundle", response_model=ImportResult)
async def import_bundle(
    request: FHIRBundleRequest,
    session: Session = Depends(get_session)
):
    """
    Importe un bundle FHIR complet.
    
    Le bundle peut contenir des ressources Patient, Location, Encounter, etc.
    Les ressources sont créées ou mises à jour dans la base de données.
    
    Args:
        request: Requête contenant le bundle FHIR et l'ID de l'EJ
        
    Returns:
        Résultat de l'import avec statistiques
        
    Raises:
        400: Bundle invalide
        404: Entité juridique non trouvée
    """
    # Vérifier que l'EJ existe
    ej = session.get(EntiteJuridique, request.ej_id)
    if not ej:
        raise HTTPException(status_code=404, detail="Entité juridique non trouvée")
    
    # Vérifier que c'est bien un bundle
    bundle = request.bundle
    if bundle.get("resourceType") != "Bundle":
        raise HTTPException(
            status_code=400,
            detail="Le document doit être un Bundle FHIR"
        )
    
    # Compter les ressources
    entries = bundle.get("entry", [])
    if not entries:
        return ImportResult(
            status="success",
            message="Bundle vide, aucune ressource à importer",
            resources_created=0,
            resources_updated=0
        )
    
    # Utiliser le FHIRBundleImporter pour importer le bundle
    try:
        import time as _time
        _start = _time.time()
        importer = FHIRBundleImporter(session, ej)
        result = importer.import_bundle(bundle)
        # Metrics
        try:
            from app.metrics import record_fhir_event
            record_fhir_event(
                direction="inbound",
                resource="bundle",
                action="import",
                success=not result["errors"],
                status_code=200 if not result["errors"] else 206,
                duration_seconds=_time.time() - _start,
            )
        except Exception:
            pass

        return ImportResult(
            status="success" if not result["errors"] else "partial",
            message=f"Import terminé: {result['imported']} ressources importées ({result['locations']} locations, {result['patients']} patients, {result['encounters']} encounters)",
            resources_created=result["imported"],
            resources_updated=0,
            errors=[f"{e['resourceType']}: {e['error']}" for e in result["errors"]]
        )
    except FHIRImportError as e:
        try:
            from app.metrics import record_fhir_event
            record_fhir_event("inbound", "bundle", "import", False, 400)
        except Exception:
            pass
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        try:
            from app.metrics import record_fhir_event
            record_fhir_event("inbound", "bundle", "import", False, 500)
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'import: {str(e)}")


@router.post("/import/patient", response_model=ImportResult)
async def import_patient(
    patient: Dict[str, Any] = Body(...),
    ej_id: int = Body(...),
    session: Session = Depends(get_session)
):
    """
    Importe une ressource Patient FHIR.
    
    Args:
        patient: Ressource Patient FHIR
        ej_id: ID de l'entité juridique
        
    Returns:
        Résultat de l'import
        
    Raises:
        400: Ressource Patient invalide
        404: Entité juridique non trouvée
    """
    # Vérifier que l'EJ existe
    ej = session.get(EntiteJuridique, ej_id)
    if not ej:
        raise HTTPException(status_code=404, detail="Entité juridique non trouvée")
    
    # Vérifier que c'est bien un Patient
    if patient.get("resourceType") != "Patient":
        raise HTTPException(
            status_code=400,
            detail="La ressource doit être de type Patient"
        )
    
    # Utiliser le convertisseur patient
    try:
        import time as _time
        _start = _time.time()
        converter = FHIRToPatientConverter(session, ej)
        patient_obj = converter.convert_patient(patient)
        # Metrics
        try:
            from app.metrics import record_fhir_event
            record_fhir_event("inbound", "patient", "import", True, 200, _time.time() - _start)
        except Exception:
            pass

        return ImportResult(
            status="success",
            message=f"Patient {patient_obj.nom} {patient_obj.prenom} importé avec succès",
            resources_created=1,
            resources_updated=0
        )
    except FHIRImportError as e:
        try:
            from app.metrics import record_fhir_event
            record_fhir_event("inbound", "patient", "import", False, 400)
        except Exception:
            pass
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        try:
            from app.metrics import record_fhir_event
            record_fhir_event("inbound", "patient", "import", False, 500)
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'import: {str(e)}")


@router.post("/import/location", response_model=ImportResult)
async def import_location(
    location: Dict[str, Any] = Body(...),
    ej_id: int = Body(...),
    session: Session = Depends(get_session)
):
    """
    Importe une ressource Location FHIR.
    
    Args:
        location: Ressource Location FHIR
        ej_id: ID de l'entité juridique
        
    Returns:
        Résultat de l'import
        
    Raises:
        400: Ressource Location invalide
        404: Entité juridique non trouvée
    """
    # Vérifier que l'EJ existe
    ej = session.get(EntiteJuridique, ej_id)
    if not ej:
        raise HTTPException(status_code=404, detail="Entité juridique non trouvée")
    
    # Vérifier que c'est bien une Location
    if location.get("resourceType") != "Location":
        raise HTTPException(
            status_code=400,
            detail="La ressource doit être de type Location"
        )
    
    # Utiliser le convertisseur location
    try:
        import time as _time
        _start = _time.time()
        converter = FHIRToLocationConverter(session, ej)
        location_obj = converter.convert_location(location)
        # Metrics
        try:
            from app.metrics import record_fhir_event
            record_fhir_event("inbound", "location", "import", True, 200, _time.time() - _start)
        except Exception:
            pass

        return ImportResult(
            status="success",
            message=f"Location {location_obj.nom} importée avec succès (type: {location_obj.__class__.__name__})",
            resources_created=1,
            resources_updated=0
        )
    except FHIRImportError as e:
        try:
            from app.metrics import record_fhir_event
            record_fhir_event("inbound", "location", "import", False, 400)
        except Exception:
            pass
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        try:
            from app.metrics import record_fhir_event
            record_fhir_event("inbound", "location", "import", False, 500)
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'import: {str(e)}")


@router.post("/import/encounter", response_model=ImportResult)
async def import_encounter(
    encounter: Dict[str, Any] = Body(...),
    ej_id: int = Body(...),
    session: Session = Depends(get_session)
):
    """
    Importe une ressource Encounter FHIR.
    
    Args:
        encounter: Ressource Encounter FHIR
        ej_id: ID de l'entité juridique
        
    Returns:
        Résultat de l'import
        
    Raises:
        400: Ressource Encounter invalide
        404: Entité juridique non trouvée
    """
    # Vérifier que l'EJ existe
    ej = session.get(EntiteJuridique, ej_id)
    if not ej:
        raise HTTPException(status_code=404, detail="Entité juridique non trouvée")
    
    # Vérifier que c'est bien un Encounter
    if encounter.get("resourceType") != "Encounter":
        raise HTTPException(
            status_code=400,
            detail="La ressource doit être de type Encounter"
        )
    
    # Utiliser le convertisseur encounter
    try:
        import time as _time
        _start = _time.time()
        converter = FHIRToEncounterConverter(session)
        mouvement = converter.convert_encounter(encounter)
        # Metrics
        try:
            from app.metrics import record_fhir_event
            record_fhir_event("inbound", "encounter", "import", True, 200, _time.time() - _start)
        except Exception:
            pass

        return ImportResult(
            status="success",
            message=f"Encounter importé avec succès (mouvement {mouvement.type})",
            resources_created=1,
            resources_updated=0
        )
    except FHIRImportError as e:
        try:
            from app.metrics import record_fhir_event
            record_fhir_event("inbound", "encounter", "import", False, 400)
        except Exception:
            pass
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        try:
            from app.metrics import record_fhir_event
            record_fhir_event("inbound", "encounter", "import", False, 500)
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'import: {str(e)}")


@router.post("/validate/bundle", response_model=dict)
async def validate_bundle(
    bundle: Dict[str, Any] = Body(...),
    strict: bool = True,
    profile: str = "fr-core",
):
    """
    Valide un bundle FHIR sans l'importer.
    
    Vérifie que le bundle est conforme au standard FHIR et compatible
    avec le modèle de données de l'application.
    
    Args:
        bundle: Bundle FHIR à valider
        
    Returns:
        Résultat de la validation avec liste des erreurs/avertissements
    """
    validator = FHIRProfileValidator()
    report = validator.validate_bundle(bundle, strict=strict, profile=profile)
    return report.to_dict()