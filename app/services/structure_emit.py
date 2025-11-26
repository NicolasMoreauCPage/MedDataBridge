import time

async def _emit_mfn_entity(entity, session: Session, ght_context_id=None) -> None:
    """Émet un message MFN^M05 pour une entité individuelle vers les endpoints MLLP."""
    from app.services.mfn_structure import generate_mfn_message_for_entity
    mfn = generate_mfn_message_for_entity(session, entity)
    _, mllp_senders = _get_senders(session, ght_context_id=ght_context_id)
    for endpoint in mllp_senders:
        correlation_id = getattr(entity, "correlation_id", None)
        existing_log = session.exec(
            select(MessageLog)
            .where(MessageLog.endpoint_id == endpoint.id)
            .where(MessageLog.kind == "MLLP")
            .where(MessageLog.direction == "out")
            .where(MessageLog.correlation_id == correlation_id)
        ).first() if correlation_id else None
        retry = 0
        max_retry = 3
        while retry < max_retry:
            ack = ""
            status = "generated"
            try:
                ack, status = await send_mllp(endpoint, mfn)
                if existing_log:
                    existing_log.payload = mfn
                    existing_log.ack_payload = ack
                    existing_log.status = status
                    existing_log.created_at = datetime.utcnow()
                    log = existing_log
                else:
                    log = MessageLog(
                        direction="out",
                        kind="MLLP",
                        endpoint_id=endpoint.id,
                        payload=mfn,
                        ack_payload=ack,
                        status=status,
                        message_type="MFN^M05",
                        correlation_id=correlation_id,
                    )
                    session.add(log)
                break
            except Exception as exc:
                retry += 1
                if existing_log:
                    existing_log.payload = mfn
                    existing_log.ack_payload = str(exc)
                    existing_log.status = "error"
                    existing_log.created_at = datetime.utcnow()
                    log = existing_log
                else:
                    log = MessageLog(
                        direction="out",
                        kind="MLLP",
                        endpoint_id=endpoint.id,
                        payload=mfn,
                        ack_payload=str(exc),
                        status="error",
                        message_type="MFN^M05",
                        correlation_id=correlation_id,
                    )
                    session.add(log)
                if retry < max_retry:
                    time.sleep(60)
"""Emission des messages Structure (FHIR Location et HL7 MFN) après modifications.

Cette couche envoie:
- FHIR: Bundle transaction avec PUT/DELETE Location/{id} vers les endpoints FHIR "sender"
- HL7: message MFN^M05 (snapshot complet) vers les endpoints MLLP "sender"

Utilisation:
- await emit_structure_change(entity, session, operation="insert|update")
- await emit_structure_delete(entity_id, session)
"""

from __future__ import annotations

import json
import logging

from datetime import datetime
from typing import Tuple

from sqlmodel import Session, select

from app.models_endpoints import SystemEndpoint, MessageLog
from app.services.fhir_structure import entity_to_fhir_location
from app.services.fhir_organization import organization_to_bundle
from app.services.fhir_transport import post_fhir_bundle
from app.services.mllp import send_mllp
from app.services.mfn_structure import generate_mfn_message
from app.services.mfn_organization import generate_mfn_organization_message, generate_mfn_organization_delete

logger = logging.getLogger(__name__)


def _get_senders(session: Session, ght_context_id=None):
    query = select(SystemEndpoint).where(SystemEndpoint.role == "sender")
    if ght_context_id is not None:
        query = query.where(SystemEndpoint.ght_context_id == ght_context_id)
    endpoints = session.exec(query).all()
    fhir_senders = [e for e in endpoints if (e.kind or "").lower() == "fhir" and e.is_enabled and getattr(e, "emit_fhir_structure", True)]
    mllp_senders = [e for e in endpoints if (e.kind or "").upper() == "MLLP" and e.is_enabled and getattr(e, "emit_hl7_mfn", True)]
    return fhir_senders, mllp_senders


