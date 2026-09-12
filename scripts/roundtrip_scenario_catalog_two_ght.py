#!/usr/bin/env python3
"""Campagne de roundtrip de tous les scénarios PAM/HPRIM sur deux GHT.

Les deux environnements utilisent deux BDD SQLite distinctes. Chaque scénario
actif du catalogue consolidé est émis vers un endpoint FILE, puis ses payloads
réellement déposés sont reçus par les deux pipelines. Un résultat par scénario
est écrit dans ``result.json`` et ``report.md``.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlmodel import SQLModel, Session, create_engine, select

# Enregistre l'intégralité du modèle avant create_all sur les deux moteurs.
import app.db  # noqa: F401
from app.models import Dossier, Mouvement, Patient, Venue
from app.models_endpoints import SystemEndpoint
from app.models.hprim_models import HprimExchangeAct
from app.models_identifiers import Identifier
from app.models_outbox import OutboundMessage
from app.models_practitioners import MedecinResponsable
from app.models_scenario_runs import ScenarioDelivery, ScenarioPlayStep
from app.models_scenarios import InteropScenario, InteropScenarioStep
from app.models_scenario_target_profiles import ScenarioTargetLocation, ScenarioTargetProfile
from app.models_structure import EntiteGeographique, EntiteJuridique, GHTContext, IdentifierNamespace, Pole, Service, UniteFonctionnelle
from app.routers.roundtrip_hprim import _persist_exchange_acts, _store_roundtrip_message
from app.services.hprim import HprimService
from app.services.legacy_scenario_catalog import import_legacy_catalog
from app.services.mllp import parse_msh_fields
from app.services.scenario_play_service import execute_scenario_play, prepare_scenario_play
from app.services.transport_inbound import on_message_inbound_async


def _create_environment(path: Path, code: str) -> tuple[Any, int, int, int, dict[str, tuple[int, int]]]:
    engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        ght = GHTContext(name=f"GHT qualification {code}", code=f"ROUNDTRIP-{code}")
        session.add(ght)
        session.commit()
        session.refresh(ght)
        session.add_all([
            IdentifierNamespace(name="IPP roundtrip", type="IPP", system="urn:roundtrip:ipp", ght_context_id=ght.id),
            IdentifierNamespace(name="NDA roundtrip", type="NDA", system="urn:roundtrip:nda", ght_context_id=ght.id),
            IdentifierNamespace(name="VN roundtrip", type="VN", system="urn:roundtrip:vn", prefix_pattern="9...", ght_context_id=ght.id),
        ])
        ej = EntiteJuridique(identifier=f"EJ-ROUNDTRIP-{code}", name=f"EJ recette {code}", ght_context_id=ght.id)
        session.add(ej)
        session.flush()
        eg = EntiteGeographique(identifier=f"EG-ROUNDTRIP-{code}", name=f"Site recette {code}", entite_juridique_id=ej.id)
        session.add(eg)
        session.flush()
        pole = Pole(identifier=f"POLE-ROUNDTRIP-{code}", name="Pôle recette", entite_geo_id=eg.id, entite_juridique_id=ej.id)
        session.add(pole)
        session.flush()
        service = Service(identifier=f"SERVICE-ROUNDTRIP-{code}", name="Service recette", pole_id=pole.id)
        session.add(service)
        session.flush()
        role_data: dict[str, tuple[int, int]] = {}
        for index, (role, suffix) in enumerate((
            ("hospitalisation", "HOSP"), ("externe", "EXT"), ("urgences", "URG"),
            ("mutation", "MUT"), ("hopital_jour", "HDJ"), ("laboratoire", "LAB"),
        ), 1):
            doctor = MedecinResponsable(
                rpps=f"9{index:010d}", adeli=f"8{index:08d}", family_name=f"ROUNDTRIP{suffix}",
                given_name="Test", prefix="Dr", active=True,
            )
            session.add(doctor)
            session.flush()
            uf = UniteFonctionnelle(
                identifier=f"UF-{code}-{suffix}", name=f"UF recette {suffix}", service_id=service.id,
                medecin_responsable_id=doctor.id, status="active",
            )
            session.add(uf)
            session.flush()
            role_data[role] = (uf.id, doctor.id)
        endpoint = SystemEndpoint(name=f"Réception {code}", kind="MLLP", role="receiver", is_enabled=True)
        session.add(endpoint)
        session.commit()
        return engine, ght.id, endpoint.id, ej.id, role_data


def _configure_target_profile(session: Session, target_key: str, ej_id: int, roles: dict[str, tuple[int, int]]) -> ScenarioTargetProfile:
    """Paramètre les données cliniques explicites du logiciel cible de recette."""
    profile = ScenarioTargetProfile(
        target_system_key=target_key, name=f"Profil roundtrip {target_key}",
        entite_juridique_id=ej_id, description="UF et médecins de recette par rôle", is_active=True,
    )
    session.add(profile)
    session.flush()
    for role, (uf_id, doctor_id) in roles.items():
        session.add(ScenarioTargetLocation(
            profile_id=profile.id, role=role, unite_fonctionnelle_id=uf_id,
            medecin_responsable_id=doctor_id,
            room=f"R-{role[:3].upper()}", bed=f"L-{role[:3].upper()}",
        ))
    session.flush()
    return profile


def _ack_code(ack: str) -> str:
    for segment in ack.replace("\n", "\r").split("\r"):
        if segment.startswith("MSA|"):
            return segment.split("|")[1] if len(segment.split("|")) > 1 else "UNKNOWN"
    return "UNKNOWN"


def _ack_detail(ack: str) -> str:
    """Extrait le texte MSA d'un ACK pour qualifier l'écart sans ambiguïté."""
    for segment in ack.replace("\n", "\r").split("\r"):
        if segment.startswith("MSA|"):
            fields = segment.split("|")
            return fields[3] if len(fields) > 3 else ""
    return ""


def _payload_file(outbox: OutboundMessage, folder: Path) -> Path:
    kind = (outbox.message_type or "").upper()
    suffix = ".xml" if kind.startswith("HPRIM") else ".json" if kind in {"FHIR", "JSON", "BUNDLE"} else ".hl7"
    return folder / f"outbox_{outbox.id}{suffix}"


def _integrate_hprim(session: Session, payload: str) -> tuple[bool, str]:
    result = HprimService().traiter_message_xml(payload)
    if not result.get("succes"):
        errors = result.get("erreurs") or [result.get("erreur") or "Erreur HPRIM inconnue"]
        return False, str(errors[0])[:500]
    message = result["message"]
    _store_roundtrip_message(
        session, message_id=message.entete.message_id,
        type_message=message.entete.message_type.value, xml_content=payload,
        status="received", source="catalog-two-ght-roundtrip",
    )
    _persist_exchange_acts(session, message)
    session.commit()
    return True, "HPRIM intégré"


def _business_snapshot(session: Session) -> dict[str, Any]:
    """Empreinte métier, sans clés techniques ni horodatages de traitement."""
    def enum_value(value: Any) -> str:
        return getattr(value, "value", str(value))

    return {
        "patients": sorted((item.family, item.given, str(item.birth_date), item.gender, item.birth_family) for item in session.exec(select(Patient)).all()),
        "identifiers": sorted((item.value, enum_value(item.type), item.system, item.patient_id, item.dossier_id, item.venue_id, item.mouvement_id) for item in session.exec(select(Identifier)).all()),
        "dossiers": sorted((item.patient_id, enum_value(item.dossier_type), item.uf_responsabilite) for item in session.exec(select(Dossier)).all()),
        "venues": sorted((item.dossier_id, item.code, item.uf_responsabilite, item.label) for item in session.exec(select(Venue)).all()),
        "mouvements": sorted((item.venue_id, item.trigger_event, item.movement_type, item.location) for item in session.exec(select(Mouvement)).all()),
        "hprim": sorted((item.patient_id, item.act_type, item.code, item.action, item.payload_json) for item in session.exec(select(HprimExchangeAct)).all()),
    }


def _copy_active_catalog_from_database(session: Session) -> dict[str, int]:
    """Copie le catalogue courant dans le GHT A de recette, sans ses IDs SQL."""
    with Session(app.db.engine) as source_session:
        source_scenarios = source_session.exec(
            select(InteropScenario).where(InteropScenario.is_active == True).order_by(InteropScenario.key)  # noqa: E712
        ).all()
        copied = 0
        for original in source_scenarios:
            fields = (
                "key", "name", "description", "functional_comment", "category", "protocol", "version",
                "preconditions_json", "assertions_json", "source_path", "source_checksum", "legacy_package",
                "legacy_source_json", "tags", "is_active", "time_anchor_mode", "time_anchor_days_offset",
                "time_fixed_start_iso", "preserve_intervals", "jitter_min_minutes", "jitter_max_minutes",
                "apply_jitter_on_events",
            )
            scenario = InteropScenario(**{field: getattr(original, field) for field in fields})
            session.add(scenario)
            session.flush()
            original_steps = source_session.exec(
                select(InteropScenarioStep)
                .where(InteropScenarioStep.scenario_id == original.id)
                .order_by(InteropScenarioStep.order_index, InteropScenarioStep.id)
            ).all()
            for step in original_steps:
                session.add(InteropScenarioStep(
                    scenario_id=scenario.id, order_index=step.order_index, name=step.name,
                    description=step.description, message_format=step.message_format, message_type=step.message_type,
                    payload=step.payload, delay_seconds=step.delay_seconds, assertions_json=step.assertions_json,
                ))
            copied += 1
        session.commit()
    return {"source_items": copied, "scenarios": copied, "created": copied, "updated": 0, "duplicates": 0}


def _qualification_for(row: dict[str, Any]) -> str:
    """Classe les écarts sans supprimer les cas négatifs utiles.

    ``retirer_du_roundtrip_positif`` ne veut pas dire effacer le scénario : il
    doit rester dans les tests de validation négative afin de prouver le rejet.
    """
    if row["status"] == "success":
        return "conserver"
    diagnostic = row.get("diagnostic") or " ".join(str(step) for step in row.get("steps", []))
    negative_hprim_markers = (
        "XMLSyntaxError", "XML Syntax Error", "Invalid bytes",
        "Acte HPRIM UCD sans code", "CCAM_QUANTITY_001",
    )
    if any(marker in diagnostic for marker in negative_hprim_markers):
        return "retirer_du_roundtrip_positif"
    if "PATIENT_ID_001" in diagnostic:
        return "ajouter_prerequis_patient"
    if "'str' object has no attribute 'value'" in diagnostic:
        return "corriger_moteur_hprim"
    if (
        row.get("scenario_category") in {"HL7_SIU", "HL7_MIXTE"}
        or any(str(step.get("message_type") or "").upper().startswith("SIU^") for step in row.get("steps", []))
    ):
        return "corriger_hl7_siu"
    if row["key"].startswith("legacy.pam."):
        return "corriger_pam"
    return "a_qualifier"


async def _run(workdir: Path, *, catalog_source: str = "seed") -> dict[str, Any]:
    source_engine, source_ght_id, source_receiver_id, source_ej_id, source_roles = _create_environment(workdir / "ght_a.sqlite", "A")
    target_engine, target_ght_id, target_receiver_id, _, _ = _create_environment(workdir / "ght_b.sqlite", "B")
    outbox_dir = workdir / "outbox"
    outbox_dir.mkdir(parents=True, exist_ok=True)
    raw = json.loads(Path("data/all_scenarios_dump.json").read_text(encoding="utf-8"))
    from data.scenarios_hprim_seed import scenarios as hprim_scenarios
    catalog = (raw.get("scenarios", raw) if isinstance(raw, dict) else raw) + hprim_scenarios
    results: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    ack_counts: Counter[str] = Counter()
    profile_snapshot: dict[str, Any] = {}

    with Session(source_engine) as source, Session(target_engine) as target:
        imported = _copy_active_catalog_from_database(source) if catalog_source == "database" else import_legacy_catalog(source, catalog)
        file_endpoint = SystemEndpoint(name="Dépôt vers GHT B", kind="FILE", role="sender", outbox_path=str(outbox_dir), target_system_key="GHT-B")
        source.add(file_endpoint)
        profile = _configure_target_profile(source, "GHT-B", source_ej_id, source_roles)
        source.commit()
        profile_snapshot = {
            "key": profile.target_system_key, "id": profile.id,
            "entite_juridique_id": profile.entite_juridique_id, "roles": sorted(source_roles),
        }
        source_receiver = source.get(SystemEndpoint, source_receiver_id)
        target_receiver = target.get(SystemEndpoint, target_receiver_id)
        scenarios = source.exec(select(InteropScenario).where(InteropScenario.is_active == True).order_by(InteropScenario.key)).all()  # noqa: E712
        for index, scenario in enumerate(scenarios, 1):
            scenario.ght_context_id = source_ght_id
            source.add(scenario)
            source.commit()
            row: dict[str, Any] = {
                "index": index,
                "key": scenario.key,
                "name": scenario.name,
                "scenario_category": scenario.category,
                "source_checksum": scenario.source_checksum,
                "steps": [],
            }
            try:
                play = prepare_scenario_play(source, scenario, [file_endpoint])
                play = await execute_scenario_play(source, play.id)
                row["play_status"] = play.status
                deliveries = session_deliveries = source.exec(select(ScenarioDelivery).where(ScenarioDelivery.play_id == play.id)).all()
                steps = {step.id: step for step in source.exec(select(ScenarioPlayStep).where(ScenarioPlayStep.play_id == play.id)).all()}
                outbox = {message.scenario_delivery_id: message for message in source.exec(select(OutboundMessage).where(OutboundMessage.scenario_delivery_id.in_([item.id for item in deliveries]))).all()}
                for delivery in session_deliveries:
                    step = steps[delivery.play_step_id]
                    message = outbox.get(delivery.id)
                    detail = {
                        "order": step.order_index, "format": step.message_format,
                        "message_type": step.message_type, "delivery": delivery.status,
                        "target_context": json.loads(delivery.target_context_json or "{}"),
                    }
                    if not message:
                        detail.update(status="error", diagnostic="Outbox absente")
                    else:
                        output = _payload_file(message, outbox_dir)
                        if not output.exists():
                            detail.update(status="error", diagnostic=f"Fichier non déposé: {output.name}")
                        else:
                            payload = output.read_text(encoding="utf-8")
                            if step.message_format == "hl7":
                                source_ack = await on_message_inbound_async(payload, source, source_receiver)
                                target_ack = await on_message_inbound_async(payload, target, target_receiver)
                                source_code, target_code = _ack_code(source_ack), _ack_code(target_ack)
                                ack_counts[source_code] += 1
                                detail.update(
                                    source_ack=source_code, target_ack=target_code,
                                    source_ack_detail=_ack_detail(source_ack), target_ack_detail=_ack_detail(target_ack),
                                )
                                detail["status"] = "accepted" if source_code == target_code == "AA" else "rejected" if source_code == target_code else "mismatch"
                            elif step.message_format == "xml":
                                source_ok, source_info = _integrate_hprim(source, payload)
                                target_ok, target_info = _integrate_hprim(target, payload)
                                detail.update(source_hprim=source_info, target_hprim=target_info)
                                detail["status"] = "accepted" if source_ok and target_ok else "rejected" if source_ok == target_ok else "mismatch"
                            else:
                                detail.update(status="unsupported", diagnostic=step.message_format)
                    row["steps"].append(detail)
                statuses = {item["status"] for item in row["steps"]}
                row["status"] = "success" if statuses == {"accepted"} else "partial" if "accepted" in statuses else "error"
                row["qualification"] = _qualification_for(row)
            except Exception as exc:  # one malformed legacy scenario must not stop the campaign
                row.update(status="error", diagnostic=f"{type(exc).__name__}: {str(exc)[:1000]}")
                row["qualification"] = _qualification_for(row)
            counts[row["status"]] += 1
            results.append(row)
        source_snapshot, target_snapshot = _business_snapshot(source), _business_snapshot(target)

    source_engine.dispose()
    target_engine.dispose()
    return {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "catalog_import": imported,
        "target_profile": profile_snapshot,
        "totals": dict(counts),
        "ack_totals": dict(ack_counts),
        "database_equal": source_snapshot == target_snapshot,
        "source_snapshot": {key: len(value) for key, value in source_snapshot.items()},
        "target_snapshot": {key: len(value) for key, value in target_snapshot.items()},
        "results": results,
    }


def _markdown(result: dict[str, Any]) -> str:
    totals = result["totals"]
    failures = [row for row in result["results"] if row["status"] != "success"]
    lines = [
        "# Campagne roundtrip catalogue de scénarios — deux GHT",
        "",
        f"Date : {result['generated_at']}",
        "",
        "## Résultat",
        "",
        f"- Catalogue consolidé : **{result['catalog_import']['scenarios']}** scénarios actifs.",
        f"- Profil clinique appliqué : **{result['target_profile']['key']}** ({', '.join(result['target_profile']['roles'])}).",
        f"- Scénarios entièrement acceptés : **{totals.get('success', 0)}**.",
        f"- Partiels : **{totals.get('partial', 0)}** ; en erreur : **{totals.get('error', 0)}**.",
        f"- Projections métier BDD A = BDD B : **{'oui' if result['database_equal'] else 'non'}**.",
        "",
        "## ACK PAM",
        "",
        "| Code | Nombre |",
        "|---|---:|",
        *[f"| {key} | {value} |" for key, value in sorted(result['ack_totals'].items())],
        "",
        "## Volumes BDD comparés",
        "",
        "| Entité | GHT A | GHT B |",
        "|---|---:|---:|",
        *[f"| {key} | {result['source_snapshot'][key]} | {result['target_snapshot'][key]} |" for key in result['source_snapshot']],
        "",
        "## Écarts à qualifier",
        "",
    ]
    if not failures:
        lines.append("Aucun écart.")
    else:
        lines.extend(["| Scénario | Statut | Qualification | Diagnostic |", "|---|---|---|---|"])
        for row in failures:
            detail = row.get("diagnostic") or "; ".join(
                f"#{step.get('order')} {step.get('status')} {step.get('diagnostic') or step.get('source_ack') or step.get('source_hprim') or ''}" for step in row.get("steps", []) if step.get("status") != "accepted"
            )
            lines.append(f"| `{row['key']}` | {row['status']} | {row.get('qualification', 'à qualifier')} | {str(detail).replace('|', '/')} |")
    lines.extend(["", "Le détail complet et machine-readable est disponible dans `result.json`."])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workdir", default="artifacts/roundtrip-scenarios-two-ght", help="Répertoire des deux BDD et rapports")
    parser.add_argument("--catalog-source", choices=("seed", "database"), default="seed", help="Catalogue historique brut ou catalogue courant en BDD")
    args = parser.parse_args()
    workdir = Path(args.workdir).resolve()
    workdir.mkdir(parents=True, exist_ok=True)
    result = asyncio.run(_run(workdir, catalog_source=args.catalog_source))
    (workdir / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    (workdir / "report.md").write_text(_markdown(result), encoding="utf-8")
    print((workdir / "report.md").read_text(encoding="utf-8"))
    return 0 if result["database_equal"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
