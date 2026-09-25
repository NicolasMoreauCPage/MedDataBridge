"""Préparation et émission cohérente des jeux de scénarios multi-protocoles.

Le service est intentionnellement séparé du runner historique: il compile une
fois les messages, alloue une identité unique au jeu, puis réutilise exactement
ces payloads pour tous les endpoints sélectionnés.
"""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from dataclasses import replace
from datetime import date, datetime, timedelta
from typing import Any, Iterable, Optional
from uuid import uuid4

from sqlmodel import Session, select

from app.models_endpoints import SystemEndpoint
from app.models.outbox import OutboundMessage
from app.models.practitioners import MedecinResponsable
from app.models_scenario_runs import ScenarioDelivery, ScenarioPlay, ScenarioPlayStep, ScenarioPlayTarget
from app.models_scenario_review import ScenarioCatalogReview
from app.models_scenarios import InteropScenario, InteropScenarioStep
from app.models_structure import IdentifierNamespace
from app.services.scenario_identifier_replacer import replace_identifiers_in_hl7_message
from app.services.scenario_identity_generator import PatientIdentity, apply_patient_identity_to_hl7, generate_patient_identity
from app.services.identifier_generator import generate_identifier_set
from app.services.scenario_qualification_service import refresh_play_target_states, target_key
from app.services.scenario_version_service import current_scenario_version
from app.services.outbox_service import enqueue_message, process_outbox_message, retry_now
from app.services.scenario_play_assertions import evaluate_play_assertions
from app.services.qualification_engine import validate_preconditions
from app.services.scenario_target_profile_service import resolve_target_context
from app.services.scenario_output_validation import validate_compiled_payload
from app.utils.seq_generator import generate_venue_seq


class ScenarioPlayError(ValueError):
    """Erreur fonctionnelle de préparation ou de livraison d'un jeu."""


def _identity_from_authoring_data(scenario: InteropScenario, generated: PatientIdentity) -> PatientIdentity:
    """Applique l'identité choisie dans l'assistant au jeu compilé.

    Les scénarios historiques et les métadonnées malformées conservent sans
    interruption la génération aléatoire historique.
    """
    try:
        metadata = json.loads(scenario.authoring_metadata_json or "{}")
        data = metadata.get("test_data", {}) if isinstance(metadata, dict) else {}
        if not isinstance(data, dict):
            return generated
        family, given = str(data.get("family") or "").strip(), str(data.get("given") or "").strip()
        birth_date = date.fromisoformat(str(data.get("birth_date") or ""))
        gender = str(data.get("gender") or "").upper()
        if not family or not given or gender not in {"F", "M", "U"}:
            return generated
        return replace(generated, family=family, given=given, birth_date=birth_date, gender=gender)
    except (TypeError, ValueError, json.JSONDecodeError):
        return generated


def _namespace(session: Session, ght_context_id: Optional[int], kind: str) -> Optional[IdentifierNamespace]:
    if not ght_context_id:
        return None
    return session.exec(
        select(IdentifierNamespace)
        .where(IdentifierNamespace.ght_context_id == ght_context_id)
        .where(IdentifierNamespace.type == kind)
        .where(IdentifierNamespace.is_active == True)  # noqa: E712
        .order_by(IdentifierNamespace.id)
    ).first()


def _identifier_context(session: Session, ght_context_id: Optional[int], play_key: str) -> dict[str, Any]:
    ipp, nda, venue = (_namespace(session, ght_context_id, t) for t in ("IPP", "NDA", "VN"))
    values: dict[str, Optional[str]] = {"ipp": None, "nda": None, "venue": None}
    if ipp and nda:
        values.update(generate_identifier_set(session, ipp, nda, venue))
    # A scenario remains usable in a minimally configured test GHT.  The key is
    # unique and never depends on a timestamp-only value.
    suffix = play_key.rsplit("-", 1)[-1]
    values["ipp"] = values["ipp"] or f"TEST{suffix}"
    values["nda"] = values["nda"] or f"NDA{suffix}"
    values["venue"] = values["venue"] or f"VEN{suffix}"
    return {"identifiers": values, "namespaces": {"ipp": _namespace_dict(ipp), "nda": _namespace_dict(nda), "venue": _namespace_dict(venue)}}


def _source_hl7_entity_key(payload: str) -> Optional[str]:
    """Retourne la clé patient portée par un template HL7 historique.

    Un catalogue peut contenir une mère et son nouveau-né dans le même
    scénario. Il est alors essentiel de conserver deux identités générées :
    remplacer tous les PID par le même IPP transforme artificiellement deux
    admissions valides en ``A01 -> A01`` sur une seule venue.
    """
    normalized = _normalize_hl7_line_endings(payload)
    for line in normalized.replace("\r", "\n").split("\n"):
        if not line.startswith("PID|"):
            continue
        fields = line.split("|")
        if len(fields) <= 3:
            return None
        for repetition in fields[3].split("~"):
            value = repetition.split("^", 1)[0].strip()
            if value:
                return f"pid:{value}"
        return None
    return None


def _step_entity_key(step: InteropScenarioStep) -> Optional[str]:
    if (step.message_format or "hl7").lower() != "hl7":
        return None
    return _source_hl7_entity_key(step.payload)


def _build_entity_contexts(
    session: Session,
    scenario: InteropScenario,
    source_steps: list[InteropScenarioStep],
    play_key: str,
    primary_context: dict[str, Any],
    primary_identity: PatientIdentity,
) -> tuple[str, dict[str, tuple[PatientIdentity, dict[str, Any]]]]:
    """Alloue une identité/venue par patient source, sans réutilisation entre jeux.

    Les étapes XML/FHIR sans PID sont rattachées au patient principal ; les
    scénarios à patient unique conservent donc exactement le comportement
    antérieur. Les autres PID reçoivent chacun un triplet IPP/NDA/venue propre.
    """
    keys: list[str] = []
    for step in source_steps:
        key = _step_entity_key(step)
        if key and key not in keys:
            keys.append(key)
    primary_key = keys[0] if keys else "default"
    entities: dict[str, tuple[PatientIdentity, dict[str, Any]]] = {
        primary_key: (primary_identity, primary_context)
    }
    for index, key in enumerate(keys[1:], start=2):
        entities[key] = (
            generate_patient_identity(),
            _identifier_context(session, scenario.ght_context_id, f"{play_key}-P{index}"),
        )
    return primary_key, entities


def _entity_for_step(
    step: InteropScenarioStep,
    primary_key: str,
    entities: dict[str, tuple[PatientIdentity, dict[str, Any]]],
) -> tuple[PatientIdentity, dict[str, Any]]:
    return entities.get(_step_entity_key(step) or primary_key, entities[primary_key])