async def _emit_organization_upsert(entity, session: Session, ght_context_id=None) -> None:
    """Émet FHIR Organization vers les endpoints sender."""
    import time
    from datetime import datetime
    bundle = organization_to_bundle(entity, session, method="PUT")
    fhir_senders, _ = _get_senders(session, ght_context_id=ght_context_id)
    for endpoint in fhir_senders:
        base = endpoint.base_url or endpoint.host or ""
        log = None
        # Use correlation_id for deduplication if available
        correlation_id = getattr(entity, "correlation_id", None)
        with session.no_autoflush:
            if correlation_id:
                existing_log = session.exec(
                    select(MessageLog)
                    .where(MessageLog.endpoint_id == endpoint.id)
                    .where(MessageLog.kind == "FHIR")
                    .where(MessageLog.direction == "out")
                    .where(MessageLog.correlation_id == correlation_id)
                ).first()
            else:
                existing_log = session.exec(
                    select(MessageLog)
                    .where(MessageLog.endpoint_id == endpoint.id)
                    .where(MessageLog.kind == "FHIR")
                    .where(MessageLog.status.in_(["error", "pending"]))
                    .order_by(MessageLog.created_at.desc())
                ).first()
            if not base:
                if existing_log:
                    existing_log.payload = json.dumps(bundle, ensure_ascii=False)
                    existing_log.ack_payload = "Endpoint sans host/base_url"
                    existing_log.status = "error"
                    existing_log.created_at = datetime.utcnow()
                    log = existing_log
                else:
                    log = MessageLog(
                        direction="out",
                        kind="FHIR",
                        endpoint_id=endpoint.id,
                        payload=json.dumps(bundle, ensure_ascii=False),
                        ack_payload="Endpoint sans host/base_url",
                        status="error",
                        correlation_id=correlation_id,
                    )
                    session.add(log)
                continue
            retry = 0
            max_retry = 3
            while retry < max_retry:
                try:
                    status_code, response = await post_fhir_bundle(base, bundle)
                    if existing_log:
                        existing_log.payload = json.dumps(bundle, ensure_ascii=False)
                        existing_log.ack_payload = json.dumps(response or {}, ensure_ascii=False)
                        existing_log.status = "sent" if 200 <= status_code < 300 else "error"
                        existing_log.created_at = datetime.utcnow()
                        log = existing_log
                    else:
                        log = MessageLog(
                            direction="out",
                            kind="FHIR",
                            endpoint_id=endpoint.id,
                            payload=json.dumps(bundle, ensure_ascii=False),
                            ack_payload=json.dumps(response or {}, ensure_ascii=False),
                            status="sent" if 200 <= status_code < 300 else "error",
                            correlation_id=correlation_id,
                        )
                        session.add(log)
                    break
                except Exception as exc:
                    retry += 1
                    if existing_log:
                        existing_log.payload = json.dumps(bundle, ensure_ascii=False)
                        existing_log.ack_payload = str(exc)
                        existing_log.status = "error"
                        existing_log.created_at = datetime.utcnow()
                        log = existing_log
                    else:
                        log = MessageLog(
                            direction="out",
                            kind="FHIR",
                            endpoint_id=endpoint.id,
                            payload=json.dumps(bundle, ensure_ascii=False),
                            ack_payload=str(exc),
                            status="error",
                            correlation_id=correlation_id,
                        )
                        session.add(log)
                    if retry < max_retry:
                        time.sleep(60)


