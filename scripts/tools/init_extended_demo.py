"""Initialisation étendue du GHT de démonstration.

Ce script orchestre la création d'une structure multi-entités juridiques,
les endpoints MLLP/FHIR et une population réaliste de patients.

Utilisation (depuis la racine du projet, venv activé):
    python -m tools.init_extended_demo
"""
from __future__ import annotations


import sys
import os
from sqlmodel import Session, select
import pathlib
# Always add project root (where 'app' lives) to sys.path
SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent  # Go up to MedData_Bridge
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from app.db import engine, init_db
from app.models_structure import GHTContext
from app.services.structure_seed import (
    ensure_extended_demo_ght,
    ensure_endpoints_for_context,
    ensure_namespaces_for_context,
    seed_demo_population,
    EXTENDED_GHT_DATA,
)


def get_or_create_default_context(session: Session) -> GHTContext:
    ctx = session.exec(select(GHTContext)).first()
    if ctx is None:
        ctx = GHTContext(name="DEMO GHT", code="GHT-DEMO")
        session.add(ctx)
        session.commit()
        session.refresh(ctx)
    return ctx


def main():
    with Session(engine) as session:
        # Ensure tables exist (idempotent)
        init_db()
        context = get_or_create_default_context(session)
        print("[STRUCTURE] Seeding extended GHT structures...")
        stats_struct = ensure_extended_demo_ght(session, context)
        print("  -> done", stats_struct)

        finess_list = [ej["entite_juridique"]["finess_ej"] for ej in EXTENDED_GHT_DATA.get("juridical_entities", [])]
        print("[ENDPOINTS] Ensuring endpoints for each EJ...")
        stats_ep = ensure_endpoints_for_context(session, context, finess_list)
        print("  -> done", stats_ep)

        # Ajout endpoint de lecture MFN pour le GHT de démo
        from app.models_shared import SystemEndpoint, EndpointKind, EndpointRole
        mfn_inbox_path = "/home/nico/Travail/Fhir_MedBridgeData/Interfaces/Entrant/MFN/In/"
        endpoint_mfn = SystemEndpoint(
            name="MFN File Reader Demo GHT",
            kind=EndpointKind.FILE,
            role=EndpointRole.RECEIVER,
            is_enabled=True,
            ght_context_id=context.id,
            inbox_path=mfn_inbox_path,
            file_extensions=".hl7,.txt",
            emit_hl7_pam=False,
            emit_hl7_mfn=True,
            emit_fhir_structure=False,
            emit_fhir_identity=False,
        )
        session.add(endpoint_mfn)
        session.commit()
        print(f"[ENDPOINT] MFN file reader created for demo GHT: {mfn_inbox_path}")

        print("[NAMESPACES] Ensuring identifier namespaces for each EJ...")
        stats_ns = ensure_namespaces_for_context(session, context, finess_list)
        print("  -> done", stats_ns)

        print("[PATIENTS] Skipping patient seeding for faster test setup...")
        stats_pat = {"created": {"patient": 0}, "updated": {"patient": 0}}
        print("  -> skipped", stats_pat)

        print("Initialisation étendue terminée.")


if __name__ == "__main__":
    main()