def _practitioner_context(session: Session) -> dict[str, str]:
    """Construit le praticien commun à toutes les étapes d'un jeu.

    Un praticien déclaré dans le référentiel local est préférable à une valeur
    fictive : il représente alors le même professionnel dans PAM, HPRIM et
    FHIR. Un contexte de recette vide conserve néanmoins un praticien de test
    valide, pour qu'un scénario reste prévisualisable et que ses tokens soient
    toujours résolus.
    """
    practitioner = session.exec(
        select(MedecinResponsable)
        .where(MedecinResponsable.active == True)  # noqa: E712
        .order_by(MedecinResponsable.id)
    ).first()
    if practitioner:
        rpps = practitioner.rpps or ""
        adeli = practitioner.adeli or ""
        family = practitioner.family_name or "MEDECIN"
        given = practitioner.given_name or "SCENARIO"
        prefix = practitioner.prefix or "Dr"
        specialty = practitioner.specialty or ""
    else:
        rpps, adeli = "00000000000", "000000000"
        family, given, prefix, specialty = "MEDECIN", "SCENARIO", "Dr", ""
    identifier = rpps or adeli
    identifier_type = "RPPS" if rpps else "ADELI"
    identifier_oid = "1.2.250.1.71.4.2.1" if rpps else "1.2.250.1.71.4.2.1.1"
    xcn = f"{identifier}^{family}^{given}^^^{prefix}^^{identifier_type}^{identifier_oid}^L" if identifier else ""
    return {
        "id": identifier,
        "rpps": rpps,
        "adeli": adeli,
        "family": family,
        "given": given,
        "prefix": prefix,
        "specialty": specialty,
        "name": " ".join(part for part in (prefix, given, family) if part),
        "xcn": xcn,
    }


def _namespace_dict(namespace: Optional[IdentifierNamespace]) -> Optional[dict[str, str]]:
    if not namespace:
        return None
    return {"name": namespace.name, "system": namespace.system, "oid": namespace.oid or namespace.system.split(":")[-1]}


def _token_values(
    play_key: str,
    identity: PatientIdentity,
    ids: dict[str, Optional[str]],
    order: int,
    practitioner: Optional[dict[str, str]] = None,
    location: Optional[dict[str, str]] = None,
) -> dict[str, str]:
    now = datetime.utcnow()
    practitioner = practitioner or _practitioner_context_fallback()
    location = location or {}
    uf_code, room, bed, pv1_3 = (
        location.get("code", ""), location.get("room", ""),
        location.get("bed", ""), location.get("pv1_3", ""),
    )
    tokens = {
        "{{play.key}}": play_key,
        "{{patient.ipp}}": ids.get("ipp") or "",
        "{{dossier.nda}}": ids.get("nda") or "",
        "{{venue.id}}": ids.get("venue") or "",
        "{{step.order}}": str(order),
        "{{message.control_id}}": f"{play_key}-{order:03d}",
        # HPRIM limite l'identifiant de message et n'accepte pas le format
        # libre du contrôle HL7 (ex. ``PLAY-…``). La valeur est alphanumérique,
        # déterministe dans le jeu et distincte à chaque étape.
        "{{hprim.message_id}}": f"H{play_key.rsplit('-', 1)[-1]}{order:03d}",
        "{{movement.id}}": f"MVT-{play_key}-{order:03d}",
        "{{patient.family}}": identity.family,
        "{{patient.given}}": identity.given,
        "{{patient.birth_date}}": identity.birth_date.strftime("%Y%m%d"),
        "{{date}}": now.strftime("%Y%m%d"),
        "{{time}}": now.strftime("%H%M%S"),
        # Variantes explicites pour les templates XML HPRIM. Les formes HL7
        # compactes ci-dessus restent nécessaires aux messages ADT.
        "{{hprim.date}}": now.date().isoformat(),
        "{{hprim.date_time}}": now.isoformat(timespec="seconds"),
        "{{hprim.time}}": now.strftime("%H:%M:%S"),
        "{{hprim.patient_birth_date}}": identity.birth_date.isoformat(),
        "{{uf.code}}": uf_code or f"UF-{play_key[-6:]}",
        "{{uf.room}}": room,
        "{{uf.bed}}": bed,
        "{{uf.pv1_3}}": pv1_3,
        "{{target.uf.code}}": uf_code,
        "{{target.uf.room}}": room,
        "{{target.uf.bed}}": bed,
        "{{target.uf.pv1_3}}": pv1_3,
        "{{practitioner.id}}": practitioner["id"],
        "{{practitioner.rpps}}": practitioner["rpps"],
        "{{practitioner.adeli}}": practitioner["adeli"],
        "{{practitioner.family}}": practitioner["family"],
        "{{practitioner.given}}": practitioner["given"],
        "{{practitioner.prefix}}": practitioner["prefix"],
        "{{practitioner.name}}": practitioner["name"],
        "{{practitioner.xcn}}": practitioner["xcn"],
        "{{practitioner.specialty}}": practitioner["specialty"],
        "{{medecin.id}}": practitioner["id"],
        "{{medecin.rpps}}": practitioner["rpps"],
        "{{medecin.adeli}}": practitioner["adeli"],
        "{{medecin.nom}}": practitioner["family"],
        "{{medecin.prenom}}": practitioner["given"],
        "{{medecin.nom_complet}}": practitioner["name"],
        "{{medecin.xcn}}": practitioner["xcn"],
        "{{sender.code}}": "MEDBRIDGE",
        "{{intervention.id}}": f"INT-{play_key[-8:]}",
        "{{act.id}}": f"ACT-{play_key[-8:]}",
        "{{act.code}}": "TEST001",
        "{{care.pathway}}": "oriente",
        "{{organization.code}}": "MEDBRIDGE",
        "{{organization.oid}}": "1.2.250.1.213.1.1.4",
        "{{group.code}}": "GR-TEST",
        "{{billing.value}}": "0",
        "{{beneficiary.name}}": identity.family,
        "{{beneficiary.given}}": identity.given,
        "{{beneficiary.birth_date}}": identity.birth_date.strftime("%Y%m%d"),
    }
    # Les scénarios du pont historique utilisent ces jetons. Les convertir ici
    # permet de rejouer son catalogue sans conserver des identifiants fixes.
    legacy = {
        "$IPP$": "{{patient.ipp}}", "$NIP$": "{{patient.ipp}}", "$NDA$": "{{dossier.nda}}",
        "$VENUE$": "{{venue.id}}", "$UF$": "{{uf.code}}", "$DATE$": "{{date}}", "$HEURE$": "{{time}}",
        "$RPPS$": "{{practitioner.rpps}}", "$ADELI$": "{{practitioner.adeli}}",
        "$NOM$": "{{patient.family}}", "$PRENOM$": "{{patient.given}}",
        "$DOSSIER$": "{{dossier.nda}}", "$EMETTEUR$": "{{sender.code}}", "$INTERVENTION$": "{{intervention.id}}",
        "$IDACTE$": "{{act.id}}", "$ACTE$": "{{act.code}}", "$PSC$": "{{care.pathway}}",
        "$ADELI2$": "{{practitioner.adeli}}", "$ADELI_EXT$": "{{practitioner.adeli}}", "$CODE_SIH$": "{{organization.code}}",
        "$ESPACE_DE_NOM_MEDECIN_SIH$": "{{organization.oid}}", "$GR$": "{{group.code}}", "$UF_EXT$": "{{uf.code}}",
        "$caisse$": "{{billing.value}}", "$centre$": "{{billing.value}}", "$exercice$": "{{billing.value}}", "$finess$": "{{organization.code}}",
        "$montantlot11$": "{{billing.value}}", "$numlot$": "{{billing.value}}", "$numsecu$": "{{billing.value}}", "$numtitre$": "{{billing.value}}",
        "$nombeneficiaire$": "{{beneficiary.name}}", "$prenombeneficiaire$": "{{beneficiary.given}}", "$datenaissance$": "{{beneficiary.birth_date}}", "$datetraitement$": "{{date}}",
    }
    return {**tokens, **{old: tokens[new] for old, new in legacy.items()}}


