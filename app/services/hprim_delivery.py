"""Mise en file durable des messages HPRIM produits par les API d'actes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlmodel import Session, select

from app.models_endpoints import MessageLog, SystemEndpoint
from app.models_outbox import OutboundMessage
from app.services.outbox_service import enqueue_message


@dataclass(frozen=True)
class HprimDelivery:
    endpoint: SystemEndpoint
    outbox: OutboundMessage


def _protocol(endpoint: SystemEndpoint) -> str:
    kind = (endpoint.kind or "").upper()
    if kind in {"FILE", "FTP", "SFTP"}:
        return kind
    if kind == "HPRIM":
        # Un endpoint HPRIM décrit le contenu ; son transport est configuré
        # par ses champs fichier/FTP. Le repli FILE est le comportement
        # historique et nécessite donc un outbox_path au traitement.
        if endpoint.ftp_host:
            return "SFTP" if endpoint.ftp_use_sftp else "FTP"
        return "FILE"
    raise ValueError("Endpoint incompatible avec une émission HPRIM")


def resolve_hprim_endpoint(
    session: Session,
    *,
    endpoint_id: Optional[int],
    target_system_key: Optional[str],
) -> Optional[SystemEndpoint]:
    """Résout l'endpoint explicitement choisi ou la destination logique."""
    if endpoint_id is not None:
        endpoint = session.get(SystemEndpoint, endpoint_id)
        if endpoint is None:
            raise ValueError("Endpoint HPRIM introuvable")
        return endpoint
    if not target_system_key:
        return None
    candidates = session.exec(
        select(SystemEndpoint)
        .where(SystemEndpoint.is_enabled == True)  # noqa: E712
        .where(SystemEndpoint.target_system_key == target_system_key)
        .order_by(SystemEndpoint.id)
    ).all()
    return next((item for item in candidates if (item.role or "").lower() in {"sender", "both"} and (item.kind or "").upper() in {"HPRIM", "FILE", "FTP", "SFTP"}), None)


def queue_hprim_delivery(
    session: Session,
    *,
    xml_content: str,
    message_id: str,
    message_type: str,
    endpoint_id: Optional[int] = None,
    target_system_key: Optional[str] = None,
) -> Optional[HprimDelivery]:
    """Crée le journal source et sa ligne d'outbox, sans simuler d'envoi."""
    endpoint = resolve_hprim_endpoint(
        session, endpoint_id=endpoint_id, target_system_key=target_system_key,
    )
    if endpoint is None:
        return None
    if not endpoint.is_enabled:
        raise ValueError("Endpoint HPRIM désactivé")
    if (endpoint.role or "").lower() not in {"sender", "both"}:
        raise ValueError("Endpoint HPRIM non émetteur")
    protocol = _protocol(endpoint)
    source_log = MessageLog(
        direction="out",
        kind="HPRIM",
        message_type=message_type,
        endpoint_id=endpoint.id,
        correlation_id=message_id,
        status="pending",
        payload=xml_content,
    )
    session.add(source_log)
    session.flush()
    outbox = enqueue_message(
        session,
        endpoint_id=endpoint.id,
        protocol=protocol,
        payload=xml_content,
        message_type=message_type,
        correlation_id=message_id,
        source_message_log_id=source_log.id,
    )
    session.flush()
    return HprimDelivery(endpoint=endpoint, outbox=outbox)
