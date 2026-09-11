#!/usr/bin/env python3
"""Campagne de roundtrip IHE PAM CPage sur deux environnements MLLP isolés.

Le script crée deux BDD SQLite temporaires et deux structures GHT identiques.
Les captures CPage sont injectées en MLLP dans GHT-1, puis les messages PAM
générés par MedBridge sont réellement transmis en MLLP vers GHT-2. Il produit
un JSON sans données de santé nominatives, utilisable dans un rapport d'audit.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import hashlib
import json
import os
import re
import signal
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CPAGE_DIR = ROOT / "data" / "pam"
SOURCE_PORT = 29101
TARGET_PORT = 29102

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _database_url(path: Path) -> str:
    return f"sqlite:///{path}"


def _normalise_hl7(path: Path) -> str:
    raw = path.read_text(encoding="latin-1", errors="replace")
    return "\r".join(part for part in re.split(r"\r\n|\r|\n", raw) if part)


def _cpage_files() -> list[Path]:
    return [
        path for path in sorted(CPAGE_DIR.glob("*.hl7"))
        if _normalise_hl7(path).startswith("MSH|^~\\&|CPAGE|")
    ]


def _ack_code(ack: str) -> str:
    msa = next((segment for segment in ack.split("\r") if segment.startswith("MSA|")), "")
    fields = msa.split("|")
    return fields[1] if len(fields) > 1 else "NO_MSA"


def _wait_for_port(port: int, timeout: float = 20.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.3):
                return
        except OSError:
            time.sleep(0.1)
    raise TimeoutError(f"Le serveur MLLP {port} n'est pas prêt")


def _node_environment(database: Path) -> dict[str, str]:
    env = os.environ.copy()
    env.update({
        "DATABASE_URL": _database_url(database),
        "TESTING": "0",
        "PAM_AUTO_CREATE_UF": "0",
        "MLLP_RETRY_SLEEP": "0.05",
    })
    return env


def _start_node(database: Path, port: int, role: str) -> subprocess.Popen:
    return subprocess.Popen(
        [sys.executable, str(Path(__file__).resolve()), "node", "--port", str(port), "--role", role],
        cwd=ROOT,
        env=_node_environment(database),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )


def _run_json_command(command: str, database: Path) -> dict[str, Any]:
    result = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), command], cwd=ROOT,
        env=_node_environment(database), text=True, capture_output=True,
    )
    if result.returncode:
        raise RuntimeError(f"{command} a échoué : {result.stderr.strip()}")
    return json.loads(result.stdout)


def _stop(process: subprocess.Popen) -> str:
    if process.poll() is None:
        process.send_signal(signal.SIGTERM)
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
    return process.stderr.read() if process.stderr else ""


def _create_environment(role: str, listen_port: int) -> int:
    """Crée une structure GHT complète minimale et retourne l'endpoint entrant."""
    from sqlmodel import Session
    from app.db import engine, init_db
    from app.models_endpoints import SystemEndpoint
    from app.models_structure import (
        EntiteGeographique,
        EntiteJuridique,
        GHTContext,
        IdentifierNamespace,
        Pole,
        Service,
        UniteFonctionnelle,
    )

    init_db()
    with Session(engine) as session:
        context = GHTContext(name="Roundtrip CPage", code="RT-CPAGE", oid_racine="1.2.250.1.999.77")
        session.add(context)
        session.flush()
        ej = EntiteJuridique(
            identifier="RT-EJ", name="Établissement Roundtrip", finess_ej="999999999",
            ght_context_id=context.id, strict_pam_fr=False,
        )
        session.add(ej)
        session.flush()
        eg = EntiteGeographique(identifier="RT-EG", name="Site Roundtrip", entite_juridique_id=ej.id)
        session.add(eg)
        session.flush()
        pole = Pole(identifier="RT-POLE", name="Pôle Roundtrip", entite_geo_id=eg.id, entite_juridique_id=ej.id)
        session.add(pole)
        session.flush()
        service = Service(identifier="RT-SERVICE", name="Service Roundtrip", pole_id=pole.id)
        session.add(service)
        session.flush()
        session.add(UniteFonctionnelle(identifier="7700", name="UF CPage 7700", service_id=service.id))
        for namespace_type in ("IPP", "NDA", "VN", "MVT"):
            session.add(IdentifierNamespace(
                name=f"{namespace_type} Roundtrip", system="RT-CPAGE", oid="1.2.250.1.999.77",
                type=namespace_type, entite_juridique_id=ej.id, ght_context_id=context.id,
            ))
        inbound = SystemEndpoint(
            name=f"RT-{role.upper()}-IN", kind="MLLP", role="receiver", is_enabled=True,
            host="127.0.0.1", port=listen_port, ght_context_id=context.id, entite_juridique_id=ej.id,
            pam_validate_enabled=True, pam_validate_mode="warn", pam_profile="IHE_PAM_FR",
            receiving_app=f"RT_{role.upper()}", receiving_facility="RT-CPAGE",
        )
        session.add(inbound)
        if role == "source":
            session.add(SystemEndpoint(
                name="RT-SOURCE-OUT", kind="MLLP", role="sender", is_enabled=True,
                host="127.0.0.1", port=TARGET_PORT, ght_context_id=context.id, entite_juridique_id=ej.id,
                emit_hl7_pam=True, emit_hl7_mfn=False, sending_app="RT_GHT1",
                sending_facility="RT-CPAGE", receiving_app="RT_GHT2", receiving_facility="RT-CPAGE",
            ))
        session.commit()
        return inbound.id