def _practitioner_context_fallback() -> dict[str, str]:
    """Valeur de secours interne pour les appels unitaires de compilation."""
    return {
        "id": "00000000000", "rpps": "00000000000", "adeli": "000000000",
        "family": "MEDECIN", "given": "SCENARIO", "prefix": "Dr", "specialty": "",
        "name": "Dr SCENARIO MEDECIN",
        "xcn": "00000000000^MEDECIN^SCENARIO^^^Dr^^RPPS^1.2.250.1.71.4.2.1^L",
    }


def _replace_tokens(payload: str, tokens: dict[str, str]) -> str:
    for source, destination in tokens.items():
        payload = payload.replace(source, destination)
    return payload


def _normalize_hl7_line_endings(payload: str) -> str:
    """Accepte les séparateurs HL7 réels et leur représentation JSON ``\\r``.

    Certains exports historiques ont sérialisé les retours chariot en deux
    caractères. Les convertir avant toute projection évite que le message soit
    vu comme un unique segment MSH.
    """
    return (
        payload.replace("\\r\\n", "\r")
        .replace("\\n", "\r")
        .replace("\\r", "\r")
        .replace("\n", "\r")
    )


def _set_hl7_field(payload: str, segment: str, field: int, value: str) -> str:
    lines = _normalize_hl7_line_endings(payload).replace("\r", "\n").split("\n")
    for index, line in enumerate(lines):
        if line.startswith(f"{segment}|"):
            fields = line.split("|")
            while len(fields) <= field:
                fields.append("")
            fields[field] = value
            lines[index] = "|".join(fields)
            break
    return "\r".join(line for line in lines if line)


def _set_hl7_fields(payload: str, segment: str, field: int, value: str) -> str:
    """Remplace un champ pour toutes les occurrences d'un segment HL7."""
    lines = _normalize_hl7_line_endings(payload).replace("\r", "\n").split("\n")
    for index, line in enumerate(lines):
        if not line.startswith(f"{segment}|"):
            continue
        fields = line.split("|")
        while len(fields) <= field:
            fields.append("")
        fields[field] = value
        lines[index] = "|".join(fields)
    return "\r".join(line for line in lines if line)


def _hl7_field(payload: str, segment: str, field: int) -> str:
    for line in _normalize_hl7_line_endings(payload).replace("\r", "\n").split("\n"):
        if line.startswith(f"{segment}|"):
            values = line.split("|")
            return values[field] if len(values) > field else ""
    return ""


def _source_movement_id(payload: str) -> str:
    """Valeur source de ZBE-1, hors autorité d'affectation."""
    return _hl7_field(payload, "ZBE", 1).split("^", 1)[0].strip()


def _source_venue_id(payload: str) -> str:
    """Valeur source de PV1-19, hors autorité d'affectation."""
    return _hl7_field(payload, "PV1", 19).split("^", 1)[0].strip()


def _rewrite_zbe_original_reference(payload: str, movement_ids: dict[str, str]) -> str:
    """Projette ZBE-6 vers l'identifiant régénéré du mouvement d'origine."""
    original = _hl7_field(payload, "ZBE", 6)
    original_id = original.split("^", 1)[0].strip()
    replacement = movement_ids.get(original_id)
    if not replacement:
        return payload
    # ZBE-6 peut contenir soit un trigger, soit une référence composite. Seule
    # une référence présente dans ZBE-1 du scénario doit être réécrite.
    suffix = original[len(original_id):]
    return _set_hl7_field(payload, "ZBE", 6, replacement + suffix)


def _movement_ids_for_steps(
    source_steps: Iterable[InteropScenarioStep], play_key: str
) -> tuple[dict[int, str], dict[int, str], dict[str, str]]:
    """Construit les identifiants ZBE d'un jeu, dans l'ordre des étapes.

    Un même ZBE-1 historique peut être présent dans plusieurs ``INSERT``.
    Chaque insertion doit néanmoins être un mouvement différent dans la base
    cible. Les ``UPDATE`` et ``CANCEL`` gardent, eux, l'identifiant du dernier
    mouvement généré pour la valeur source afin de conserver leur référence.
    """
    by_step: dict[int, str] = {}
    references_by_step: dict[int, str] = {}
    current_by_source: dict[str, str] = {}
    for step in sorted(source_steps, key=lambda item: item.order_index):
        if (step.message_format or "hl7").lower() != "hl7" or step.id is None:
            continue
        source_id = _source_movement_id(step.payload)
        if not source_id:
            continue
        action = _hl7_field(step.payload, "ZBE", 4).strip().upper()
        is_mutation = action in {"UPDATE", "CANCEL", "DELETE"}
        movement_id = current_by_source.get(source_id) if is_mutation else None
        if not movement_id:
            # mouvement.mouvement_seq est numérique dans le modèle métier.
            movement_id = str(generate_venue_seq())
        by_step[step.id] = movement_id
        current_by_source[source_id] = movement_id

        original_id = _hl7_field(step.payload, "ZBE", 6).split("^", 1)[0].strip()
        if original_id and original_id in current_by_source:
            references_by_step[step.id] = current_by_source[original_id]
    return by_step, references_by_step, current_by_source


def _venue_ids_for_steps(source_steps: Iterable[InteropScenarioStep]) -> dict[str, str]:
    """Conserve une venue générée par numéro de venue historique distinct."""
    result: dict[str, str] = {}
    for step in source_steps:
        if (step.message_format or "hl7").lower() != "hl7":
            continue
        source_id = _source_venue_id(step.payload)
        if source_id:
            result.setdefault(source_id, str(generate_venue_seq()))
    return result


def _ensure_hl7_sender_context(payload: str) -> str:
    """Complète l'en-tête minimum d'un export de scénario historique.

    Quelques messages A28 de l'ancien catalogue avaient MSH-3 vide. Ils ne
    peuvent alors pas être acceptés par un récepteur HL7, indépendamment de
    leur contenu PAM. Les valeurs déjà fournies par le scénario sont
    préservées ; seules MSH-3 et MSH-4, obligatoires, reçoivent une identité
    locale de secours.
    """
    lines = _normalize_hl7_line_endings(payload).replace("\r", "\n").split("\n")
    for index, line in enumerate(lines):
        if not line.startswith("MSH|"):
            continue
        fields = line.split("|")
        while len(fields) <= 3:
            fields.append("")
        fields[2] = fields[2] or "MEDBRIDGE"
        fields[3] = fields[3] or "MEDBRIDGE"
        lines[index] = "|".join(fields)
        break
    return "\r".join(line for line in lines if line)


def _source_hl7_event_time(payload: str) -> Optional[datetime]:
    for segment, field in (("ZBE", 2), ("EVN", 2), ("MSH", 7), ("PV1", 44)):
        value = _hl7_field(payload, segment, field)
        for pattern, length in (("%Y%m%d%H%M%S", 14), ("%Y%m%d%H%M", 12), ("%Y%m%d", 8)):
            try:
                return datetime.strptime(value[:length], pattern)
            except ValueError:
                continue
    return None


