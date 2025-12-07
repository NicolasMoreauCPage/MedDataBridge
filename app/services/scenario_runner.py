from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime
from typing import Iterable, List, Optional, Tuple

from sqlmodel import Session, select

from app.models_endpoints import FHIRConfig, MessageLog, SystemEndpoint
from app.models_scenarios import InteropScenario, InteropScenarioStep, ScenarioBinding
from app.models_scenario_runs import (
    ScenarioExecutionRun,
    ScenarioExecutionStepLog,
)
from app.models_structure import IdentifierNamespace
from app.services.fhir_transport import post_fhir_bundle
from app.services.mllp import parse_msh_fields, send_mllp
from app.services.scenario_date_updater import update_hl7_message_dates
from app.services.scenario_timeplan import TimeShiftConfig, shift_hl7_scenario
from app.services.scenario_realistic_timeplan import create_realistic_timeshift_config
from app.services.scenario_transform import transform_hl7_for_context
from app.services.scenario_identifier_replacer import replace_identifiers_in_hl7_message


logger = logging.getLogger(__name__)


class ScenarioExecutionError(Exception):
    """Erreur personnalisée pour l'exécution d'un scénario."""


def _build_fhir_targets(endpoint: SystemEndpoint) -> List[Tuple[str, str, str | None]]:
    targets: List[Tuple[str, str, str | None]] = []
    for cfg in getattr(endpoint, "fhir_configs", []) or []:
        if isinstance(cfg, FHIRConfig) and cfg.is_enabled and cfg.base_url:
            targets.append((cfg.base_url, cfg.auth_kind or "none", cfg.auth_token))
    if targets:
        return targets

    host = (endpoint.host or "").strip()
    if not host:
        return targets

    if host.startswith(("http://", "https://")):
        base_url = host
        if endpoint.port and ":" not in host.split("//", 1)[1]:
            base_url = f"{host}:{endpoint.port}"
    else:
        scheme = "https" if str(endpoint.port) in {"443", "8443"} else "http"
        base_url = f"{scheme}://{host}"
        if endpoint.port:
            base_url = f"{base_url}:{endpoint.port}"
    targets.append((base_url, "none", None))
    return targets


def _extract_trigger(step: InteropScenarioStep) -> Optional[str]:
    if step.message_type:
        parts = step.message_type.split("^")
        if len(parts) > 1 and parts[1]:
            return parts[1]
        return step.message_type
    try:
        fields = parse_msh_fields(step.payload)
        return fields.get("trigger")
    except Exception:
        return None


def _extract_segment(message: str, segment_name: str) -> Optional[str]:
    """Extrait un segment HL7 du message (ex: 'PID' pour obtenir la ligne PID)."""
    lines = message.split('\n')
    for line in lines:
        if line.startswith(segment_name + '|'):
            return line
    return None


def _replace_segment(message: str, segment_name: str, new_segment: str) -> str:
    """Remplace un segment HL7 dans le message."""
    lines = message.split('\n')
    result = []
    replaced = False
    for line in lines:
        if line.startswith(segment_name + '|') and not replaced:
            result.append(new_segment)
            replaced = True
        else:
            result.append(line)
    return '\n'.join(result)


