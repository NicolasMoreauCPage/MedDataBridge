"""Roundtrip HPRIM persistant pour génération, téléchargement et réintégration."""

from datetime import datetime
from decimal import Decimal
import json
from uuid import uuid4

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, BackgroundTasks
from fastapi.responses import JSONResponse, Response
from sqlalchemy.orm import Session
from sqlmodel import select

from app.api.hprim_ccam import ReceptionRequest, recevoir_actes_ccam
from app.db import get_session
from app.models.hprim_models import HprimMessage as StoredHprimMessage, HprimExchangeAct
from app.hprim_models import (
    HprimActeCCAM, HprimActeLPP, HprimActeNGAP, HprimActeUCD, HprimAction,
    HprimCodeLPP, HprimEnteteMessage, HprimLPP, HprimMessage,
    HprimMessageType, HprimPatient, HprimProfessionnel, HprimUCD,
)
from app.services.hprim import HprimService

router = APIRouter(prefix="/roundtrip-hprim", tags=["Roundtrip HPRIM"])

_roundtrip_hprim_service = HprimService()


def _as_datetime(value: object) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            pass
    return datetime.utcnow()


def _build_message(payload: dict) -> tuple[HprimMessage, str]:
    """Construit le contrat commun CCAM/NGAP/UCD/LPP du roundtrip.

    Les valeurs de contexte restent explicites lorsqu'elles sont fournies, avec
    des valeurs de démonstration uniquement pour l'ancien payload minimal de
    qualification (`type` + `code`).
    """
    acts_payload = payload.get("actes") or []
    act_data = acts_payload[0] if isinstance(acts_payload, list) and acts_payload else payload
    act_type = str(payload.get("type_acte") or payload.get("type") or ("CCAM" if acts_payload else "")).upper()
    if act_type not in {"CCAM", "NGAP", "UCD", "LPP"}:
        raise ValueError("type_acte doit être CCAM, NGAP, UCD ou LPP")
    message_id = str(payload.get("message_id") or uuid4().hex[:12].upper())[:12]
    patient_data = payload.get("patient") or {}
    actor_data = payload.get("acteur") or {}
    patient = HprimPatient(
        identifiant_id=str(patient_data.get("identifiant_id") or "PATIENT001"),
        identifiant_clef=str(patient_data.get("identifiant_clef") or "CLEF"),
        nom=str(patient_data.get("nom") or "DUPONT"),
        prenom=str(patient_data.get("prenom") or "Jean"),
        date_naissance=patient_data.get("date_naissance") or "1980-01-01",
        sexe=patient_data.get("sexe") or "M",
    )
    actor = HprimProfessionnel(
        nom=str(actor_data.get("nom") or "MARTIN"),
        prenom=str(actor_data.get("prenom") or "Marie"),
        numero_rpps=str(actor_data.get("numero_rpps") or "12345678901"),
    )
    entete = HprimEnteteMessage(
        emetteur_id=str(payload.get("emetteur_id") or "123456789")[:10],
        emetteur_nom=str(payload.get("emetteur_nom") or "HOPITAL TEST")[:35],
        destinataire_id=str(payload.get("destinataire_id") or "987654321")[:10],
        destinataire_nom=str(payload.get("destinataire_nom") or "DESTINATAIRE TEST")[:35],
        date_emission=_as_datetime(payload.get("date_emission")),
        message_id=message_id,
        message_type=HprimMessageType.EVENEMENTS_SERVEUR_ACTES,
    )
    code = str(act_data.get("code") or act_data.get("code_acte") or "")
    if not code:
        raise ValueError("code est obligatoire")
    act_id = str(act_data.get("act_id") or f"A{message_id[-10:]}")[:17]
    quantity = Decimal(str(act_data.get("quantite", act_data.get("quantity", 1))))
    unit_price = Decimal(str(act_data.get("prix_unitaire", act_data.get("montant", 0))))
    total = Decimal(str(act_data.get("montant_total", unit_price * quantity)))
    if total != unit_price * quantity:
        raise ValueError("montant_total doit être égal à prix_unitaire × quantite")

    message = HprimMessage(entete=entete, patient=patient, acteur=actor)
    if act_type == "CCAM":
        message.actes_ccam = [HprimActeCCAM(
            identifiant=act_id, code_acte=code,
            code_activite=str(act_data.get("code_activite") or "01").zfill(2),
            code_phase=str(act_data.get("code_phase") or "00").zfill(2),
            execute_date=_as_datetime(act_data.get("date_execution")), executant=actor,
            quantite=int(quantity), action=HprimAction.CREATION,
        )]
    elif act_type == "NGAP":
        message.actes_ngap = [HprimActeNGAP(
            identifiant=act_id, lettre_cle=code, coefficient=Decimal(str(act_data.get("coefficient", 1))),
            execute_date=_as_datetime(act_data.get("date_execution")), prestataire=actor,
            action=HprimAction.CREATION,
        )]
    elif act_type == "LPP":
        message.actes_lpp = HprimActeLPP(
            identifiant=act_id,
            lpps=[HprimLPP(HprimCodeLPP(code), unit_price, total, act_data.get("libelle"), int(quantity))],
        )
    else:
        message.actes_ucd = HprimActeUCD(
            identifiant=act_id,
            ucds=[HprimUCD(code, str(act_data.get("libelle") or "Produit UCD"), quantity, unit_price, total)],
        )
    return message, act_type


