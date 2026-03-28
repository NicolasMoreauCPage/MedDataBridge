"""Routes UI legacy pour explorer et importer les messages HPRIM de cotation."""

from __future__ import annotations

import logging
from datetime import datetime
from decimal import Decimal
from typing import Any, Callable, Optional
from urllib.parse import quote_plus

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, func, or_, select

from app.db import get_session
from app.models import CCAMAct, Dossier, LPPAct, NGAPAct, Patient, UCDAct
from app.models.hprim_models import HprimMessage
from app.services.hprim.hprim_xml import HprimXmlService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/hprim-cotation", tags=["HPRIM Cotation"])
templates = Jinja2Templates(directory="app/templates")

VISIBLE_STATUSES = ("received", "validated", "stored", "stored_with_errors", "processed", "error")


def _safe_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return str(value)


def _safe_int(value: Any) -> Optional[int]:
    text = _safe_text(value)
    if not text:
        return None
    try:
        return int(text)
    except (TypeError, ValueError):
        return None


def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    text = _safe_text(value)
    if not text:
        return None
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def _parse_message_content(message: HprimMessage):
    return HprimXmlService().parse_xml(message.xml_content)


def _get_patient_identifier(message: HprimMessage, parsed_message: Any) -> Optional[str]:
    patient_identifier = _safe_text(message.patient_id)
    if patient_identifier:
        return patient_identifier
    patient = getattr(parsed_message, "patient", None)
    return _safe_text(getattr(patient, "identifiant_id", None))


def _get_nda(parsed_message: Any) -> Optional[str]:
    venue = getattr(parsed_message, "venue", None)
    return _safe_text(getattr(venue, "identifiant", None))


def _resolve_dossier(session: Session, message: HprimMessage, parsed_message: Any) -> Optional[Dossier]:
    nda = _get_nda(parsed_message)
    dossier_seq = _safe_int(nda)
    if dossier_seq is not None:
        dossier = session.exec(
            select(Dossier)
            .where(Dossier.dossier_seq == dossier_seq)
            .order_by(Dossier.admit_time.desc())
        ).first()
        if dossier:
            return dossier

    patient_identifier = _get_patient_identifier(message, parsed_message)
    if patient_identifier:
        return session.exec(
            select(Dossier)
            .join(Patient)
            .where(Patient.identifier == patient_identifier)
            .order_by(Dossier.admit_time.desc())
        ).first()

    return None


def _build_patient_info(parsed_message: Any, matched_patient: Optional[Patient]) -> dict[str, Any]:
    parsed_patient = getattr(parsed_message, "patient", None)
    return {
        "identifiant": (
            _safe_text(getattr(matched_patient, "identifier", None))
            if matched_patient
            else _safe_text(getattr(parsed_patient, "identifiant_id", None))
        ),
        "nom": (
            _safe_text(getattr(matched_patient, "nom", None))
            if matched_patient
            else _safe_text(getattr(parsed_patient, "nom", None))
        ),
        "prenom": (
            _safe_text(getattr(matched_patient, "prenom", None))
            if matched_patient
            else _safe_text(getattr(parsed_patient, "prenom", None))
        ),
        "date_naissance": (
            getattr(matched_patient, "birth_date", None)
            if matched_patient
            else _safe_text(getattr(parsed_patient, "date_naissance", None))
        ),
    }


def _build_venue_info(parsed_message: Any) -> Optional[dict[str, Any]]:
    venue = getattr(parsed_message, "venue", None)
    if not venue:
        return None
    identifiant = _safe_text(getattr(venue, "identifiant", None))
    libelle = _safe_text(getattr(venue, "libelle", None))
    if not identifiant and not libelle:
        return None
    return {
        "identifiant": identifiant,
        "libelle": libelle,
    }