async def _send_hl7_step(
    session: Session,
    step: InteropScenarioStep,
    endpoint: SystemEndpoint,
    update_dates: bool = True,
    binding: Optional[ScenarioBinding] = None,
    payload_override: Optional[str] = None,
) -> MessageLog:
    """
    Envoie une étape HL7 via MLLP avec remplacement optionnel des identifiants.
    
    Args:
        session: Session de base de données
        step: Étape du scénario à envoyer
        endpoint: Endpoint cible
        update_dates: Si True, met à jour les dates du message pour qu'elles soient récentes
        binding: ScenarioBinding optionnel pour configuration des identifiants
    """
    if not endpoint.host or not endpoint.port:
        raise ScenarioExecutionError("Endpoint MLLP incomplet (host/port manquant)")

    # Choisir payload de départ (override pré-calculé si fourni)
    working_payload = payload_override if payload_override else step.payload

    # Adapter le message au contexte local (MSH, namespaces PID-3)
    try:
        # Privilégier le contexte du scénario, sinon celui de l'endpoint
        ght_context_id = None
        ej_context_id = None
        try:
            # Relationship lazy; safe in this session
            if step.scenario and step.scenario.ght_context_id:
                ght_context_id = step.scenario.ght_context_id
            if step.scenario and step.scenario.entite_juridique_id:
                ej_context_id = step.scenario.entite_juridique_id
        except Exception:
            pass
        if not ght_context_id:
            ght_context_id = getattr(endpoint, "ght_context_id", None)
        if not ej_context_id:
            ej_context_id = getattr(endpoint, "entite_juridique_id", None)
        payload_to_send = transform_hl7_for_context(
            session,
            working_payload,
            endpoint=endpoint,
            ght_context_id=ght_context_id,
            ej_context_id=ej_context_id,
            remap_pid3=True,
        )
    except Exception:
        # En cas d'erreur transformation, Solution de repli au payload original
        payload_to_send = working_payload
    
    # Remplacement des identifiants - TOUJOURS génération de nouveaux identifiants
    generated_ids = {}
    if ght_context_id:
        try:
            # Récupérer les namespaces configurés pour ce contexte
            ipp_namespace = session.exec(
                select(IdentifierNamespace).where(
                    IdentifierNamespace.ght_context_id == ght_context_id,
                    IdentifierNamespace.type == "IPP",
                    IdentifierNamespace.is_active == True
                )
            ).first()
            
            nda_namespace = session.exec(
                select(IdentifierNamespace).where(
                    IdentifierNamespace.ght_context_id == ght_context_id,
                    IdentifierNamespace.type == "NDA",
                    IdentifierNamespace.is_active == True
                )
            ).first()
            
            venue_namespace = session.exec(
                select(IdentifierNamespace).where(
                    IdentifierNamespace.ght_context_id == ght_context_id,
                    IdentifierNamespace.type == "VN",
                    IdentifierNamespace.is_active == True
                )
            ).first()
            
            # Si namespaces configurés, utiliser le système standard
            if ipp_namespace and nda_namespace:
                ipp_prefix_override = binding.identifier_prefix_ipp if binding else None
                nda_prefix_override = binding.identifier_prefix_nda if binding else None
                
                payload_to_send, generated_ids = replace_identifiers_in_hl7_message(
                    message=payload_to_send,
                    session=session,
                    ipp_namespace=ipp_namespace,
                    nda_namespace=nda_namespace,
                    venue_namespace=venue_namespace,
                    ipp_prefix_override=ipp_prefix_override,
                    nda_prefix_override=nda_prefix_override
                )
                
                # Mettre à jour le binding avec les identifiants générés (si binding existe)
                if binding and generated_ids:
                    binding.generated_ipp = generated_ids.get('ipp')
                    binding.generated_nda = generated_ids.get('nda')
                    binding.generated_venue_id = generated_ids.get('venue')
                    binding.last_execution_at = datetime.utcnow()
                    session.add(binding)
                    session.commit()
                    
                logger.info(f"✅ Identifiants générés avec namespaces: IPP={generated_ids.get('ipp')}, NDA={generated_ids.get('nda')}")
            
            # Dans TOUS LES CAS (namespaces ou pas), générer nouveaux identifiants + config EJ
            if True:  # Force toujours la génération
                logger.info("🔄 Génération systématique de nouveaux identifiants avec config EJ")
                from app.utils.seq_generator import generate_patient_seq, generate_dossier_seq
                from app.models_scenario_config import ScenarioEJConfig, get_medecin_for_event, build_xcn_field, get_location_for_event
                
                # Récupérer la config EJ
                ej_config = session.exec(
                    select(ScenarioEJConfig).where(ScenarioEJConfig.entite_juridique_id == ght_context_id)
                ).first()
                
                # Générer NOUVEAUX identifiants IPP/NDA à chaque exécution
                ipp_value = str(generate_patient_seq())  # Format: "9" + 11 chiffres
                nda_value = str(generate_dossier_seq())  # Format: "9" + 8 chiffres
                
                # Extraire le trigger pour déterminer les UF/médecin à utiliser
                trigger = None
                msh_line = next((line for line in payload_to_send.split('\n') if line.startswith('MSH')), None)
                if msh_line:
                    msh_fields = msh_line.split('|')
                    if len(msh_fields) > 9:
                        trigger = msh_fields[9].split('^')[0] if '^' in msh_fields[9] else msh_fields[9]
                
                # Remplacer dans PID (identifiants patient)
                pid_segment = _extract_segment(payload_to_send, "PID")
                if pid_segment:
                    # PID-3: IPP
                    new_pid = re.sub(
                        r'^(PID\|[^|]*\|[^|]*\|)([^|]*)(\|)',
                        fr'\g<1>{ipp_value}^^^1.2.250.1.213.1.1.1\g<3>',
                        pid_segment
                    )
                    # PID-18: NDA
                    fields = new_pid.split('|')
                    while len(fields) <= 18:
                        fields.append('')
                    fields[18] = f"{nda_value}^^^1.2.250.1.213.1.1.9"
                    new_pid = '|'.join(fields)
                    payload_to_send = _replace_segment(payload_to_send, "PID", new_pid)
                    
                    generated_ids.update({'ipp': ipp_value, 'nda': nda_value})
                    logger.info(f"🆔 NOUVEAUX identifiants: IPP={ipp_value}, NDA={nda_value}")
                
                # Remplacer UF et médecin dans PV1 avec config EJ
                pv1_segment = _extract_segment(payload_to_send, "PV1")
                if pv1_segment and trigger:
                    pv1_fields = pv1_segment.split('|')
                    
                    # PV1-3: Localisation avec UF configurée
                    if ej_config:
                        location_info = get_location_for_event(ej_config, trigger, session)
                        if location_info.get("pv1_3"):
                            if len(pv1_fields) > 3:
                                pv1_fields[3] = location_info["pv1_3"]
                                logger.info(f"🏥 UF configurée: {location_info['pv1_3']}")
                    
                    # PV1-7: Médecin responsable configuré
                    if ej_config:
                        medecin_info = get_medecin_for_event(ej_config, trigger)
                        if medecin_info:
                            pv1_7 = build_xcn_field(medecin_info)
                            if len(pv1_fields) > 7:
                                pv1_fields[7] = pv1_7
                                logger.info(f"👨‍⚕️ Médecin configuré: {medecin_info.get('nom', '')} (RPPS: {medecin_info.get('rpps', '')})")
                    
                    new_pv1 = '|'.join(pv1_fields)
                    payload_to_send = _replace_segment(payload_to_send, "PV1", new_pv1)
        except Exception as e:
            # Log l'erreur mais continue avec le payload non modifié
            logger.warning(f"⚠️ Erreur remplacement identifiants: {e}")

    # Mettre à jour les dates du message si demandé ET pas déjà recalé globalement
    if update_dates and payload_override is None:
        try:
            payload_to_send = update_hl7_message_dates(payload_to_send, datetime.utcnow())
        except Exception:
            pass

    ack_payload = ""
    status = "error"
    try:
        maybe = send_mllp(endpoint.host, endpoint.port, payload_to_send)
        # Support both async and sync monkeypatched implementations
        if hasattr(maybe, "__await"):
            ack_payload = await maybe
        else:
            ack_payload = maybe
        status = "sent" if ack_payload else "unknown"
    except Exception as exc:
        ack_payload = str(exc)
        status = "error"
        raise ScenarioExecutionError(str(exc))

    msh_fields = parse_msh_fields(payload_to_send)
    log = MessageLog(
        direction="out",
        kind="MLLP",
        endpoint_id=endpoint.id,
        payload=payload_to_send,  # Logger le message avec dates mises à jour
        ack_payload=ack_payload or "",
        status=status,
        correlation_id=msh_fields.get("control_id"),
    )
    session.add(log)
    session.commit()
    session.refresh(log)
    return log