def _act_projection(act_type: str, act: object) -> tuple[str, str, dict]:
    values = vars(act)
    # Le parseur des flux historiques retourne les UCD avec ``code_ucd`` ou
    # ``code_commercial`` (et non le champ ``code`` des UCD générées par
    # l'IHM). Les deux représentations décrivent le même code de produit et
    # doivent être persistées de façon uniforme pendant un roundtrip.
    code = (
        values.get("code_acte") or values.get("lettre_cle") or values.get("code_lpp")
        or values.get("code_ucd") or values.get("code_commercial") or values.get("code")
    )
    if isinstance(values.get("code"), HprimCodeLPP):
        code = values["code"].code
    if not code:
        raise ValueError(f"Acte HPRIM {act_type} sans code")
    act_id = str(values.get("identifiant") or f"{act_type}-{code}")
    projection = {key: str(value) if isinstance(value, (datetime, Decimal)) else value for key, value in values.items()}
    return act_id, str(code), projection


def _persist_exchange_acts(db: Session, message: HprimMessage) -> int:
    count = 0
    lpp_acts = (
        message.actes_lpp.lpps if isinstance(message.actes_lpp, HprimActeLPP)
        else message.actes_lpp or []
    )
    ucd_acts = (
        message.actes_ucd.ucds if isinstance(message.actes_ucd, HprimActeUCD)
        else message.actes_ucd or []
    )
    for act_type, acts in (
        ("CCAM", message.actes_ccam),
        ("NGAP", message.actes_ngap),
        ("LPP", lpp_acts),
        ("UCD", ucd_acts),
    ):
        for act in acts or []:
            act_id, code, projection = _act_projection(act_type, act)
            key = f"{message.entete.message_id}:{act_type}:{act_id}"
            stored = db.get(HprimExchangeAct, key) or HprimExchangeAct(id=key, message_id=message.entete.message_id)
            stored.patient_id = message.patient.identifiant_id
            stored.act_type = act_type
            stored.code = code
            stored.action = str(getattr(act, "action", "creation"))
            stored.payload_json = json.dumps(projection, default=str, ensure_ascii=False, sort_keys=True)
            stored.updated_at = datetime.utcnow()
            db.add(stored)
            count += 1
    return count


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
        message, act_type = _build_message(payload)
        validation_errors = _roundtrip_hprim_service.valider_message(message)
        if validation_errors:
            raise ValueError("; ".join(error.message for error in validation_errors))
        xml_content = _roundtrip_hprim_service.generer_xml(message, valider=False)
        xsd_valid, xsd_errors = _roundtrip_hprim_service.validate_generated_xml(xml_content, message.entete.message_type)
        if not xsd_valid:
            raise ValueError("; ".join(xsd_errors))
        _store_roundtrip_message(
            db, message_id=message.entete.message_id, type_message=act_type,
            xml_content=xml_content, status="validated", source="roundtrip-generate-structured",
        )
        _persist_exchange_acts(db, message)
        db.commit()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Payload roundtrip HPRIM invalide: {exc}") from exc
    return JSONResponse(
        {
            "message_id": message.entete.message_id,
            "filename": f"{message.entete.message_id}.xml",
            "download_url": f"/roundtrip-hprim/download/{message.entete.message_id}.xml",
            "xml_size": len(xml_content),
            "type_acte": act_type,
            "validation_errors": [],
            "validation": {"succes": True, "xsd_valid": True, "schema_utilise": "evenements_serveur_actes"},
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
    result = _roundtrip_hprim_service.traiter_message_xml(xml_content)
    if not result.get("succes"):
        return {"status": "error", "filename": file.filename, "message_id": None, "actes_count": 0,
                "erreurs": [result.get("erreur", "Erreur HPRIM inconnue")]}
    message = result["message"]
    _store_roundtrip_message(
        db, message_id=message.entete.message_id, type_message=message.entete.message_type.value,
        xml_content=xml_content, status="received", source="roundtrip-reintegrate",
    )
    actes_count = _persist_exchange_acts(db, message)
    db.commit()
    response = await recevoir_actes_ccam(ReceptionRequest(xml_content=xml_content, validate_only=False), db)
    return {
        "status": "ok" if response.succes else "error",
        "filename": file.filename,
        "message_id": message.entete.message_id,
        "actes_count": actes_count,
        "erreurs": response.erreurs_traitement,
    }