def _serialize_ccam_act(acte: Any) -> dict[str, Any]:
    return {
        "code": _safe_text(getattr(acte, "code_acte", None)),
        "activite": _safe_text(getattr(acte, "code_activite", None)),
        "phase": _safe_text(getattr(acte, "code_phase", None)),
        "date": getattr(acte, "execute_date", None),
        "quantite": getattr(acte, "quantite", None),
        "executant": " ".join(
            filter(
                None,
                [
                    _safe_text(getattr(getattr(acte, "executant", None), "nom", None)),
                    _safe_text(getattr(getattr(acte, "executant", None), "prenom", None)),
                ],
            )
        )
        or None,
        "modificateurs": ", ".join(
            mod.code for mod in getattr(acte, "modificateurs", []) if getattr(mod, "code", None)
        ),
        "montant": _safe_float(getattr(getattr(acte, "montant", None), "valeur", None)),
    }


def _serialize_ngap_act(acte: Any) -> dict[str, Any]:
    return {
        "lettre_cle": _safe_text(getattr(acte, "lettre_cle", None)),
        "coefficient": _safe_float(getattr(acte, "coefficient", None)),
        "date": getattr(acte, "execute_date", None),
        "denombrement": getattr(acte, "denombrement", None),
        "executant": " ".join(
            filter(
                None,
                [
                    _safe_text(getattr(getattr(acte, "prestataire", None), "nom", None)),
                    _safe_text(getattr(getattr(acte, "prestataire", None), "prenom", None)),
                ],
            )
        )
        or None,
        "montant": _safe_float(getattr(getattr(acte, "montant", None), "valeur", None)),
    }


def _serialize_generic_act(acte: Any, code_attr: str, label_attr: str) -> dict[str, Any]:
    return {
        "code": _safe_text(getattr(acte, code_attr, None) or getattr(acte, "code", None)),
        "libelle": _safe_text(getattr(acte, label_attr, None) or getattr(acte, "libelle", None)),
        "date": getattr(acte, "execute_date", None),
        "quantite": _safe_float(getattr(acte, "quantite", None)),
        "montant": _safe_float(getattr(getattr(acte, "montant", None), "valeur", None)),
    }


def _compute_dossier_cotation_count(session: Session, dossier_id: int) -> int:
    counts = [
        session.exec(select(func.count(CCAMAct.id)).where(CCAMAct.dossier_id == dossier_id)).one(),
        session.exec(select(func.count(NGAPAct.id)).where(NGAPAct.dossier_id == dossier_id)).one(),
        session.exec(select(func.count(UCDAct.id)).where(UCDAct.dossier_id == dossier_id)).one(),
        session.exec(select(func.count(LPPAct.id)).where(LPPAct.dossier_id == dossier_id)).one(),
    ]
    return sum(int(count or 0) for count in counts)


def _refresh_dossier_flags(session: Session, dossier: Dossier) -> None:
    count = _compute_dossier_cotation_count(session, dossier.id)
    dossier.has_cotations = count > 0
    dossier.cotations_count = count
    session.add(dossier)


def _redirect_with_message(message_id: str, kind: str, text: str) -> RedirectResponse:
    return RedirectResponse(
        url=f"/hprim-cotation/message/{message_id}?{kind}={quote_plus(text)}",
        status_code=303,
    )


def _emit_created_entities(session: Session, entities: list[Any], entity_type: str) -> None:
    if not entities:
        return
    try:
        from app.services.emit_on_create import emit_to_senders_async

        for entity in entities:
            emit_to_senders_async(entity, entity_type, session, operation="insert")
    except Exception as exc:
        logger.warning("Erreur auto-emission HPRIM pour %s: %s", entity_type, exc)