async def _send_fhir_step(session: Session, step: InteropScenarioStep, endpoint: SystemEndpoint) -> MessageLog:
    try:
        payload_obj = json.loads(step.payload)
    except json.JSONDecodeError as exc:
        raise ScenarioExecutionError(f"Payload FHIR invalide: {exc}") from exc

    targets = _build_fhir_targets(endpoint)
    if not targets:
        raise ScenarioExecutionError("Endpoint FHIR sans configuration d'URL")

    status = "error"
    ack_payload = ""
    last_status_code = None

    for base_url, auth_kind, auth_token in targets:
        try:
            status_code, response = await post_fhir_bundle(
                base_url,
                payload_obj,
                auth_kind=auth_kind,
                auth_token=auth_token,
            )
            last_status_code = status_code
            ack_payload = json.dumps(response or {}, default=str)
            status = "sent" if 200 <= status_code < 300 else "error"
            if status == "sent":
                break
        except Exception as exc:
            ack_payload = str(exc)
            status = "error"
            raise ScenarioExecutionError(str(exc))

    log = MessageLog(
        direction="out",
        kind="FHIR",
        endpoint_id=endpoint.id,
        payload=json.dumps(payload_obj, default=str),
        ack_payload=ack_payload,
        status=status,
        correlation_id=str(last_status_code) if last_status_code is not None else None,
    )
    session.add(log)
    session.commit()
    session.refresh(log)
    return log


