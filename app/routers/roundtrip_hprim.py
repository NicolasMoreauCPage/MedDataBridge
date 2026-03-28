"""Roundtrip HPRIM persistant pour génération, téléchargement et réintégration."""

from datetime import datetime

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, BackgroundTasks
from fastapi.responses import JSONResponse, Response
from sqlalchemy.orm import Session
from sqlmodel import select

from app.api.hprim_ccam import EmissionRequest, ReceptionRequest, emettre_actes_ccam, recevoir_actes_ccam
from app.db import get_session
from app.models.hprim_models import HprimMessage as StoredHprimMessage
from app.services.hprim import HprimService

router = APIRouter(prefix="/roundtrip-hprim", tags=["Roundtrip HPRIM"])

_roundtrip_hprim_service = HprimService()


def _store_roundtrip_message(
    db: Session,
    *,
    message_id: str,
    type_message: str,
    xml_content: str,
    status: str,
    source: str,
) -> StoredHprimMessage:
    stored = db.get(StoredHprimMessage, message_id)
    if not stored:
        stored = StoredHprimMessage(message_id=message_id, type_message=type_message, direction="roundtrip")

    stored.type_message = type_message
    stored.direction = "roundtrip"
    stored.status = status
    stored.filename = f"{message_id}.xml"
    stored.source = source
    stored.xml_content = xml_content
    stored.xml_size = len(xml_content)
    stored.updated_at = datetime.utcnow()
    db.add(stored)
    return stored


@router.post("/generate")
async def generate_hprim_xml(payload: dict, db: Session = Depends(get_session)):
    """Génère un XML HPRIM persistant à partir d'un payload structuré ou brut."""
    if payload.get("xml_content"):
        xml_content = str(payload["xml_content"])
        parse_result = _roundtrip_hprim_service.traiter_message_xml(xml_content)
        if parse_result.get("succes"):
            message = parse_result["message"]
            message_id = message.entete.message_id
            message_type = message.entete.message_type.value
            status = "validated"
        else:
            message_id = str(payload.get("message_id") or datetime.utcnow().strftime("RT%Y%m%d%H%M%S"))[:17]
            message_type = str(payload.get("type_message") or "roundtrip")
            status = "stored_with_errors"

        stored = _store_roundtrip_message(
            db,
            message_id=message_id,
            type_message=message_type,
            xml_content=xml_content,
            status=status,
            source="roundtrip-generate-raw",
        )
        db.commit()
        validation_summary = {
            "succes": bool(parse_result.get("succes")),
            "type_erreur": parse_result.get("type_erreur"),
            "erreur": parse_result.get("erreur"),
            "xsd_valid": parse_result.get("xsd_valid"),
            "schema_utilise": parse_result.get("schema_utilise"),
        }
        return JSONResponse(
            {
                "message_id": stored.message_id,
                "filename": stored.filename,
                "download_url": f"/roundtrip-hprim/download/{stored.filename}",
                "xml_size": stored.xml_size,
                "status": stored.status,
                "validation": validation_summary,
            }
        )

    try:
        request_model = EmissionRequest.model_validate(payload)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Payload roundtrip HPRIM invalide: {exc}") from exc

    response = await emettre_actes_ccam(request_model, BackgroundTasks(), db)
    return JSONResponse(
        {
            "message_id": response.message_id,
            "filename": f"{response.message_id}.xml",
            "download_url": f"/roundtrip-hprim/download/{response.message_id}.xml",
            "xml_size": response.xml_size,
            "validation_errors": response.validation_errors,
        }
    )


@router.get("/download/{filename}")
async def download_hprim_xml(filename: str, db: Session = Depends(get_session)):
    """Télécharge un XML HPRIM persistant."""
    message_id = filename[:-4] if filename.endswith(".xml") else filename
    statement = select(StoredHprimMessage).where(
        (StoredHprimMessage.filename == filename) | (StoredHprimMessage.message_id == message_id)
    )
    stored = db.exec(statement).first()
    if not stored:
        raise HTTPException(status_code=404, detail="Fichier HPRIM introuvable")

    return Response(
        content=stored.xml_content,
        media_type="application/xml",
        headers={"Content-Disposition": f'attachment; filename="{stored.filename or filename}"'},
    )


@router.post("/reintegrate")
async def reintegrate_hprim_xml(file: UploadFile = File(...), db: Session = Depends(get_session)):
    """Réintègre un XML HPRIM uploadé en repassant par le pipeline de réception."""
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Fichier HPRIM vide")

    xml_content = content.decode("iso-8859-1", errors="ignore")
    response = await recevoir_actes_ccam(
        ReceptionRequest(xml_content=xml_content, validate_only=False),
        db,
    )
    return {
        "status": "ok" if response.succes else "error",
        "filename": file.filename,
        "message_id": response.message_id,
        "actes_count": len(response.actes_recus),
        "erreurs": response.erreurs_traitement,
    }