async def _run_node(role: str, port: int) -> None:
    # L'émission est explicitement pilotée par la phase export pour conserver
    # l'ordre Patient -> Mouvement dans la campagne reproductible.
    from sqlmodel import Session
    from app.db import engine, session_factory
    from app.models_endpoints import SystemEndpoint
    from app.services.mllp import start_mllp_server, stop_mllp_server
    from app.services.transport_inbound import on_message_inbound_async

    endpoint_id = _create_environment(role, port)
    with Session(engine) as session:
        endpoint = session.get(SystemEndpoint, endpoint_id)
        server = await start_mllp_server("127.0.0.1", port, on_message_inbound_async, endpoint, session_factory)
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        with contextlib.suppress(NotImplementedError):
            loop.add_signal_handler(sig, stop_event.set)
    await stop_event.wait()
    await stop_mllp_server(server)


def _export_source() -> dict[str, int]:
    """Émet les états intégrables de GHT-1 vers le serveur MLLP de GHT-2."""
    from sqlmodel import Session, select
    from app.db import engine
    from app.models import Mouvement, Patient
    from app.models_structure import EntiteJuridique
    from app.services.emit_on_create import emit_to_senders_async

    totals = Counter()
    with Session(engine) as session:
        ej = session.exec(select(EntiteJuridique).where(EntiteJuridique.identifier == "RT-EJ")).one()
        patients = session.exec(select(Patient).where(Patient.entite_juridique_id == ej.id).order_by(Patient.identifier)).all()
        # Le patient est émis avant ses mouvements afin que PID-3 soit toujours connu.
        for patient in patients:
            emit_to_senders_async(patient, "patient", session, operation="insert")
            totals["patient"] += 1
        movements = session.exec(select(Mouvement).where(Mouvement.entite_juridique_id == ej.id).order_by(Mouvement.when, Mouvement.id)).all()
        for movement in movements:
            emit_to_senders_async(movement, "mouvement", session, operation="insert")
            totals["mouvement"] += 1
    return dict(totals)