async def send_step(
    session: Session,
    step: InteropScenarioStep,
    endpoint: SystemEndpoint,
    update_dates: bool = True,
    binding: Optional[ScenarioBinding] = None,
    payload_override: Optional[str] = None,
) -> MessageLog:
    """
    Envoie une étape de scénario au système cible.
    
    Args:
        session: Session de base de données
        step: Étape du scénario à envoyer
        endpoint: Endpoint cible
        update_dates: Si True, met à jour automatiquement les dates HL7 pour qu'elles soient récentes
        binding: ScenarioBinding optionnel pour configuration des identifiants
    """
    trigger = _extract_trigger(step)

    if step.message_format.lower() == "hl7" and trigger and trigger.startswith("Z") and trigger != "Z99":
        log = MessageLog(
            direction="out",
            kind="MLLP",
            endpoint_id=endpoint.id,
            payload=step.payload,
            ack_payload="Message Zxx obsolète (non émis)",
            status="skipped",
            correlation_id=None,
        )
        session.add(log)
        session.commit()
        session.refresh(log)
        return log

    if endpoint.kind == "MLLP":
        return await _send_hl7_step(
            session,
            step,
            endpoint,
            update_dates=update_dates,
            binding=binding,
            payload_override=payload_override,
        )
    if endpoint.kind == "FHIR":
        return await _send_fhir_step(session, step, endpoint)
    raise ScenarioExecutionError(f"Type d'endpoint non supporté: {endpoint.kind}")