def _scenario_event_times(steps: list[InteropScenarioStep]) -> dict[int, str]:
    """Rebase les dates et impose une minute entre mouvements HL7."""
    result: dict[int, str] = {}
    previous_source: Optional[datetime] = None
    previous_target: Optional[datetime] = None
    for step in sorted(steps, key=lambda item: item.order_index):
        if (step.message_format or "hl7").lower() != "hl7":
            continue
        source = _source_hl7_event_time(step.payload or "")
        if previous_target is None:
            target = datetime.utcnow().replace(second=0, microsecond=0)
        elif source and previous_source and source > previous_source:
            target = previous_target + max(source - previous_source, timedelta(minutes=1))
        else:
            target = previous_target + timedelta(minutes=1)
        result[step.id] = target.isoformat()
        previous_source, previous_target = source or previous_source, target
    return result


def _apply_hl7_event_time(payload: str, event_time: Optional[datetime | str]) -> str:
    if not event_time:
        return payload
    if isinstance(event_time, str):
        event_time = datetime.fromisoformat(event_time)
    value = event_time.strftime("%Y%m%d%H%M%S")
    for segment, field in (("MSH", 7), ("EVN", 2), ("ZBE", 2), ("PV1", 44), ("PV1", 45)):
        if _hl7_field(payload, segment, field):
            payload = _set_hl7_field(payload, segment, field, value)
    return payload


def _replace_hardcoded_practitioner_in_hl7(payload: str, practitioner: dict[str, str]) -> str:
    """Projette le praticien du jeu sur les positions XCN cliniques usuelles.

    Le remplacement est volontairement limité aux rôles de professionnel : il
    ne touche ni les données patient, ni l'autorité émettrice des segments.
    """
    xcn = practitioner.get("xcn", "")
    if not xcn:
        return payload
    for field in (7, 8, 17):
        payload = _set_hl7_fields(payload, "PV1", field, xcn)
    return _set_hl7_fields(payload, "ROL", 4, xcn)


def _compile_hl7(
    session: Session,
    scenario: InteropScenario,
    step: InteropScenarioStep,
    payload: str,
    identity: PatientIdentity,
    context: dict[str, Any],
    play_key: str,
) -> str:
    ids = dict(context["identifiers"])
    source_venue_id = _source_venue_id(step.payload)
    if source_venue_id and context.get("venue_ids", {}).get(source_venue_id):
        ids["venue"] = context["venue_ids"][source_venue_id]
    payload = _replace_tokens(
        _normalize_hl7_line_endings(payload),
        _token_values(play_key, identity, ids, step.order_index, context.get("practitioner"), context.get("location")),
    )
    # La transformation de contexte requiert un endpoint cible. À ce stade le
    # payload est compilé une seule fois et partagé entre ses livraisons : il ne
    # faut donc pas tenter un appel incomplet (il était systématiquement masqué
    # par un ``except: pass``) ni injecter la configuration d'une cible au hasard.
    # Les champs communs au jeu sont normalisés plus bas, de manière déterministe.
    payload = apply_patient_identity_to_hl7(payload, identity)
    namespaces = context["namespaces"]
    ipp = _namespace(session, scenario.ght_context_id, "IPP") if namespaces["ipp"] else None
    nda = _namespace(session, scenario.ght_context_id, "NDA") if namespaces["nda"] else None
    venue = _namespace(session, scenario.ght_context_id, "VN") if namespaces["venue"] else None
    if ipp and nda:
        payload, _ = replace_identifiers_in_hl7_message(payload, session, ipp, nda, venue, generated_ids=ids)
    else:
        # A test context without namespaces still uses a stable identity across
        # all HL7 steps in the same play.
        payload = _set_hl7_field(payload, "PID", 3, ids["ipp"] or "")
        payload = _set_hl7_field(payload, "PID", 18, ids["nda"] or "")
        payload = _set_hl7_field(payload, "PV1", 19, ids["venue"] or ids["nda"] or "")
        payload = _set_hl7_field(payload, "PV1", 50, ids["venue"] or "")
    payload = _ensure_hl7_sender_context(payload)
    payload = _set_hl7_field(payload, "MSH", 9, f"{play_key}-{step.order_index:03d}")
    # ZBE-1 identifies the movement in IHE PAM; keeping it deterministic in
    # the play preserves referential integrity without relying on CPage ZBE-9.
    movement_ids = context.get("movement_ids", {})
    reference_id = context.get("movement_reference_ids", {}).get(step.id)
    if reference_id:
        source_reference = _hl7_field(payload, "ZBE", 6)
        source_reference_id = source_reference.split("^", 1)[0].strip()
        payload = _rewrite_zbe_original_reference(payload, {source_reference_id: reference_id})
    movement_id = (
        context.get("movement_ids_by_step", {}).get(step.id)
        or movement_ids.get(_source_movement_id(step.payload))
        or str(generate_venue_seq())
    )
    payload = _set_hl7_field(payload, "ZBE", 1, movement_id)
    if context.get("location", {}).get("pv1_3"):
        payload = _set_hl7_field(payload, "PV1", 3, context["location"]["pv1_3"])
    if context.get("location", {}).get("code"):
        # En PAM France, ZBE-7 porte l'UF responsable du mouvement. Les
        # exports historiques y conservent souvent une UF CPage étrangère à la
        # destination ; elle doit suivre la même projection que PV1-3.
        payload = _set_hl7_field(payload, "ZBE", 7, context["location"]["code"])
    payload = _replace_hardcoded_practitioner_in_hl7(payload, context["practitioner"])
    return _apply_hl7_event_time(payload, context.get("event_time"))


def _adapt_fhir(obj: Any, tokens: dict[str, str]) -> Any:
    if isinstance(obj, str):
        return _replace_tokens(obj, tokens)
    if isinstance(obj, list):
        return [_adapt_fhir(item, tokens) for item in obj]
    if not isinstance(obj, dict):
        return obj
    obj = {key: _adapt_fhir(value, tokens) for key, value in obj.items()}
    if obj.get("resourceType") == "Patient":
        identifiers = obj.setdefault("identifier", [])
        if identifiers:
            identifiers[0]["value"] = tokens["{{patient.ipp}}"]
        else:
            identifiers.append({"value": tokens["{{patient.ipp}}"], "type": {"text": "IPP"}})
    if obj.get("resourceType") == "Encounter":
        identifiers = obj.setdefault("identifier", [])
        if identifiers:
            identifiers[0]["value"] = tokens["{{venue.id}}"]
        else:
            identifiers.append({"value": tokens["{{venue.id}}"], "type": {"text": "Venue"}})
        if tokens.get("{{target.uf.code}}"):
            obj["location"] = [{"location": {"display": tokens["{{target.uf.code}}"]}}]
        if tokens.get("{{practitioner.rpps}}") or tokens.get("{{practitioner.adeli}}"):
            practitioner_id = tokens.get("{{practitioner.rpps}}") or tokens.get("{{practitioner.adeli}}")
            obj["participant"] = [{
                "type": [{"coding": [{"code": "ATND", "system": "http://terminology.hl7.org/CodeSystem/v3-ParticipationType"}]}],
                "individual": {"display": tokens.get("{{practitioner.name}}", practitioner_id), "identifier": {"value": practitioner_id}},
            }]
    if obj.get("resourceType") == "Bundle":
        obj["id"] = tokens["{{play.key}}"]
    if obj.get("resourceType") == "Practitioner":
        identifiers = []
        if tokens["{{practitioner.rpps}}"]:
            identifiers.append({"system": "urn:oid:1.2.250.1.71.4.2.1", "value": tokens["{{practitioner.rpps}}"]})
        if tokens["{{practitioner.adeli}}"]:
            identifiers.append({"system": "urn:oid:1.2.250.1.71.4.2.1.1", "value": tokens["{{practitioner.adeli}}"]})
        obj["identifier"] = identifiers
        obj["name"] = [{
            "use": "official",
            "family": tokens["{{practitioner.family}}"],
            "given": [tokens["{{practitioner.given}}"]],
            "prefix": [tokens["{{practitioner.prefix}}"]],
        }]
    return obj


