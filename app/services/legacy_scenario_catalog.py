"""Import idempotent du catalogue PAM/HPRIM de l'outil historique.

Le fichier exporté peut contenir des variantes techniques strictement
identiques. Elles sont regroupées par contenu normalisé, tout en gardant les
clés et chemins d'origine dans ``legacy_source_json`` pour l'audit.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlmodel import Session, select

from app.models.scenarios import InteropScenario, InteropScenarioStep
from app.services.scenario_qualification_service import assign_theme, ensure_theme
from app.services.scenario_import import split_embedded_messages
from app.services.scenario_naming import humanize_scenario_name
from app.services.scenario_protocol_classifier import classify_hl7_scenario


def _format(value: str | None) -> str:
    value = (value or "hl7").lower()
    return "xml" if value in {"hprim", "hprimxml"} else value


def _payload(value: str, fmt: str) -> str:
    value = (value or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if fmt == "xml":
        value = re.sub(r"^MSH\|(?=<)", "", value)
    return value


def _legacy_tokens(value: str) -> str:
    replacements = {
        "$IPP$": "{{patient.ipp}}", "$NIP$": "{{patient.ipp}}", "$NDA$": "{{dossier.nda}}",
        "$VENUE$": "{{venue.id}}", "$UF$": "{{uf.code}}", "$DATE$": "{{date}}", "$HEURE$": "{{time}}",
        "$RPPS$": "{{practitioner.rpps}}", "$ADELI$": "{{practitioner.adeli}}",
        "$NOM$": "{{patient.family}}", "$PRENOM$": "{{patient.given}}",
        "$DOSSIER$": "{{dossier.nda}}", "$EMETTEUR$": "{{sender.code}}", "$INTERVENTION$": "{{intervention.id}}",
        "$IDACTE$": "{{act.id}}", "$ACTE$": "{{act.code}}", "$PSC$": "{{care.pathway}}",
        "$ADELI2$": "{{practitioner.adeli}}", "$ADELI_EXT$": "{{practitioner.adeli}}", "$CODE_SIH$": "{{sender.code}}",
        "$ESPACE_DE_NOM_MEDECIN_SIH$": "1.2.250.1.213.1.1.4", "$GR$": "GR-TEST", "$UF_EXT$": "{{uf.code}}",
        "$caisse$": "0", "$centre$": "0", "$exercice$": "0", "$finess$": "MEDBRIDGE", "$montantlot11$": "0",
        "$numlot$": "0", "$numsecu$": "0", "$numtitre$": "0", "$nombeneficiaire$": "{{patient.family}}",
        "$prenombeneficiaire$": "{{patient.given}}", "$datenaissance$": "{{patient.birth_date}}", "$datetraitement$": "{{date}}",
    }
    for old, new in replacements.items():
        value = value.replace(old, new)
    return value


def _expand_steps(item: dict[str, Any]) -> list[dict[str, Any]]:
    """Déplie les exports historiques qui concaténaient plusieurs messages."""
    expanded: list[dict[str, Any]] = []
    for step in item.get("steps") or []:
        fmt = _format(step.get("message_format"))
        fragments = split_embedded_messages(step.get("payload", ""), fmt, step.get("message_type"))
        for message_index, fragment in enumerate(fragments, 1):
            label = step.get("name") or fragment["message_type"] or f"Message {message_index}"
            expanded.append({
                **step,
                "order_index": len(expanded) + 1,
                "name": label if len(fragments) == 1 else f"{label} — message {message_index}",
                "message_format": fragment["message_format"],
                "message_type": fragment["message_type"],
                "payload": fragment["payload"],
            })
    return expanded


def _signature(item: dict[str, Any]) -> str:
    steps = _expand_steps(item)
    source = "\n".join(
        f"{step.get('order_index', index)}:{_format(step.get('message_format'))}:{_legacy_tokens(_payload(step.get('payload', ''), _format(step.get('message_format'))))}"
        for index, step in enumerate(steps, 1)
    )
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def _theme_for(item: dict[str, Any]) -> tuple[str, str, str, str]:
    category = (item.get("category") or "").upper()
    text = " ".join(str(item.get(field) or "") for field in ("name", "description", "tags")).lower()
    if "HPRIM" in category:
        for code, label in (("ccam", "Actes CCAM"), ("ngap", "Actes NGAP"), ("ucd", "Médicaments UCD"), ("lpp", "Dispositifs LPP"), ("intervention", "Interventions")):
            if code in text:
                return "hprim", "HPRIM XML", f"hprim.{code}", label
        return "hprim", "HPRIM XML", "hprim.autres", "Autres flux HPRIM"
    hl7_family = classify_hl7_scenario(_expand_steps(item))
    if hl7_family == "siu":
        return "hl7", "HL7 v2", "hl7.siu", "Rendez-vous (SIU)"
    if hl7_family == "mixed_siu":
        return "hl7", "HL7 v2", "hl7.mixte", "Mouvements et rendez-vous"
    for code, label in (("ident", "Identité patient"), ("urgence", "Urgences"), ("matern", "Maternité"), ("séance", "Séances"), ("annul", "Annulations et corrections")):
        if code in text:
            return "pam", "IHE PAM France", f"pam.{code}", label
    return "pam", "IHE PAM France", "pam.mouvements", "Mouvements et hospitalisation"


def _comment(item: dict[str, Any]) -> str:
    return (item.get("description") or item.get("name") or "Scénario importé depuis le catalogue historique.").strip()


def import_legacy_catalog(session: Session, path: str | Path | list[dict[str, Any]]) -> dict[str, int]:
    """Importe / met à jour le catalogue ; n'efface jamais un scénario local."""
    raw = json.loads(Path(path).read_text(encoding="utf-8")) if not isinstance(path, list) else path
    items = raw.get("scenarios", raw) if isinstance(raw, dict) else raw
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in items:
        if (item.get("category") or "").upper() not in {"IHE_PAM", "HPRIM"}:
            continue
        groups[_signature(item)].append(item)
    created = updated = duplicates = 0
    for checksum, variants in groups.items():
        item = variants[0]
        scenario = session.exec(select(InteropScenario).where(InteropScenario.source_checksum == checksum)).first()
        if not scenario and item.get("key"):
            # Une évolution du normaliseur ne doit pas recréer un scénario
            # importé précédemment : sa clé historique reste une ancre stable.
            scenario = session.exec(
                select(InteropScenario)
                .where(InteropScenario.legacy_source_json.contains(f'"key": "{item["key"]}"'))
                .order_by(InteropScenario.id.desc())
            ).first()
        root_key, root_name, theme_key, theme_name = _theme_for(item)
        ensure_theme(session, root_key, root_name)
        theme = ensure_theme(session, theme_key, theme_name, parent_key=root_key)
        sources = [{"key": value.get("key"), "source_path": value.get("source_path"), "name": value.get("name")} for value in variants]
        if not scenario:
            scenario = InteropScenario(
                key=f"legacy.{root_key}.{checksum[:14]}", name=humanize_scenario_name(
                    item.get("name") or f"Catalogue {checksum[:8]}", family=root_key
                ),
                description=item.get("description"), functional_comment=_comment(item),
                category="HPRIM" if root_key == "hprim" else "HL7_SIU" if theme_key == "hl7.siu" else "HL7_MIXTE" if theme_key == "hl7.mixte" else "IHE_PAM", protocol="HPRIM" if root_key == "hprim" else "HL7",
                tags=item.get("tags"), source_path=item.get("source_path"), source_checksum=checksum,
                legacy_package=theme_key, legacy_source_json=json.dumps(sources, ensure_ascii=False),
            )
            session.add(scenario)
            session.flush()
            for index, source_step in enumerate(_expand_steps(item), 1):
                fmt = _format(source_step.get("message_format"))
                session.add(InteropScenarioStep(
                    scenario_id=scenario.id, order_index=source_step.get("order_index", index), name=source_step.get("name"),
                    description=source_step.get("description"), message_format=fmt, message_type=source_step.get("message_type"),
                    payload=_legacy_tokens(_payload(source_step.get("payload", ""), fmt)),
                    delay_seconds=source_step.get("delay_seconds"), assertions_json=source_step.get("assertions_json"),
                ))
            created += 1
        else:
            scenario.name = humanize_scenario_name(item.get("name") or scenario.name, family=root_key)
            scenario.functional_comment = scenario.functional_comment or _comment(item)
            scenario.category = "HPRIM" if root_key == "hprim" else "HL7_SIU" if theme_key == "hl7.siu" else "HL7_MIXTE" if theme_key == "hl7.mixte" else "IHE_PAM"
            scenario.protocol = "HPRIM" if root_key == "hprim" else "HL7"
            scenario.source_checksum = checksum
            scenario.legacy_package, scenario.legacy_source_json, scenario.updated_at = theme_key, json.dumps(sources, ensure_ascii=False), datetime.utcnow()
            scenario.is_active = True
            session.add(scenario)
            existing_steps = {step.order_index: step for step in session.exec(select(InteropScenarioStep).where(InteropScenarioStep.scenario_id == scenario.id)).all()}
            for index, source_step in enumerate(_expand_steps(item), 1):
                fmt = _format(source_step.get("message_format"))
                step = existing_steps.get(source_step.get("order_index", index))
                if not step:
                    step = InteropScenarioStep(scenario_id=scenario.id, order_index=source_step.get("order_index", index))
                step.name, step.description = source_step.get("name"), source_step.get("description")
                step.message_format, step.message_type = fmt, source_step.get("message_type")
                step.payload, step.delay_seconds = _legacy_tokens(_payload(source_step.get("payload", ""), fmt)), source_step.get("delay_seconds")
                step.assertions_json, step.updated_at = source_step.get("assertions_json"), datetime.utcnow()
                session.add(step)
            updated += 1
        assign_theme(session, scenario.id, theme.id, primary=True)
        duplicates += len(variants) - 1
    # A previous version of the normalizer may have calculated another hash for
    # the same historical source. Preserve that row for traceability but hide it
    # from the active catalogue: an operator must never see two technical
    # copies of one legacy scenario.
    current_checksums = set(groups)
    for scenario in session.exec(select(InteropScenario).where(InteropScenario.key.startswith("legacy."))).all():
        if scenario.source_checksum and scenario.source_checksum not in current_checksums:
            scenario.is_active = False
            scenario.updated_at = datetime.utcnow()
            session.add(scenario)
    session.commit()
    return {"source_items": sum(len(values) for values in groups.values()), "scenarios": len(groups), "created": created, "updated": updated, "duplicates": duplicates}
