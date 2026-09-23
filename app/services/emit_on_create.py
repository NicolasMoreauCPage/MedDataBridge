"""Orchestration des émissions déclenchées par une mutation métier.

La génération PAM vit dans :mod:`app.services.pam_message_generation`. Elle
reste réexportée ici pour préserver l'API historique des routeurs et tests.
"""

import asyncio
import logging
from typing import Literal, Optional

from sqlmodel import Session

from app.services.emission_audit import persist_generated_payloads
from app.services.emission_endpoints import list_eligible_sender_endpoints
from app.services.emission_snapshot import snapshot_entity as _snapshot_entity
from app.services.fhir_emission import emit_fhir_payload, generate_fhir
from app.services.file_endpoint_emission import emit_file_endpoint
from app.services.hprim_emission import emit_hprim_act
from app.services.pam_emission import emit_outbound_pam_attempt
from app.services.pam_message_generation import generate_pam_hl7

logger = logging.getLogger(__name__)


def emit_to_senders_async(
    entity,
    entity_type: Literal[
        "patient",
        "dossier",
        "venue",
        "mouvement",
        "structure",
        "ccam_act",
        "ngap_act",
        "ucd_act",
        "lpp_act",
    ],
    session: Session,
    operation: str = "insert",
    mrg_prior_identifiers: Optional[list] = None,
    mrg_prior_name: str | None = None,
) -> None:
    """Émet les notifications HL7, FHIR ou HPRIM d'une entité modifiée."""

    endpoints = list_eligible_sender_endpoints(session, entity)
    base_correlation_id = getattr(entity, "correlation_id", None)

    for endpoint in endpoints:
        correlation_id = base_correlation_id
        use_snapshot = getattr(endpoint, "use_snapshot_emission", True)
        snapshot = _snapshot_entity(entity, entity_type, session) if use_snapshot else None

        if endpoint.kind == "MLLP" and entity_type in ["patient", "venue", "mouvement"]:
            if not getattr(endpoint, "emit_hl7_pam", True):
                logger.debug(
                    "[MLLP] Endpoint %s has emit_hl7_pam=False - skipping PAM emission for %s",
                    endpoint.id,
                    entity_type,
                )
            elif not endpoint.host or not endpoint.port:
                logger.debug(
                    "[MLLP] Endpoint %s not properly configured (missing host/port) - skipping PAM emission",
                    endpoint.id,
                )
            else:
                gen_entity = entity if not isinstance(entity, dict) else (snapshot or entity)
                hl7_message = generate_pam_hl7(
                    gen_entity,
                    entity_type,
                    session,
                    forced_identifier_system=getattr(endpoint, "forced_identifier_system", None),
                    forced_identifier_oid=getattr(endpoint, "forced_identifier_oid", None),
                    operation=operation,
                    msh_sending_app=getattr(endpoint, "sending_app", None),
                    msh_sending_facility=getattr(endpoint, "sending_facility", None),
                    msh_receiving_app=getattr(endpoint, "receiving_app", None),
                    msh_receiving_facility=getattr(endpoint, "receiving_facility", None),
                    mrg_prior_identifiers=mrg_prior_identifiers,
                    mrg_prior_name=mrg_prior_name,
                )
                if hl7_message is None or not str(hl7_message).strip():
                    hl7_message = "[Emission error: HL7 message not generated]"
                try:
                    from app.services.mllp import parse_msh_fields

                    hl7_fields = parse_msh_fields(hl7_message)
                except (AttributeError, IndexError, TypeError, ValueError):
                    logger.warning(
                        "Impossible d'extraire les champs MSH du message sortant",
                        exc_info=True,
                    )
                    hl7_fields = {}
                correlation_id = hl7_fields.get("control_id") or correlation_id
                emit_outbound_pam_attempt(
                    session,
                    endpoint=endpoint,
                    payload=hl7_message,
                    correlation_id=correlation_id,
                    entity_id=getattr(entity, "id", "unknown"),
                    message_type=hl7_fields.get("msg_type") or "ADT^unknown",
                )

        if endpoint.kind == "MLLP" and entity_type == "structure":
            if not getattr(endpoint, "emit_hl7_mfn", True):
                logger.debug(
                    "[MLLP] Endpoint %s has emit_hl7_mfn=False - skipping MFN emission",
                    endpoint.id,
                )
            elif not endpoint.host or not endpoint.port:
                logger.debug(
                    "[MLLP] Endpoint %s not properly configured (missing host/port) - skipping MFN emission",
                    endpoint.id,
                )
            else:
                logger.warning(
                    "[MLLP] Endpoint %s requests automatic MFN emission, which is not implemented",
                    endpoint.id,
                )

        if endpoint.kind == "FHIR" and entity_type in ["dossier", "venue"]:
            if not getattr(endpoint, "emit_fhir_structure", True):
                logger.debug(
                    "[FHIR] Endpoint %s has emit_fhir_structure=False - skipping structure emission for %s",
                    endpoint.id,
                    entity_type,
                )
            elif not endpoint.base_url:
                logger.debug(
                    "[FHIR] Endpoint %s not properly configured (missing base_url) - skipping structure emission",
                    endpoint.id,
                )
            else:
                gen_entity = entity if not isinstance(entity, dict) else (snapshot or entity)
                fhir_payload = generate_fhir(
                    gen_entity,
                    entity_type,
                    session,
                    forced_identifier_system=getattr(endpoint, "forced_identifier_system", None),
                    forced_identifier_oid=getattr(endpoint, "forced_identifier_oid", None),
                )
                emit_fhir_payload(
                    session,
                    endpoint=endpoint,
                    payload=fhir_payload,
                    correlation_id=correlation_id,
                )

        if endpoint.kind == "FHIR" and entity_type in ["patient", "mouvement", "venue"]:
            if not getattr(endpoint, "emit_fhir_identity", True):
                logger.debug(
                    "[FHIR] Endpoint %s has emit_fhir_identity=False - skipping identity emission for %s",
                    endpoint.id,
                    entity_type,
                )
            elif not endpoint.base_url:
                logger.debug(
                    "[FHIR] Endpoint %s not properly configured (missing base_url) - skipping identity emission",
                    endpoint.id,
                )
            else:
                gen_entity = entity if not isinstance(entity, dict) else (snapshot or entity)
                fhir_payload = generate_fhir(
                    gen_entity,
                    entity_type,
                    session,
                    forced_identifier_system=getattr(endpoint, "forced_identifier_system", None),
                    forced_identifier_oid=getattr(endpoint, "forced_identifier_oid", None),
                )
                emit_fhir_payload(
                    session,
                    endpoint=endpoint,
                    payload=fhir_payload,
                    correlation_id=correlation_id,
                )

        if endpoint.kind == "HPRIM" and entity_type in [
            "ccam_act",
            "ngap_act",
            "ucd_act",
            "lpp_act",
        ]:
            try:
                emit_hprim_act(
                    session,
                    entity=entity,
                    entity_type=entity_type,
                    endpoint=endpoint,
                    operation=operation,
                    correlation_id=correlation_id,
                )
            except (AttributeError, TypeError, ValueError):
                logger.exception(
                    "[HPRIM] Error generating message for %s %s",
                    entity_type,
                    getattr(entity, "id", "unknown"),
                )

        if endpoint.kind in {"FILE", "SFTP"}:
            emit_file_endpoint(
                session,
                endpoint=endpoint,
                entity=entity,
                entity_type=entity_type,
                operation=operation,
                generate_pam=generate_pam_hl7,
                generate_fhir=generate_fhir,
            )

    if not endpoints:
        persist_generated_payloads(session, entity, entity_type, generate_pam_hl7, generate_fhir)


class _EmitToSendersWrapper:
    """Permet l'appel de l'émetteur depuis des contextes synchrones et asynchrones."""

    def __init__(self, async_callable):
        self._async = async_callable

    def __call__(self, entity, entity_type, session: Session, **kwargs):
        result = self._async(entity, entity_type, session, **kwargs)
        if asyncio.iscoroutine(result):
            try:
                asyncio.get_running_loop()
            except RuntimeError:
                return asyncio.run(result)
            return result
        return result


emit_to_senders = _EmitToSendersWrapper(emit_to_senders_async)

__all__ = ["emit_to_senders", "emit_to_senders_async", "generate_pam_hl7"]