def _compile_payload(
    session: Session, scenario: InteropScenario, step: InteropScenarioStep, identity: PatientIdentity, context: dict[str, Any], play_key: str
) -> str:
    kind = (step.message_format or "hl7").lower()
    if kind in {"hprim", "hprimxml"}:
        kind = "xml"
    if kind == "hl7":
        return _compile_hl7(session, scenario, step, step.payload, identity, context, play_key)
    tokens = _token_values(
        play_key, identity, context["identifiers"], step.order_index, context.get("practitioner"), context.get("location")
    )
    if kind == "xml":
        # Les exports historiques partagent les mêmes marqueurs que HL7
        # (notamment $DATE$). En HPRIM ils doivent être rendus conformément à
        # xs:date/xs:time, sans modifier les dates littérales du template.
        tokens = {
            **tokens,
            "{{date}}": tokens["{{hprim.date}}"],
            "{{time}}": tokens["{{hprim.time}}"],
            "{{patient.birth_date}}": tokens["{{hprim.patient_birth_date}}"],
            "{{beneficiary.birth_date}}": tokens["{{hprim.patient_birth_date}}"],
            "$DATE$": tokens["{{hprim.date}}"],
            "$HEURE$": tokens["{{hprim.time}}"],
            "$datetraitement$": tokens["{{hprim.date}}"],
            "$datenaissance$": tokens["{{hprim.patient_birth_date}}"],
        }
    raw = _replace_tokens(step.payload, tokens)
    if kind in {"fhir", "json"}:
        try:
            return json.dumps(_adapt_fhir(json.loads(raw), tokens), ensure_ascii=False, indent=2)
        except json.JSONDecodeError as exc:
            raise ScenarioPlayError(f"Étape #{step.order_index}: JSON/FHIR invalide: {exc.msg}") from exc
    if kind == "xml":
        # Des exports de l'ancien outil préfixaient parfois le XML par ``MSH|``.
        # Ce n'est pas un segment HPRIM : on le retire avant la validation XML.
        raw = re.sub(r"^\s*MSH\|(?=<)", "", raw)
        return _adapt_hprim_xml(raw, tokens)
    return raw


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _adapt_hprim_xml(payload: str, tokens: dict[str, str]) -> str:
    """Project the common HPRIM identity/message references when XML is valid.

    This deliberately keeps unknown HPRIM extensions untouched. Templates can
    always use explicit tokens; the structural adaptation covers the canonical
    HPRIM patient/venue/message nodes emitted by this application.
    """
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        raise ScenarioPlayError(f"Payload HPRIM XML invalide: {exc}") from exc
    for element in root.iter():
        if _local_name(element.tag) == "identifiantMessage":
            element.text = tokens["{{hprim.message_id}}"]
    for element in root.iter():
        if _local_name(element.tag) == "patient":
            value = next((node for node in element.iter() if _local_name(node.tag) == "valeur"), None)
            if value is not None:
                value.text = tokens["{{patient.ipp}}"]
        elif _local_name(element.tag) == "venue":
            value = next((node for node in element.iter() if _local_name(node.tag) in {"valeur", "emetteur"}), None)
            if value is not None:
                value.text = tokens["{{venue.id}}"]
        elif _local_name(element.tag) in {"uf", "ufResponsable", "uniteFonctionnelle", "uniteFonctionnelleResponsable", "codeUF"}:
            if tokens.get("{{target.uf.code}}"):
                element.text = tokens["{{target.uf.code}}"]
        elif _local_name(element.tag) == "lettreCle" and (element.text or "").strip() == "TEST001":
            # ``$ACTE$`` est un jeton générique du catalogue historique. Sa
            # valeur CCAM de démonstration (TEST001) est valide pour CCAM mais
            # pas pour une lettre-clé NGAP. Une valeur NGAP neutre, valide et
            # explicite évite de transformer ces scénarios positifs en faux
            # tests d'erreur.
            element.text = "AMK"
    _replace_hardcoded_practitioner_in_hprim(root, tokens)
    return ET.tostring(root, encoding="unicode")


def _replace_hardcoded_practitioner_in_hprim(root: ET.Element, tokens: dict[str, str]) -> None:
    """Projette le professionnel du jeu dans les nœuds HPRIM cliniques.

    Les noms patients sont explicitement exclus : seuls les identifiants et
    personnes des médecins, exécutants, prescripteurs, prestataires ou acteurs
    sont remplacés. Une identité absente est retirée plutôt que rendue vide,
    afin de ne pas produire un XML HPRIM invalide.
    """
    parent_map = {child: parent for parent in root.iter() for child in parent}

    def within_patient(element: ET.Element) -> bool:
        current = element
        while current in parent_map:
            current = parent_map[current]
            if _local_name(current.tag) == "patient":
                return True
        return False

    def set_or_remove(element: ET.Element, value: str) -> None:
        if value:
            element.text = value
        else:
            parent = parent_map.get(element)
            if parent is not None:
                parent.remove(element)

    for element in list(root.iter()):
        local_name = _local_name(element.tag)
        if local_name in {"noRPPS", "numeroRPPS"}:
            set_or_remove(element, tokens["{{practitioner.rpps}}"])
        elif local_name in {"numeroAdeli", "noADELI"}:
            set_or_remove(element, tokens["{{practitioner.adeli}}"])
        elif not within_patient(element) and local_name in {"nomUsuel", "nomExercice"}:
            element.text = tokens["{{practitioner.family}}"]
        elif not within_patient(element) and local_name in {"prenom", "prenomExercice"}:
            element.text = tokens["{{practitioner.given}}"]

    # Plusieurs exports CPage historiques ne portent dans ``acteur`` qu'un
    # code interne (sans identité de personne). Lorsqu'un scénario est envoyé
    # vers une destination, ce code ne doit ni survivre tel quel ni être
    # interprété comme un professionnel incomplet : on le matérialise avec le
    # médecin résolu pour la cible. On complète uniquement les nœuds déjà
    # présents, afin de respecter les scénarios qui testent explicitement
    # l'absence d'un prescripteur ou d'un exécutant.
    def qualified_tag(name: str) -> str:
        return f"{{{root.tag.split('}', 1)[0][1:]}}}{name}" if root.tag.startswith("{") else name
    for element in list(root.iter()):
        if within_patient(element) or _local_name(element.tag) not in {"acteur", "medecin"}:
            continue
        has_person = any(_local_name(node.tag) == "personne" for node in element.iter())
        has_rpps = any(_local_name(node.tag) in {"noRPPS", "numeroRPPS"} and (node.text or "").strip() for node in element.iter())
        if not has_rpps and tokens["{{practitioner.rpps}}"]:
            ET.SubElement(element, qualified_tag("noRPPS")).text = tokens["{{practitioner.rpps}}"]
        if not has_person:
            person = ET.SubElement(element, qualified_tag("personne"))
            ET.SubElement(person, qualified_tag("nomUsuel")).text = tokens["{{practitioner.family}}"]
            prenoms = ET.SubElement(person, qualified_tag("prenoms"))
            ET.SubElement(prenoms, qualified_tag("prenom")).text = tokens["{{practitioner.given}}"]