def _import_acts(
    session: Session,
    message: HprimMessage,
    extract_acts: Callable[[Any], list[Any]],
    import_one: Callable[[Session, Dossier, Any], Optional[Any]],
    entity_type: str,
) -> tuple[int, Optional[str]]:
    parsed_message = _parse_message_content(message)
    dossier = _resolve_dossier(session, message, parsed_message)
    if not dossier:
        nda = _get_nda(parsed_message)
        patient_identifier = _get_patient_identifier(message, parsed_message)
        context = nda or patient_identifier or message.message_id
        return 0, f"Dossier introuvable pour le message {context}"

    acts = extract_acts(parsed_message)
    created_entities: list[Any] = []
    imported_count = 0
    for acte in acts:
        created = import_one(session, dossier, acte)
        if created is not None:
            created_entities.append(created)
            imported_count += 1

    _refresh_dossier_flags(session, dossier)
    session.commit()
    for entity in created_entities:
        session.refresh(entity)
    _emit_created_entities(session, created_entities, entity_type)
    return imported_count, None


def _import_one_ccam(session: Session, dossier: Dossier, acte: Any) -> Optional[CCAMAct]:
    existing = session.exec(
        select(CCAMAct)
        .where(CCAMAct.dossier_id == dossier.id)
        .where(CCAMAct.code_acte == getattr(acte, "code_acte", None))
        .where(CCAMAct.execute_date == getattr(acte, "execute_date", None))
    ).first()
    if existing:
        return None

    new_act = CCAMAct(
        dossier_id=dossier.id,
        identifiant_acte=_safe_text(getattr(acte, "identifiant", None)),
        code_acte=getattr(acte, "code_acte", None),
        code_activite=getattr(acte, "code_activite", None) or "01",
        code_phase=getattr(acte, "code_phase", None) or "00",
        execute_date=getattr(acte, "execute_date", None) or datetime.utcnow(),
        modificateurs=",".join(
            mod.code for mod in getattr(acte, "modificateurs", []) if getattr(mod, "code", None)
        )
        or None,
        quantite=getattr(acte, "quantite", None) or 1,
        montant_total=_safe_float(getattr(getattr(acte, "montant", None), "valeur", None)),
        commentaire=_safe_text(getattr(acte, "commentaire", None)),
        valide=bool(getattr(acte, "valide", False)),
        facture="oui" if getattr(acte, "facture", False) else "non",
    )
    session.add(new_act)
    return new_act


def _import_one_ngap(session: Session, dossier: Dossier, acte: Any) -> Optional[NGAPAct]:
    existing = session.exec(
        select(NGAPAct)
        .where(NGAPAct.dossier_id == dossier.id)
        .where(NGAPAct.lettre_cle == getattr(acte, "lettre_cle", None))
        .where(NGAPAct.execute_date == getattr(acte, "execute_date", None))
    ).first()
    if existing:
        return None

    new_act = NGAPAct(
        dossier_id=dossier.id,
        identifiant_acte=_safe_text(getattr(acte, "identifiant", None)),
        lettre_cle=getattr(acte, "lettre_cle", None),
        coefficient=_safe_float(getattr(acte, "coefficient", None)) or 1.0,
        denombrement=getattr(acte, "denombrement", None) or 1,
        execute_date=getattr(acte, "execute_date", None) or datetime.utcnow(),
        montant_total=_safe_float(getattr(getattr(acte, "montant", None), "valeur", None)),
        commentaire=_safe_text(getattr(acte, "commentaire", None)),
        valide=bool(getattr(acte, "valide", False)),
        facture="oui" if getattr(acte, "facture", False) else "non",
    )
    session.add(new_act)
    return new_act