async def _emit_organization_delete(entity_id: int, finess_ej: str, session: Session) -> None:
    """Émet FHIR Organization DELETE vers les endpoints sender."""
    from app.models_structure import EntiteJuridique
    bundle = {
        "resourceType": "Bundle",
        "type": "transaction",
        "entry": [
            {"request": {"method": "DELETE", "url": f"Organization/{entity_id}"}}
        ],
    }
    fhir_senders, _ = _get_senders(session)
    for endpoint in fhir_senders:
        base = endpoint.base_url or endpoint.host or ""
        with session.no_autoflush:
            if not base:
                log = MessageLog(
                    direction="out",
                    kind="FHIR",
                    endpoint_id=endpoint.id,
                    payload=json.dumps(bundle, ensure_ascii=False),
                    ack_payload="Endpoint sans host/base_url",
                    status="error",
                )
                session.add(log)
                continue
            try:
                status_code, response = await post_fhir_bundle(base, bundle)
                log = MessageLog(
                    direction="out",
                    kind="FHIR",
                    endpoint_id=endpoint.id,
                    payload=json.dumps(bundle, ensure_ascii=False),
                    ack_payload=json.dumps(response or {}, ensure_ascii=False),
                    status="sent" if 200 <= status_code < 300 else "error",
                )
            except Exception as exc:  # noqa: BLE001
                log = MessageLog(
                    direction="out",
                    kind="FHIR",
                    endpoint_id=endpoint.id,
                    payload=json.dumps(bundle, ensure_ascii=False),
                    ack_payload=str(exc),
                    status="error",
                )
            session.add(log)


async def _emit_mfn_organization(entity, session: Session, ght_context_id=None) -> None:
    """Génère et envoie un message MFN M05 pour Organization aux endpoints MLLP."""
    mfn = generate_mfn_organization_message(session, ej=entity)
    if ght_context_id is None:
        ght_context_id = getattr(entity, "ght_context_id", None)
    _, mllp_senders = _get_senders(session, ght_context_id=ght_context_id)
    for endpoint in mllp_senders:
        correlation_id = getattr(entity, "correlation_id", None)
        with session.no_autoflush:
            ack = ""
            status = "generated"
            if correlation_id:
                existing_log = session.exec(
                    select(MessageLog)
                    .where(MessageLog.endpoint_id == endpoint.id)
                    .where(MessageLog.kind == "MLLP")
                    .where(MessageLog.direction == "out")
                    .where(MessageLog.correlation_id == correlation_id)
                ).first()
            else:
                existing_log = None
            try:
                if not (endpoint.host and endpoint.port):
                    raise ValueError("Endpoint MLLP incomplet (host/port)")
                ack = await send_mllp(endpoint.host, endpoint.port, mfn)
                # Correction : parser l'ACK pour détecter AE/AR
                msa = next((seg for seg in ack.split('\r') if seg.startswith('MSA|')), None)
                ack_code = msa.split('|')[1] if msa and len(msa.split('|')) > 1 else "AA"
                if ack_code in ("AE", "AR"):
                    status = "error"
                else:
                    status = "sent"
            except Exception as exc:  # noqa: BLE001
                status = "error"
                ack = str(exc)
            if existing_log:
                existing_log.payload = mfn
                existing_log.ack_payload = ack
                existing_log.status = status
                existing_log.message_type = "MFN^M05"
                existing_log.created_at = datetime.utcnow()
            else:
                log = MessageLog(
                    direction="out",
                    kind="MLLP",
                    endpoint_id=endpoint.id,
                    payload=mfn,
                    ack_payload=ack,
                    status=status,
                    message_type="MFN^M05",
                    correlation_id=correlation_id,
                )
                session.add(log)