def _transport_for(endpoint: SystemEndpoint, message_format: str) -> Optional[str]:
    fmt = (message_format or "").lower()
    if fmt in {"hprim", "hprimxml"}:
        fmt = "xml"
    kind = (endpoint.kind or "").upper()
    if fmt == "hl7" and kind == "MLLP":
        return "MLLP"
    if fmt in {"fhir", "json"} and kind == "FHIR":
        return "FHIR"
    if fmt == "xml" and kind in {"HPRIM", "FILE"}:
        return "FILE"
    if kind in {"FTP", "SFTP"} and fmt in {"hl7", "xml", "json", "fhir"}:
        return kind
    if kind == "FILE" and fmt in {"hl7", "xml", "json", "fhir"}:
        return "FILE"
    return None


def _routed_endpoints(
    step: InteropScenarioStep,
    endpoints: list[SystemEndpoint],
) -> list[SystemEndpoint]:
    """Applique le routage fonctionnel d'une étape aux endpoints compatibles."""
    compatible = [endpoint for endpoint in endpoints if _transport_for(endpoint, step.message_format)]
    mode = (step.route_mode or "all_compatible").strip().lower()
    if mode == "all_compatible":
        return compatible
    if mode == "explicit":
        try:
            raw_ids = json.loads(step.endpoint_ids_json or "[]")
        except json.JSONDecodeError as exc:
            raise ScenarioPlayError(f"Étape #{step.order_index}: endpoint_ids_json invalide") from exc
        if not isinstance(raw_ids, list) or not all(isinstance(item, int) for item in raw_ids):
            raise ScenarioPlayError(f"Étape #{step.order_index}: endpoint_ids_json doit être une liste d'entiers")
        allowed = set(raw_ids)
        return [endpoint for endpoint in compatible if endpoint.id in allowed]
    if mode == "target_system":
        expected = target_key(step.target_system_key or "")
        if not expected:
            raise ScenarioPlayError(f"Étape #{step.order_index}: système cible non renseigné")
        return [
            endpoint for endpoint in compatible
            if target_key(endpoint.target_system_key or endpoint.name) == expected
        ]
    raise ScenarioPlayError(f"Étape #{step.order_index}: mode de routage inconnu ({step.route_mode})")


def _strict_output_validation(session: Session, scenario: InteropScenario) -> bool:
    """Les scénarios approuvés positifs ne peuvent jamais émettre un payload invalide.

    Les brouillons/non qualifiés conservent leurs diagnostics dans le jeu afin
    de rester éditables. Les scénarios négatifs doivent, eux, pouvoir envoyer
    le message volontairement fautif au système cible.
    """
    review = session.exec(
        select(ScenarioCatalogReview).where(ScenarioCatalogReview.scenario_id == scenario.id)
    ).first()
    try:
        expected = json.loads(scenario.expected_outcome_json or "{}")
    except json.JSONDecodeError:
        expected = {}
    return bool(review and review.status == "approved" and expected.get("mode", "positive") != "negative")