def _import_one_ucd(session: Session, dossier: Dossier, acte: Any) -> Optional[UCDAct]:
    code_ucd = _safe_text(getattr(acte, "code_ucd", None) or getattr(acte, "code_cip", None) or getattr(acte, "code", None))
    execute_date = getattr(acte, "execute_date", None) or getattr(acte, "date", None) or datetime.utcnow()
    if not code_ucd:
        return None

    existing = session.exec(
        select(UCDAct)
        .where(UCDAct.dossier_id == dossier.id)
        .where(UCDAct.code_ucd == code_ucd)
        .where(UCDAct.execute_date == execute_date)
    ).first()
    if existing:
        return None

    new_act = UCDAct(
        dossier_id=dossier.id,
        code_ucd=code_ucd,
        denomination_libelle=_safe_text(
            getattr(acte, "denomination_libelle", None)
            or getattr(acte, "designation", None)
            or getattr(acte, "libelle", None)
        ),
        execute_date=execute_date,
        quantite=_safe_float(getattr(acte, "quantite", None)) or 1.0,
        montant_unitaire_facture_ttc=_safe_float(
            getattr(acte, "montant_unitaire_facture_ttc", None) or getattr(acte, "prix_unitaire", None)
        ),
        commentaire=_safe_text(getattr(acte, "commentaire", None)),
        valide=False,
        facture="non",
    )
    session.add(new_act)
    return new_act


def _import_one_lpp(session: Session, dossier: Dossier, acte: Any) -> Optional[LPPAct]:
    code_lpp = _safe_text(getattr(acte, "code_lpp", None) or getattr(acte, "code", None))
    execute_date = getattr(acte, "execute_date", None) or getattr(acte, "date", None) or datetime.utcnow()
    label = _safe_text(getattr(acte, "denomination_libelle", None) or getattr(acte, "libelle", None))
    if not code_lpp and not label:
        return None

    existing = session.exec(
        select(LPPAct)
        .where(LPPAct.dossier_id == dossier.id)
        .where(LPPAct.code_lpp == code_lpp)
        .where(LPPAct.execute_date == execute_date)
    ).first()
    if existing:
        return None

    new_act = LPPAct(
        dossier_id=dossier.id,
        execute_date=execute_date,
        code_lpp=code_lpp,
        denomination_libelle=label,
        montant_unitaire_facture_ttc=_safe_float(
            getattr(acte, "montant_unitaire_facture_ttc", None)
            or getattr(acte, "prix_unitaire", None)
            or getattr(acte, "montant_total", None)
        )
        or 0.0,
        quantite=_safe_int(getattr(acte, "quantite", None)) or 1,
        commentaire=_safe_text(getattr(acte, "commentaire", None)),
        valide=False,
        facture="non",
    )
    session.add(new_act)
    return new_act


@router.get("/", response_class=HTMLResponse)
async def hprim_messages_dashboard(
    request: Request,
    session: Session = Depends(get_session),
    status: Optional[str] = Query(None, description="Filtrer par statut"),
    search: Optional[str] = Query(None, description="Rechercher NDA/IPP/message"),
):
    query = select(HprimMessage)
    if status:
        query = query.where(HprimMessage.status == status)
    else:
        query = query.where(HprimMessage.status.in_(VISIBLE_STATUSES))

    if search:
        query = query.where(
            or_(
                HprimMessage.message_id.contains(search),
                HprimMessage.patient_id.contains(search),
                HprimMessage.filename.contains(search),
                HprimMessage.xml_content.contains(search),
            )
        )

    messages = session.exec(query.order_by(HprimMessage.created_at.desc()).limit(100)).all()

    stats = {
        "total": session.exec(select(func.count(HprimMessage.message_id))).one(),
        "received": session.exec(
            select(func.count(HprimMessage.message_id)).where(HprimMessage.status == "received")
        ).one(),
        "error": session.exec(
            select(func.count(HprimMessage.message_id)).where(HprimMessage.status == "error")
        ).one(),
    }

    return templates.TemplateResponse(
        "hprim/messages_dashboard.html",
        {
            "request": request,
            "messages": messages,
            "stats": stats,
            "current_status": status,
            "search_term": search,
        },
    )