def _snapshot() -> dict[str, Any]:
    """Empreinte métier, sans PII, pour comparer les deux BDD."""
    from sqlmodel import Session, select
    from app.db import engine
    from app.models import Dossier, Mouvement, Patient, Venue
    from app.models_endpoints import MessageLog, SystemEndpoint
    from app.models_structure import EntiteJuridique

    def digest(rows: list[dict[str, Any]]) -> str:
        canonical = json.dumps(rows, sort_keys=True, default=str, ensure_ascii=False)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    with Session(engine) as session:
        ej = session.exec(select(EntiteJuridique).where(EntiteJuridique.identifier == "RT-EJ")).one()
        patients = session.exec(select(Patient).where(Patient.entite_juridique_id == ej.id)).all()
        patient_key = {patient.id: patient.identifier for patient in patients}
        dossiers = session.exec(select(Dossier).where(Dossier.entite_juridique_id == ej.id)).all()
        dossier_key = {dossier.id: dossier.dossier_seq for dossier in dossiers}
        venues = session.exec(select(Venue).where(Venue.entite_juridique_id == ej.id)).all()
        venue_key = {venue.id: venue.venue_seq for venue in venues}
        movements = session.exec(select(Mouvement).where(Mouvement.entite_juridique_id == ej.id)).all()
        endpoint_ids = {endpoint.id for endpoint in session.exec(select(SystemEndpoint).where(SystemEndpoint.ght_context_id == ej.ght_context_id)).all()}
        logs = session.exec(select(MessageLog).where(MessageLog.endpoint_id.in_(endpoint_ids))).all()

        patient_rows = sorted(({
            "key": patient.identifier, "family": patient.family, "given": patient.given,
            "birth_date": patient.birth_date, "gender": patient.gender, "address": patient.address,
            "city": patient.city, "postal_code": patient.postal_code, "country": patient.country,
            "marital_status": patient.marital_status, "phone": patient.phone, "mobile": patient.mobile,
            "email": patient.email, "birth_family": patient.birth_family,
        } for patient in patients), key=lambda row: row["key"] or "")
        dossier_rows = sorted(({
            "key": (patient_key.get(dossier.patient_id), dossier.dossier_seq), "uf": dossier.uf_responsabilite,
            "type": dossier.dossier_type, "admit_time": dossier.admit_time,
        } for dossier in dossiers), key=lambda row: str(row["key"]))
        venue_rows = sorted(({
            "key": (dossier_key.get(venue.dossier_id), venue.venue_seq), "uf": venue.uf_responsabilite,
            "location": venue.assigned_location, "start_time": venue.start_time,
        } for venue in venues), key=lambda row: str(row["key"]))
        movement_rows = sorted(({
            "key": (venue_key.get(movement.venue_id), movement.mouvement_seq), "trigger": movement.trigger_event,
            "type": movement.type, "when": movement.when, "status": movement.status,
            "location": movement.location, "uf_medicale": movement.uf_responsabilite,
            "uf_soins": movement.uf_soins_code, "nature": movement.nature,
        } for movement in movements), key=lambda row: str(row["key"]))
        return {
            "counts": {"patients": len(patient_rows), "dossiers": len(dossier_rows), "venues": len(venue_rows), "mouvements": len(movement_rows)},
            "hashes": {"patients": digest(patient_rows), "dossiers": digest(dossier_rows), "venues": digest(venue_rows), "mouvements": digest(movement_rows)},
            "messages": {"in": sum(log.direction == "in" for log in logs), "out": sum(log.direction == "out" for log in logs), "acks": dict(sorted(Counter(_ack_code(log.ack_payload or "") for log in logs if log.direction == "in").items()))},
        }


def _run_parent() -> int:
    with tempfile.TemporaryDirectory(prefix="medbridge-cpage-roundtrip-") as temp_dir:
        root = Path(temp_dir)
        source_db, target_db = root / "ght1.db", root / "ght2.db"
        target = _start_node(target_db, TARGET_PORT, "target")
        source = _start_node(source_db, SOURCE_PORT, "source")
        try:
            _wait_for_port(TARGET_PORT)
            _wait_for_port(SOURCE_PORT)
            from app.services.mllp import send_mllp
            inbound_acks = Counter()
            for path in _cpage_files():
                ack = asyncio.run(send_mllp("127.0.0.1", SOURCE_PORT, _normalise_hl7(path)))
                inbound_acks[_ack_code(ack)] += 1
            _stop(source)
            exported = _run_json_command("export", source_db)
            # L'émetteur MLLP est synchrone ; cette courte stabilisation ne couvre
            # que la fermeture des dernières connexions TCP côté GHT-2.
            time.sleep(0.5)
            _stop(target)
            source_data = _run_json_command("snapshot", source_db)
            target_data = _run_json_command("snapshot", target_db)
            result = {
                "cpage_messages": len(_cpage_files()), "cpage_acks": dict(sorted(inbound_acks.items())),
                "generated_messages": exported,
                "ght1": source_data, "ght2": target_data,
            }
            result["identical"] = result["ght1"]["hashes"] == result["ght2"]["hashes"]
            artifact_dir = os.getenv("ROUNDTRIP_ARTIFACT_DIR")
            if artifact_dir:
                destination = Path(artifact_dir)
                destination.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source_db, destination / "ght1.db")
                shutil.copy2(target_db, destination / "ght2.db")
                (destination / "result.json").write_text(
                    json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8"
                )
            print(json.dumps(result, ensure_ascii=False, sort_keys=True))
            return 0 if result["identical"] else 2
        finally:
            _stop(source)
            _stop(target)


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command")
    node = sub.add_parser("node")
    node.add_argument("--role", choices=("source", "target"), required=True)
    node.add_argument("--port", type=int, required=True)
    sub.add_parser("export")
    sub.add_parser("snapshot")
    sub.add_parser("run")
    args = parser.parse_args()
    if args.command in (None, "run"):
        return _run_parent()
    if args.command == "node":
        asyncio.run(_run_node(args.role, args.port))
        return 0
    if args.command == "export":
        print(json.dumps(_export_source(), sort_keys=True))
        return 0
    if args.command == "snapshot":
        print(json.dumps(_snapshot(), default=str, sort_keys=True))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