def prepare_scenario_play(
    session: Session,
    scenario: InteropScenario,
    endpoints: Iterable[SystemEndpoint],
    *,
    dry_run: bool = False,
    step_id: Optional[int] = None,
    start_order_index: Optional[int] = None,
    error_policy: str = "continue_other_targets",
    allow_inactive: bool = False,
) -> ScenarioPlay:
    """Create a durable play and its compiled, immutable deliveries.

    ``allow_inactive`` is reserved for a dry-run produced by the scenario
    authoring workspace. It never authorizes an actual emission.
    """
    if allow_inactive and not dry_run:
        raise ScenarioPlayError("Un scénario inactif peut uniquement être prévisualisé à blanc.")
    targets = list({endpoint.id: endpoint for endpoint in endpoints if endpoint.id is not None}.values())
    if not targets:
        raise ScenarioPlayError("Sélectionnez au moins un endpoint actif.")
    disabled = [endpoint.name for endpoint in targets if not endpoint.is_enabled]
    if disabled:
        raise ScenarioPlayError("Endpoint désactivé : " + ", ".join(disabled))
    invalid_roles = [endpoint.name for endpoint in targets if (endpoint.role or "").lower() not in {"sender", "both"}]
    if invalid_roles:
        raise ScenarioPlayError("Endpoint non émetteur : " + ", ".join(invalid_roles))
    precondition_failures = [
        f"{endpoint.name}: {result.message}"
        for endpoint in targets
        for result in validate_preconditions(scenario, endpoint)
        if not (allow_inactive and result.assertion.get("type") == "scenario_active")
        if not result.passed
    ]
    if precondition_failures:
        raise ScenarioPlayError("Préconditions non satisfaites : " + "; ".join(precondition_failures))
    source_steps = sorted(scenario.steps or [], key=lambda item: item.order_index)
    if step_id is not None:
        source_steps = [step for step in source_steps if step.id == step_id]
    elif start_order_index is not None:
        source_steps = [step for step in source_steps if step.order_index >= start_order_index]
    if not source_steps:
        raise ScenarioPlayError("Le scénario ne contient aucune étape à émettre.")
    play_key = f"PLAY-{uuid4().hex[:12].upper()}"
    identity = _identity_from_authoring_data(scenario, generate_patient_identity())
    context = _identifier_context(session, scenario.ght_context_id, play_key)
    context["patient"] = identity.as_dict()
    context["practitioner"] = _practitioner_context(session)
    (
        context["movement_ids_by_step"],
        context["movement_reference_ids"],
        context["movement_ids"],
    ) = _movement_ids_for_steps(source_steps, play_key)
    context["venue_ids"] = _venue_ids_for_steps(source_steps)
    context["event_times"] = _scenario_event_times(source_steps)
    primary_entity_key, entity_contexts = _build_entity_contexts(
        session, scenario, source_steps, play_key, context, identity
    )
    # L'artefact du jeu décrit aussi les identités secondaires. Cela rend les
    # scénarios mère/nouveau-né ou multi-patient rejouables et auditables sans
    # exposer les identifiants fixes du catalogue historique.
    context["entities"] = {
        key: {"identifiers": item_context["identifiers"], "patient": item_identity.as_dict()}
        for key, (item_identity, item_context) in entity_contexts.items()
    }
    if error_policy not in {"stop_all", "continue_other_targets", "continue_all"}:
        raise ScenarioPlayError("Politique d'erreur inconnue")
    version = current_scenario_version(session, scenario)
    play = ScenarioPlay(
        scenario_id=scenario.id, scenario_version_id=version.id, play_key=play_key,
        ght_context_id=scenario.ght_context_id, dry_run=dry_run,
        identity_json=json.dumps(context, ensure_ascii=False), error_policy=error_policy,
    )
    session.add(play)
    session.flush()
    for endpoint in targets:
        session.add(ScenarioPlayTarget(
            play_id=play.id,
            endpoint_id=endpoint.id,
            target_system_key=target_key(endpoint.target_system_key or endpoint.name),
            is_required=True,
        ))
    unsupported = [
        f"#{step.order_index} ({(step.message_format or 'hl7').upper()})"
        for step in source_steps
        if step.is_required and not _routed_endpoints(step, targets)
    ]
    if unsupported:
        raise ScenarioPlayError(
            "Aucun endpoint compatible pour les étapes " + ", ".join(unsupported) + ". "
            "Ajoutez une destination adaptée ou limitez les étapes à émettre."
        )
    strict_validation = _strict_output_validation(session, scenario)
    schedule_at = datetime.utcnow()
    for step in source_steps:
        step_identity, step_context = _entity_for_step(step, primary_entity_key, entity_contexts)
        compatible = _routed_endpoints(step, targets)
        normalized_format = "xml" if (step.message_format or "").lower() in {"hprim", "hprimxml"} else step.message_format
        payloads: dict[int, tuple[str, dict[str, Any]]] = {}
        for endpoint in compatible:
            target_context = resolve_target_context(session, scenario, step, endpoint)
            delivery_context = {
                **step_context,
                "practitioner": target_context["practitioner"] or context["practitioner"],
                "location": target_context["location"],
                "movement_ids": context["movement_ids"],
                "movement_ids_by_step": context["movement_ids_by_step"],
                "movement_reference_ids": context["movement_reference_ids"],
                "venue_ids": context["venue_ids"],
                "event_time": context["event_times"].get(step.id),
            }
            payloads[endpoint.id] = (
                _compile_payload(session, scenario, step, step_identity, delivery_context, play_key),
                target_context,
            )
        # L'aperçu d'étape garde un payload représentatif. La copie par
        # livraison ci-dessous est l'artefact exact envoyé/rejoué.
        preview_payload = next(iter(payloads.values()))[0] if payloads else _compile_payload(session, scenario, step, step_identity, step_context, play_key)
        play_step = ScenarioPlayStep(
            play_id=play.id,
            scenario_step_id=step.id,
            order_index=step.order_index,
            name=step.name,
            message_format=normalized_format,
            message_type=step.message_type,
            source_payload=step.payload,
            compiled_payload=preview_payload,
            delay_seconds=max(step.delay_seconds or 0, 0),
            routing_json=json.dumps({
                "mode": step.route_mode or "all_compatible",
                "compatible_endpoint_ids": [endpoint.id for endpoint in compatible],
                "required": step.is_required,
            }),
        )
        session.add(play_step)
        session.flush()
        for endpoint in targets:
            transport = _transport_for(endpoint, step.message_format)
            delivery_payload, target_context = payloads.get(endpoint.id, (None, {}))
            is_routed = endpoint.id in payloads
            validation = validate_compiled_payload(delivery_payload, normalized_format) if delivery_payload else None
            if validation and strict_validation and not validation.valid:
                raise ScenarioPlayError(
                    f"Étape #{step.order_index} invalide avant émission vers {endpoint.name}: "
                    + "; ".join(validation.errors[:5])
                )
            delivery = ScenarioDelivery(
                play_id=play.id, play_step_id=play_step.id, endpoint_id=endpoint.id,
                transport=transport if is_routed else None,
                status="queued" if is_routed and not dry_run else "pending" if is_routed else "skipped",
                is_required=step.is_required,
                scheduled_at=schedule_at if is_routed else None,
                validation_status=validation.status if validation else None,
                validation_json=json.dumps(validation.to_dict(), ensure_ascii=False) if validation else None,
                error_message=None if is_routed else (
                    f"Étape non routée vers {endpoint.name}"
                    if transport else f"{step.message_format.upper()} non compatible avec endpoint {endpoint.kind}"
                ),
                compiled_payload=delivery_payload,
                target_context_json=json.dumps(target_context, ensure_ascii=False) if target_context else None,
            )
            session.add(delivery)
            session.flush()
            if is_routed and not dry_run:
                protocol = "FILE" if transport == "FILE" else transport
                message_type = step.message_type or ("HPRIM" if normalized_format == "xml" else normalized_format.upper())
                queued = enqueue_message(
                    session, endpoint_id=endpoint.id, protocol=protocol, payload=delivery_payload,
                    message_type=message_type, correlation_id=f"{play.play_key}-{step.order_index:03d}",
                    scenario_delivery_id=delivery.id,
                )
                session.flush()
                queued.next_attempt_at = schedule_at
                session.add(queued)
                delivery.outbox_id = queued.id
                session.add(delivery)
        schedule_at += timedelta(seconds=max(step.delay_seconds or 0, 0))
    session.commit()
    session.refresh(play)
    return play


async def execute_scenario_play(session: Session, play_id: int) -> ScenarioPlay:
    """Emit all compatible deliveries in the scenario order and retain evidence."""
    play = session.get(ScenarioPlay, play_id)
    if not play:
        raise ScenarioPlayError("Jeu de scénario introuvable")
    deliveries = session.exec(select(ScenarioDelivery).where(ScenarioDelivery.play_id == play.id)).all()
    steps = {item.id: item for item in session.exec(select(ScenarioPlayStep).where(ScenarioPlayStep.play_id == play.id)).all()}
    play.started_at, play.status = datetime.utcnow(), "running"
    session.add(play)
    session.commit()
    success, errors = 0, 0
    blocked_endpoints: set[int] = set()
    for delivery in sorted(deliveries, key=lambda item: (steps[item.play_step_id].order_index, item.endpoint_id)):
        delivery.updated_at = datetime.utcnow()
        if play.dry_run:
            delivery.status, delivery.finished_at = ("dry_run" if delivery.status != "skipped" else "skipped"), datetime.utcnow()
            session.add(delivery)
            continue
        if delivery.status == "skipped":
            continue
        if delivery.outbox_id:
            queued = session.get(OutboundMessage, delivery.outbox_id)
            if queued and queued.next_attempt_at > datetime.utcnow():
                # Le délai est porté par l'outbox : il survivra à un arrêt du
                # serveur et sera repris par le planificateur périodique.
                delivery.status = "queued"
                session.add(delivery)
                continue
        if play.error_policy == "continue_other_targets" and delivery.endpoint_id in blocked_endpoints:
            _block_delivery(session, delivery, "Non émise : une livraison précédente a échoué pour cette cible")
            session.commit()
            continue
        delivery.started_at = datetime.utcnow()
        try:
            if not delivery.outbox_id:
                raise ScenarioPlayError("Livraison durable absente de l'outbox")
            queued = await process_outbox_message(session, delivery.outbox_id)
            session.refresh(delivery)
            if queued.status == "sent":
                success += 1
            else:
                errors += 1
                blocked_endpoints.add(delivery.endpoint_id)
                if play.error_policy == "stop_all":
                    break
        except Exception as exc:  # preserve an error on one target without aborting all targets
            delivery.status, delivery.error_message = "error", str(exc)[:1000]
            errors += 1
            blocked_endpoints.add(delivery.endpoint_id)
            if play.error_policy == "stop_all":
                break
        delivery.finished_at, delivery.updated_at = datetime.utcnow(), datetime.utcnow()
        session.add(delivery)
        session.commit()
    if play.error_policy == "stop_all" and errors:
        for delivery in deliveries:
            if delivery.status in {"queued", "pending", "retry"}:
                _block_delivery(session, delivery, "Non émise : politique d'arrêt global après un échec")
        session.commit()
    return reconcile_scenario_play(session, play.id)