@router.get("/message/{message_id}", response_class=HTMLResponse)
async def view_hprim_message(
    message_id: str,
    request: Request,
    session: Session = Depends(get_session),
    success: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
):
    message = session.get(HprimMessage, message_id)
    if not message:
        return templates.TemplateResponse(
            "error.html",
            {"request": request, "message": "Message HPRIM introuvable"},
            status_code=404,
        )

    patient_info = None
    venue_info = None
    dossier = None
    actes_info = {"ccam": [], "ngap": [], "ucd": [], "lpp": []}
    parse_error = error

    try:
        parsed_message = _parse_message_content(message)
        dossier = _resolve_dossier(session, message, parsed_message)
        matched_patient = session.get(Patient, dossier.patient_id) if dossier else None
        patient_info = _build_patient_info(parsed_message, matched_patient)
        venue_info = _build_venue_info(parsed_message)
        actes_info = {
            "ccam": [_serialize_ccam_act(acte) for acte in getattr(parsed_message, "actes_ccam", [])],
            "ngap": [_serialize_ngap_act(acte) for acte in getattr(parsed_message, "actes_ngap", [])],
            "ucd": [
                _serialize_generic_act(acte, "code_ucd", "denomination_libelle")
                for acte in getattr(parsed_message, "actes_ucd", [])
            ],
            "lpp": [
                _serialize_generic_act(acte, "code_lpp", "denomination_libelle")
                for acte in getattr(parsed_message, "actes_lpp", [])
            ],
        }
    except Exception as exc:
        logger.error("Erreur lors du parsing du message HPRIM %s: %s", message_id, exc, exc_info=True)
        parse_error = parse_error or str(exc)

    return templates.TemplateResponse(
        "hprim/message_detail.html",
        {
            "request": request,
            "message": message,
            "patient_info": patient_info,
            "venue_info": venue_info,
            "dossier": dossier,
            "ccam_actes": actes_info["ccam"],
            "ngap_actes": actes_info["ngap"],
            "ucd_actes": actes_info["ucd"],
            "lpp_actes": actes_info["lpp"],
            "error": parse_error,
            "success_message": success,
        },
    )


@router.get("/dossiers-avec-cotations", response_class=HTMLResponse)
async def dossiers_avec_cotations(request: Request, session: Session = Depends(get_session)):
    messages = session.exec(
        select(HprimMessage)
        .where(HprimMessage.status.in_(VISIBLE_STATUSES))
        .order_by(HprimMessage.created_at.desc())
        .limit(500)
    ).all()

    dossiers_by_key: dict[str, dict[str, Any]] = {}
    for message in messages:
        try:
            parsed_message = _parse_message_content(message)
        except Exception as exc:
            logger.debug("Impossible de parser le message %s: %s", message.message_id, exc)
            continue

        nda = _get_nda(parsed_message)
        patient_identifier = _get_patient_identifier(message, parsed_message)
        key = nda or patient_identifier or message.message_id
        dossier = _resolve_dossier(session, message, parsed_message)
        patient = session.get(Patient, dossier.patient_id) if dossier else None
        parsed_patient = getattr(parsed_message, "patient", None)

        current = dossiers_by_key.get(key)
        if current is None:
            current = {
                "nda": nda or patient_identifier or "N/A",
                "patient_nom": _safe_text(getattr(patient, "nom", None)) if patient else _safe_text(getattr(parsed_patient, "nom", None)),
                "patient_prenom": _safe_text(getattr(patient, "prenom", None)) if patient else _safe_text(getattr(parsed_patient, "prenom", None)),
                "message_count": 0,
                "last_message_date": message.created_at,
                "dossier_id": dossier.id if dossier else None,
            }
            dossiers_by_key[key] = current

        current["message_count"] += 1
        if message.created_at and (
            current["last_message_date"] is None or message.created_at > current["last_message_date"]
        ):
            current["last_message_date"] = message.created_at

    dossiers = sorted(
        dossiers_by_key.values(),
        key=lambda item: item["last_message_date"] or datetime.min,
        reverse=True,
    )

    return templates.TemplateResponse(
        "hprim/dossiers_cotations.html",
        {"request": request, "dossiers": dossiers},
    )