async def _emit_mfn_organization_delete(entity_id: int, finess_ej: str, session: Session) -> None:
    """Génère et envoie un message MFN M05 DELETE pour Organization."""
    mfn = generate_mfn_organization_delete(entity_id, finess_ej)
    _, mllp_senders = _get_senders(session)
    for endpoint in mllp_senders:
        correlation_id = None  # MFN delete may not have entity.correlation_id
        with session.no_autoflush:
            ack = ""
            status = "generated"
            # Try to deduplicate by entity_id if possible (for delete, correlation_id may not exist)
            existing_log = session.exec(
                select(MessageLog)
                .where(MessageLog.endpoint_id == endpoint.id)
                .where(MessageLog.kind == "MLLP")
                .where(MessageLog.direction == "out")
                .where(MessageLog.message_type == "MFN^M05")
                .where(MessageLog.payload.contains(str(entity_id)))
            ).first()
            try:
                if not (endpoint.host and endpoint.port):
                    raise ValueError("Endpoint MLLP incomplet (host/port)")
                ack = await send_mllp(endpoint.host, endpoint.port, mfn)
                status = "sent"
            except Exception as exc:  # noqa: BLE001
                status = "error"
                ack = str(exc)
            if existing_log:
                existing_log.payload = mfn
                existing_log.ack_payload = ack
                existing_log.status = status
                existing_log.message_type = "MFN^M05"
                existing_log.created_at = datetime.utcnow()
            else:
                log = MessageLog(
                    direction="out",
                    kind="MLLP",
                    endpoint_id=endpoint.id,
                    payload=mfn,
                    ack_payload=ack,
                    status=status,
                    message_type="MFN^M05",
                )
                session.add(log)


async def _emit_fhir_upsert(entity, session: Session, ght_context_id=None) -> None:
    import time
    from datetime import datetime
    resource = entity_to_fhir_location(entity, session)
    bundle = {
        "resourceType": "Bundle",
        "type": "transaction",
        "entry": [
            {
                "resource": resource,
                "request": {"method": "PUT", "url": f"Location/{entity.id}"},
            }
        ],
    }
    fhir_senders, _ = _get_senders(session, ght_context_id=ght_context_id)
    if not fhir_senders:
        logger.info(f"[structure_emit] Aucun endpoint FHIR configuré/activé pour GHT/EJ (ght_context_id={ght_context_id}), émission ignorée.")
        return
    for endpoint in fhir_senders:
        base = endpoint.base_url or endpoint.host or ""
        log = None
        correlation_id = getattr(entity, "correlation_id", None)
        if correlation_id:
            existing_log = session.exec(
                select(MessageLog)
                .where(MessageLog.endpoint_id == endpoint.id)
                .where(MessageLog.kind == "FHIR")
                .where(MessageLog.direction == "out")
                .where(MessageLog.correlation_id == correlation_id)
            ).first()
        else:
            existing_log = session.exec(
                select(MessageLog)
                .where(MessageLog.endpoint_id == endpoint.id)
                .where(MessageLog.kind == "FHIR")
                .where(MessageLog.status.in_(["error", "pending"]))
                .order_by(MessageLog.created_at.desc())
            ).first()
            if not base:
                if existing_log:
                    existing_log.payload = json.dumps(bundle, ensure_ascii=False)
                    existing_log.ack_payload = "Endpoint sans host/base_url"
                    existing_log.status = "error"
                    existing_log.created_at = datetime.utcnow()
                    log = existing_log
                else:
                    log = MessageLog(
                        direction="out",
                        kind="FHIR",
                        endpoint_id=endpoint.id,
                        payload=json.dumps(bundle, ensure_ascii=False),
                        ack_payload="Endpoint sans host/base_url",
                        status="error",
                        correlation_id=correlation_id,
                    )
                    session.add(log)
                continue
            retry = 0
            max_retry = 3
            while retry < max_retry:
                try:
                    status_code, response = await post_fhir_bundle(base, bundle)
                    if existing_log:
                        existing_log.payload = json.dumps(bundle, ensure_ascii=False)
                        existing_log.ack_payload = json.dumps(response or {}, ensure_ascii=False)
                        existing_log.status = "sent" if 200 <= status_code < 300 else "error"
                        existing_log.created_at = datetime.utcnow()
                        log = existing_log
                    else:
                        log = MessageLog(
                            direction="out",
                            kind="FHIR",
                            endpoint_id=endpoint.id,
                            payload=json.dumps(bundle, ensure_ascii=False),
                            ack_payload=json.dumps(response or {}, ensure_ascii=False),
                            status="sent" if 200 <= status_code < 300 else "error",
                            correlation_id=correlation_id,
                        )
                        session.add(log)
                    break
                except Exception as exc:
                    retry += 1
                    if existing_log:
                        existing_log.payload = json.dumps(bundle, ensure_ascii=False)
                        existing_log.ack_payload = str(exc)
                        existing_log.status = "error"
                        existing_log.created_at = datetime.utcnow()
                        log = existing_log
                    else:
                        log = MessageLog(
                            direction="out",
                            kind="FHIR",
                            endpoint_id=endpoint.id,
                            payload=json.dumps(bundle, ensure_ascii=False),
                            ack_payload=str(exc),
                            status="error",
                            correlation_id=correlation_id,
                        )
                        session.add(log)
                    if retry < max_retry:
                        time.sleep(60)