def _block_delivery(session: Session, delivery: ScenarioDelivery, reason: str) -> None:
    """Rend un blocage métier terminal aussi bien dans le jeu que l'outbox."""
    now = datetime.utcnow()
    delivery.status, delivery.error_message = "blocked", reason
    delivery.finished_at, delivery.updated_at = now, now
    session.add(delivery)
    if delivery.outbox_id:
        queued = session.get(OutboundMessage, delivery.outbox_id)
        if queued and queued.status != "sent":
            queued.status, queued.last_error, queued.updated_at = "failed", reason, now
            session.add(queued)


def reconcile_scenario_play(session: Session, play_id: int) -> ScenarioPlay:
    """Recalcule le verdict d'un jeu après un passage direct ou différé."""
    play = session.get(ScenarioPlay, play_id)
    if not play:
        raise ScenarioPlayError("Jeu de scénario introuvable")
    deliveries = session.exec(select(ScenarioDelivery).where(ScenarioDelivery.play_id == play.id)).all()
    steps = session.exec(select(ScenarioPlayStep).where(ScenarioPlayStep.play_id == play.id)).all()
    required = [item for item in deliveries if item.is_required and item.status != "skipped"]
    optional = [item for item in deliveries if not item.is_required and item.status != "skipped"]
    outstanding_statuses = {"queued", "pending", "retry"}
    error_statuses = {"error", "failed", "blocked"}
    outstanding = sum(item.status in outstanding_statuses for item in required)
    sent = sum(item.status == "sent" for item in deliveries)
    errors = sum(item.status in error_statuses for item in required)
    optional_errors = sum(item.status in error_statuses for item in optional)

    terminal = play.dry_run or outstanding == 0
    if play.dry_run:
        play.status = "dry_run"
    elif not terminal:
        play.status = "scheduled"
    elif errors and sent:
        play.status = "partial"
    elif errors:
        play.status = "error"
    else:
        play.status = "success"

    assertions: list[dict[str, Any]] = []
    assertion_failed = False
    scenario = session.get(InteropScenario, play.scenario_id)
    if terminal and scenario:
        assertions = evaluate_play_assertions(session, scenario, play, steps, deliveries)
        assertion_failed = any(not item["passed"] for item in assertions)
        if assertion_failed and play.status in {"success", "partial"}:
            play.status = "partial" if sent else "error"
    play.finished_at = datetime.utcnow() if terminal else None
    play.result_json = json.dumps({
        "sent": sent,
        "errors": errors,
        "optional_errors": optional_errors,
        "outstanding": outstanding,
        "total": len(deliveries),
        "assertions": assertions,
        "qualification_verdict": "not_evaluated" if not terminal else "failed" if assertion_failed or errors else "passed",
    }, ensure_ascii=False)
    play.updated_at = datetime.utcnow()
    session.add(play)
    refresh_play_target_states(session, play.id)
    session.commit()
    session.refresh(play)
    return play


def reconcile_scenario_plays(session: Session, play_ids: Optional[Iterable[int]] = None) -> int:
    """Synchronise les jeux touchés par le worker d'outbox."""
    ids = sorted(set(play_ids or []))
    if not ids:
        ids = list(session.exec(
            select(ScenarioPlay.id).where(ScenarioPlay.status.in_(["prepared", "running", "scheduled"]))
        ).all())
    for play_id in ids:
        reconcile_scenario_play(session, play_id)
    return len(ids)


async def retry_scenario_delivery(session: Session, delivery_id: int) -> ScenarioDelivery:
    """Retry exactly one delivery with the compiled payload of its original play."""
    delivery = session.get(ScenarioDelivery, delivery_id)
    if not delivery:
        raise ScenarioPlayError("Livraison introuvable")
    if delivery.status == "skipped":
        raise ScenarioPlayError("Une livraison incompatible ne peut pas être rejouée")
    if not delivery.outbox_id:
        raise ScenarioPlayError("Cette livraison historique n'est pas reliée à l'outbox")
    delivery.status, delivery.error_message, delivery.started_at = "queued", None, datetime.utcnow()
    session.add(delivery)
    retry_now(session, delivery.outbox_id)
    session.commit()
    await process_outbox_message(session, delivery.outbox_id)
    session.refresh(delivery)
    refresh_play_target_states(session, delivery.play_id)
    session.commit()
    return delivery


async def retry_failed_scenario_play(session: Session, play_id: int) -> ScenarioPlay:
    """Reprend seulement les livraisons non abouties d'un jeu existant.

    Les lignes déjà envoyées restent inchangées dans l'outbox : cette action ne
    doit jamais produire un doublon chez le partenaire. Les payloads compilés et
    les identifiants du jeu sont donc strictement conservés.
    """
    play = session.get(ScenarioPlay, play_id)
    if not play:
        raise ScenarioPlayError("Jeu de scénario introuvable")
    deliveries = session.exec(
        select(ScenarioDelivery).where(ScenarioDelivery.play_id == play_id)
    ).all()
    retryable = [item for item in deliveries if item.status not in {"sent", "skipped", "dry_run"}]
    if not retryable:
        raise ScenarioPlayError("Aucune livraison en échec ou en attente dans ce jeu")
    for delivery in retryable:
        if not delivery.outbox_id:
            raise ScenarioPlayError(f"Livraison #{delivery.id} historique non reliée à l'outbox")
        retry_now(session, delivery.outbox_id)
        delivery.status, delivery.error_message, delivery.finished_at = "queued", None, None
        session.add(delivery)
    session.commit()
    return await execute_scenario_play(session, play_id)


def get_play_details(session: Session, play_id: int) -> tuple[ScenarioPlay, list[ScenarioPlayStep], list[ScenarioDelivery]]:
    play = session.get(ScenarioPlay, play_id)
    if not play:
        raise ScenarioPlayError("Jeu de scénario introuvable")
    return (
        play,
        session.exec(select(ScenarioPlayStep).where(ScenarioPlayStep.play_id == play_id).order_by(ScenarioPlayStep.order_index)).all(),
        session.exec(select(ScenarioDelivery).where(ScenarioDelivery.play_id == play_id).order_by(ScenarioDelivery.play_step_id, ScenarioDelivery.endpoint_id)).all(),
    )