@router.post("/message/{message_id}/import-ccam")
async def import_ccam_acts(message_id: str, session: Session = Depends(get_session)):
    try:
        message = session.get(HprimMessage, message_id)
        if not message:
            return _redirect_with_message(message_id, "error", "Message HPRIM introuvable")

        imported_count, import_error = _import_acts(
            session,
            message,
            lambda parsed: list(getattr(parsed, "actes_ccam", []) or []),
            _import_one_ccam,
            "ccam_act",
        )
        if import_error:
            session.rollback()
            return _redirect_with_message(message_id, "error", import_error)
        return _redirect_with_message(
            message_id,
            "success",
            f"Import reussi: {imported_count} acte(s) CCAM importe(s)",
        )
    except Exception as exc:
        logger.error("Erreur lors de l'import CCAM du message %s: %s", message_id, exc, exc_info=True)
        session.rollback()
        return _redirect_with_message(message_id, "error", f"Erreur: {exc}")


@router.post("/message/{message_id}/import-ngap")
async def import_ngap_acts(message_id: str, session: Session = Depends(get_session)):
    try:
        message = session.get(HprimMessage, message_id)
        if not message:
            return _redirect_with_message(message_id, "error", "Message HPRIM introuvable")

        imported_count, import_error = _import_acts(
            session,
            message,
            lambda parsed: list(getattr(parsed, "actes_ngap", []) or []),
            _import_one_ngap,
            "ngap_act",
        )
        if import_error:
            session.rollback()
            return _redirect_with_message(message_id, "error", import_error)
        return _redirect_with_message(
            message_id,
            "success",
            f"Import reussi: {imported_count} acte(s) NGAP importe(s)",
        )
    except Exception as exc:
        logger.error("Erreur lors de l'import NGAP du message %s: %s", message_id, exc, exc_info=True)
        session.rollback()
        return _redirect_with_message(message_id, "error", f"Erreur: {exc}")


@router.post("/message/{message_id}/import-ucd")
async def import_ucd_acts(message_id: str, session: Session = Depends(get_session)):
    try:
        message = session.get(HprimMessage, message_id)
        if not message:
            return _redirect_with_message(message_id, "error", "Message HPRIM introuvable")

        imported_count, import_error = _import_acts(
            session,
            message,
            lambda parsed: list(getattr(parsed, "actes_ucd", []) or []),
            _import_one_ucd,
            "ucd_act",
        )
        if import_error:
            session.rollback()
            return _redirect_with_message(message_id, "error", import_error)
        return _redirect_with_message(
            message_id,
            "success",
            f"Import reussi: {imported_count} acte(s) UCD importe(s)",
        )
    except Exception as exc:
        logger.error("Erreur lors de l'import UCD du message %s: %s", message_id, exc, exc_info=True)
        session.rollback()
        return _redirect_with_message(message_id, "error", f"Erreur: {exc}")


@router.post("/message/{message_id}/import-lpp")
async def import_lpp_acts(message_id: str, session: Session = Depends(get_session)):
    try:
        message = session.get(HprimMessage, message_id)
        if not message:
            return _redirect_with_message(message_id, "error", "Message HPRIM introuvable")

        imported_count, import_error = _import_acts(
            session,
            message,
            lambda parsed: list(getattr(parsed, "actes_lpp", []) or []),
            _import_one_lpp,
            "lpp_act",
        )
        if import_error:
            session.rollback()
            return _redirect_with_message(message_id, "error", import_error)
        return _redirect_with_message(
            message_id,
            "success",
            f"Import reussi: {imported_count} acte(s) LPP importe(s)",
        )
    except Exception as exc:
        logger.error("Erreur lors de l'import LPP du message %s: %s", message_id, exc, exc_info=True)
        session.rollback()
        return _redirect_with_message(message_id, "error", f"Erreur: {exc}")