async def send_scenario(
    session: Session,
    scenario: InteropScenario,
    endpoint: SystemEndpoint,
    *,
    step_ids: Iterable[int] | None = None,
    update_dates: bool = True,
    binding: Optional[ScenarioBinding] = None,
    use_advanced_timeplan: bool = True,
    dry_run: bool = False,
    start_order_index: Optional[int] = None,
) -> List[MessageLog]:
    """Envoie ou simule (dry_run) un scénario.

    Ajouts:
      - dry_run: ne pas envoyer, seulement prévisualiser (statut dry_run)
      - start_order_index: commencer à partir d'une étape (skip antérieures)
      - journalisation dans ScenarioExecutionRun/ScenarioExecutionStepLog
    """
    logs: List[MessageLog] = []
    steps = scenario.steps
    if step_ids:
        ids = set(step_ids)
        steps = [step for step in steps if step.id in ids]

    steps = sorted(steps, key=lambda s: s.order_index)
    if start_order_index is not None:
        steps = [s for s in steps if s.order_index >= start_order_index]

    # Créer le run
    run = ScenarioExecutionRun(
        scenario_id=scenario.id,
        endpoint_id=endpoint.id,
        status="running" if not dry_run else "dry_run",
        dry_run=dry_run,
        total_steps=len(steps),
    )
    session.add(run)
    session.commit()
    session.refresh(run)

    # Pré-calcul avancé de recalage temporel si activé (uniquement si pas dry_run ou si on veut aperçu cohérent)
    payload_overrides: dict[int, str] = {}
    if update_dates and use_advanced_timeplan:
        try:
            hl7_steps = [s for s in steps if s.message_format.lower() == "hl7"]
            original_messages = [s.payload for s in hl7_steps]
            message_types = [s.message_type for s in hl7_steps]
            
            # Si le scénario n'a pas de configuration temporelle personnalisée,
            # utiliser la détection automatique de workflow réaliste
            if (scenario.time_anchor_mode is None and 
                scenario.jitter_min_minutes is None and 
                scenario.jitter_max_minutes is None):
                cfg = create_realistic_timeshift_config(original_messages, message_types)
                print(f"[scenario_runner] Using automatic realistic timeplan for scenario {scenario.name}")
            else:
                # Utiliser la configuration manuelle existante
                cfg = TimeShiftConfig(
                    anchor_mode=scenario.time_anchor_mode or "now",
                    anchor_days_offset=scenario.time_anchor_days_offset,
                    fixed_start_iso=scenario.time_fixed_start_iso,
                    preserve_intervals=scenario.preserve_intervals,
                    jitter_min_minutes=scenario.jitter_min_minutes,
                    jitter_max_minutes=scenario.jitter_max_minutes,
                    jitter_events=[e.strip() for e in (scenario.apply_jitter_on_events or "").split(',') if e.strip()] or None,
                )
                print(f"[scenario_runner] Using manual timeplan configuration for scenario {scenario.name}")
            
            shifted_messages = shift_hl7_scenario(original_messages, cfg)
            for s, new_payload in zip(hl7_steps, shifted_messages):
                payload_overrides[s.id] = new_payload
        except Exception as e:
            print(f"[scenario_runner] Timeplan advanced failed: {e}. Fallback per-message update.")

    for step in steps:
        start_ts = datetime.utcnow()
        override = payload_overrides.get(step.id)
        ack_code = None
        status = "dry_run" if dry_run else "pending"
        error_message = None
        message_log: Optional[MessageLog] = None
        try:
            if dry_run:
                # Aperçu remplacement identifiants uniquement (si binding)
                if binding:
                    # Preview - ne persiste pas les identifiants
                    pass  # Placeholder pour future preview détaillée
                status = "dry_run"
            else:
                message_log = await send_step(
                    session,
                    step,
                    endpoint,
                    update_dates=update_dates,
                    binding=binding,
                    payload_override=override,
                )
                status = message_log.status
                # Extraction code ACK HL7 (AA/AE/AR) ou HTTP code pour FHIR
                if message_log.kind == "MLLP" and message_log.ack_payload:
                    for line in message_log.ack_payload.replace("\r", "\n").split("\n"):
                        if line.startswith("MSA|"):
                            msa_fields = line.split("|")
                            if len(msa_fields) > 1:
                                ack_code = msa_fields[1]
                            break
                elif message_log.kind == "FHIR" and message_log.correlation_id:
                    ack_code = message_log.correlation_id
        except ScenarioExecutionError as exc:
            status = "error"
            error_message = str(exc)
        end_ts = datetime.utcnow()
        duration_ms = int((end_ts - start_ts).total_seconds() * 1000)

        # Créer le Étape log
        step_log = ScenarioExecutionStepLog(
            run_id=run.id,
            step_id=step.id,
            endpoint_id=endpoint.id,
            order_index=step.order_index,
            status=status,
            ack_code=ack_code,
            duration_ms=duration_ms,
            error_message=error_message,
            payload_excerpt=(override or step.payload)[:512],
        )
        session.add(step_log)
        session.commit()

        if message_log:
            logs.append(message_log)
        else:
            # Créer un faux MessageLog pour interface unifiée (dry_run ou erreur sans émission MLLP/FHIR)
            synthetic = MessageLog(
                direction="out",
                kind=endpoint.kind,
                endpoint_id=endpoint.id,
                payload=override or step.payload,
                ack_payload="" if not ack_code else ack_code,
                status=status,
                correlation_id=None,
            )
            session.add(synthetic)
            session.commit()
            session.refresh(synthetic)
            logs.append(synthetic)

        # Pause si définie et pas dry_run
        if step.delay_seconds and not dry_run:
            await asyncio.sleep(step.delay_seconds)

    # Mise à jour du run
    run.finished_at = datetime.utcnow()
    run.success_steps = sum(1 for l in run.step_logs if l.status == "sent")
    run.error_steps = sum(1 for l in run.step_logs if l.status == "error")
    run.skipped_steps = sum(1 for l in run.step_logs if l.status == "skipped")
    if dry_run:
        run.status = "dry_run"
    elif run.error_steps == 0 and run.success_steps == run.total_steps:
        run.status = "success"
    elif run.error_steps == 0 and (run.success_steps + run.skipped_steps) == run.total_steps:
        run.status = "success"
    elif run.error_steps < run.total_steps:
        run.status = "partial"
    else:
        run.status = "error"
    session.add(run)
    session.commit()
    session.refresh(run)

    return logs


def list_scenarios(session: Session) -> List[InteropScenario]:
    return session.exec(select(InteropScenario).order_by(InteropScenario.name)).all()


def get_scenario(session: Session, scenario_id: int) -> Optional[InteropScenario]:
    return session.get(InteropScenario, scenario_id)