async def _emit_fhir_delete(entity_id: int, session: Session) -> None:
    import time
    from datetime import datetime
    bundle = {
        "resourceType": "Bundle",
        "type": "transaction",
        "entry": [
            {"request": {"method": "DELETE", "url": f"Location/{entity_id}"}}
        ],
    }
    fhir_senders, _ = _get_senders(session)
    for endpoint in fhir_senders:
        base = endpoint.base_url or endpoint.host or ""
        log = None
        existing_log = session.exec(
            select(MessageLog)
            .where(MessageLog.endpoint_id == endpoint.id)
            .where(MessageLog.kind == "FHIR")
            .where(MessageLog.status.in_(["error", "pending"]))
            .order_by(MessageLog.created_at.desc())
        ).first()
        if not base:
            if existing_log:
                existing_log.payload = json.dumps(bundle, ensure_ascii=False)
                existing_log.ack_payload = "Endpoint sans host/base_url"
                existing_log.status = "error"
                existing_log.created_at = datetime.utcnow()
                log = existing_log
            else:
                log = MessageLog(
                    direction="out",
                    kind="FHIR",
                    endpoint_id=endpoint.id,
                    payload=json.dumps(bundle, ensure_ascii=False),
                    ack_payload="Endpoint sans host/base_url",
                    status="error",
                )
                session.add(log)
            continue
        retry = 0
        max_retry = 3
        while retry < max_retry:
            try:
                status_code, response = await post_fhir_bundle(base, bundle)
                if existing_log:
                    existing_log.payload = json.dumps(bundle, ensure_ascii=False)
                    existing_log.ack_payload = json.dumps(response or {}, ensure_ascii=False)
                    existing_log.status = "sent" if 200 <= status_code < 300 else "error"
                    existing_log.created_at = datetime.utcnow()
                    log = existing_log
                else:
                    log = MessageLog(
                        direction="out",
                        kind="FHIR",
                        endpoint_id=endpoint.id,
                        payload=json.dumps(bundle, ensure_ascii=False),
                        ack_payload=json.dumps(response or {}, ensure_ascii=False),
                        status="sent" if 200 <= status_code < 300 else "error",
                    )
                    session.add(log)
                break
            except Exception as exc:
                retry += 1
                if existing_log:
                    existing_log.payload = json.dumps(bundle, ensure_ascii=False)
                    existing_log.ack_payload = str(exc)
                    existing_log.status = "error"
                    existing_log.created_at = datetime.utcnow()
                    log = existing_log
                else:
                    log = MessageLog(
                        direction="out",
                        kind="FHIR",
                        endpoint_id=endpoint.id,
                        payload=json.dumps(bundle, ensure_ascii=False),
                        ack_payload=str(exc),
                        status="error",
                    )
                    session.add(log)
                if retry < max_retry:
                    time.sleep(60)


async def _emit_mfn_snapshot(session: Session, ght_context_id=None) -> None:
    import time
    from datetime import datetime
    mfn = generate_mfn_message(session)
    _, mllp_senders = _get_senders(session, ght_context_id=ght_context_id)
    for endpoint in mllp_senders:
        correlation_id = None  # MFN snapshot may not have correlation_id
        # Try to deduplicate by endpoint and message_type
        existing_log = session.exec(
            select(MessageLog)
            .where(MessageLog.endpoint_id == endpoint.id)
            .where(MessageLog.kind == "MLLP")
            .where(MessageLog.direction == "out")
            .where(MessageLog.message_type == "MFN^M05")
        ).first()
        retry = 0
        max_retry = 3
        while retry < max_retry:
            ack = ""
            status = "generated"
            try:
                if not (endpoint.host and endpoint.port):
                    raise ValueError("Endpoint MLLP incomplet (host/port)")
                ack = await send_mllp(endpoint.host, endpoint.port, mfn)
                status = "sent"
                if existing_log:
                    existing_log.payload = mfn
                    existing_log.ack_payload = ack
                    existing_log.status = status
                    existing_log.message_type = "MFN^M05"
                    existing_log.created_at = datetime.utcnow()
                else:
                    log = MessageLog(
                        direction="out",
                        kind="MLLP",
                        endpoint_id=endpoint.id,
                        payload=mfn,
                        ack_payload=ack,
                        status=status,
                        message_type="MFN^M05",
                    )
                    session.add(log)
                break
            except Exception as exc:
                status = "error"
                ack = str(exc)
                retry += 1
                if existing_log:
                    existing_log.payload = mfn
                    existing_log.ack_payload = ack
                    existing_log.status = status
                    existing_log.message_type = "MFN^M05"
                    existing_log.created_at = datetime.utcnow()
                else:
                    log = MessageLog(
                        direction="out",
                        kind="MLLP",
                        endpoint_id=endpoint.id,
                        payload=mfn,
                        ack_payload=ack,
                        status=status,
                        message_type="MFN^M05",
                    )
                    session.add(log)
                if retry < max_retry:
                    time.sleep(60)


async def emit_structure_change(entity, session: Session, operation: str = "update", ght_context_id=None) -> None:
    """Émet FHIR (PUT) + HL7 MFN snapshot après création/mise à jour d'une entité de structure."""
    from app.models_structure import EntiteJuridique
    
    # EntiteJuridique doit être émise comme Organization, pas Location
    if isinstance(entity, EntiteJuridique):
        await _emit_organization_upsert(entity, session, ght_context_id=ght_context_id)
        await _emit_mfn_organization(entity, session, ght_context_id=ght_context_id)
        session.commit()
        return
    await _emit_fhir_upsert(entity, session, ght_context_id=ght_context_id)
    await _emit_mfn_entity(entity, session, ght_context_id=ght_context_id)
    session.commit()
async def emit_structure_snapshot_ej(ej_id: int, session: Session) -> None:
    """Émet le snapshot complet de la structure de l'EJ (FHIR + MFN) vers tous les endpoints."""
    from app.models_structure import EntiteJuridique
    ej = session.get(EntiteJuridique, ej_id)
    if not ej:
        logger.error(f"[structure_emit] EJ id={ej_id} introuvable pour émission snapshot.")
        return
    await _emit_organization_upsert(ej, session, ght_context_id=ej.ght_context_id)
    await _emit_mfn_organization(ej, session, ght_context_id=ej.ght_context_id)
    await _emit_mfn_snapshot(session, ght_context_id=ej.ght_context_id)
    session.commit()


async def emit_structure_delete(entity_id: int, session: Session, entity_type: str = None, finess_ej: str = None) -> None:
    """Émet FHIR (DELETE) + HL7 MFN snapshot après suppression d'une entité de structure."""
    from app.models_structure import EntiteJuridique
    
    # Si c'est une EntiteJuridique, émettre Organization DELETE
    if entity_type == "EntiteJuridique":
        await _emit_organization_delete(entity_id, finess_ej, session)
        await _emit_mfn_organization_delete(entity_id, finess_ej, session)
        session.commit()
        return
    
    await _emit_fhir_delete(entity_id, session)
    await _emit_mfn_snapshot(session)
    session.commit()