async def execute_scenario_on_endpoint(
    endpoint: SystemEndpoint,
    scenario: InteropScenario,
    steps: List[InteropScenarioStep],
    session: Session
) -> dict:
    """
    Exécute un scénario complet sur un endpoint spécifique.
    
    Args:
        endpoint: L'endpoint cible
        scenario: Le scénario à exécuter
        steps: Les étapes du scénario (déjà triées par order_index)
        session: Session de base de données
        
    Returns:
        dict avec success_count, error_count, total_count
    """
    from app.models_scenario_runs import ScenarioExecutionRun, ScenarioExecutionStepLog
    
    # Créer un run d'exécution
    run = ScenarioExecutionRun(
        scenario_id=scenario.id,
        triggered_by="manual_endpoint",
        endpoint_id=endpoint.id,
        status="running",
        started_at=datetime.utcnow(),
        total_steps=len(steps),
        success_steps=0,
        error_steps=0,
        skipped_steps=0
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    
    success_count = 0
    error_count = 0
    
    try:
        for step in steps:
            step_log = ScenarioExecutionStepLog(
                run_id=run.id,
                step_id=step.id,
                step_order=step.order_index,
                status="running",
                started_at=datetime.utcnow()
            )
            session.add(step_log)
            session.commit()
            
            try:
                # Envoyer selon le protocole de l'endpoint
                if endpoint.kind == "MLLP":
                    message_log = await _send_hl7_step(
                        session=session,
                        step=step,
                        endpoint=endpoint,
                        update_dates=True
                    )
                    
                    step_log.message_log_id = message_log.id
                    step_log.ack_code = message_log.ack_code
                    step_log.response = message_log.response_payload
                    
                    if message_log.ack_code in ("AA", "CA"):
                        step_log.status = "success"
                        success_count += 1
                    else:
                        step_log.status = "error"
                        error_count += 1
                        
                elif endpoint.kind == "FHIR":
                    # Pour FHIR, on suppose que le payload est déjà un Bundle JSON
                    targets = _build_fhir_targets(endpoint)
                    if not targets:
                        raise ScenarioExecutionError("Aucun serveur FHIR configuré")
                    
                    base_url, auth_kind, auth_token = targets[0]
                    response = await post_fhir_bundle(
                        base_url=base_url,
                        bundle_json=step.payload,
                        auth_kind=auth_kind,
                        auth_token=auth_token
                    )
                    
                    step_log.response = json.dumps(response)
                    step_log.status = "success"
                    success_count += 1
                    
                elif endpoint.kind == "FILE":
                    # Écrire le message dans l'outbox_path de l'endpoint
                    if not endpoint.outbox_path:
                        raise ScenarioExecutionError("Aucun outbox_path configuré pour l'endpoint FILE")
                    
                    import os
                    from datetime import datetime as dt
                    
                    # Créer le répertoire s'il n'existe pas
                    os.makedirs(endpoint.outbox_path, exist_ok=True)
                    
                    # Générer un nom de fichier avec timestamp
                    timestamp = dt.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
                    file_ext = ".hl7" if scenario.protocol == "HL7" else ".json"
                    filename = f"{scenario.name.replace(' ', '_')}_{step.order_index}_{timestamp}{file_ext}"
                    filepath = os.path.join(endpoint.outbox_path, filename)
                    
                    # Écrire le payload
                    with open(filepath, "w", encoding="utf-8") as f:
                        f.write(step.payload)
                    
                    step_log.response = f"Écrit dans {filepath}"
                    step_log.status = "success"
                    success_count += 1
                    
                else:
                    step_log.status = "skipped"
                    step_log.error_message = f"Type d'endpoint non supporté: {endpoint.kind}"
                    
            except Exception as e:
                step_log.status = "error"
                step_log.error_message = str(e)
                error_count += 1
                
            # Calculer la durée en millisecondes
            now = datetime.utcnow()
            duration_ms = int((now - step_log.created_at).total_seconds() * 1000)
            step_log.duration_ms = duration_ms
            session.add(step_log)
            session.commit()
            
            # Délai entre messages si configuré
            if step.delay_seconds and step.delay_seconds > 0:
                await asyncio.sleep(step.delay_seconds)
        
        # Mettre à jour le run
        run.success_steps = success_count
        run.error_steps = error_count
        run.finished_at = datetime.utcnow()
        
        if error_count == 0:
            run.status = "success"
        elif success_count > 0:
            run.status = "partial"
        else:
            run.status = "error"
            
        session.add(run)
        session.commit()
        
    except Exception as e:
        run.status = "error"
        run.finished_at = datetime.utcnow()
        session.add(run)
        session.commit()
        raise
    
    return {
        "success_count": success_count,
        "error_count": error_count,
        "total_count": len(steps),
        "run_id": run.id
    }
