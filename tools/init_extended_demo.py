"""Initialisation étendue du GHT de démonstration.

Ce script orchestre la création d'une structure multi-entités juridiques,
les endpoints MLLP/FHIR et une population réaliste de patients.

Utilisation (depuis la racine du projet, venv activé):
    python -m tools.init_extended_demo
"""
from __future__ import annotations

from sqlmodel import Session, select
from app.db import engine, init_db
from app.models_structure_fhir import GHTContext
from app.services.structure_seed import (
    ensure_extended_demo_ght,
    ensure_endpoints_for_context,
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

        print("[PATIENTS] Seeding population (target 120)...")
        stats_pat = seed_demo_population(session, context, target_patients=120)
        print("  -> done", stats_pat)

        print("Initialisation étendue terminée.")


if __name__ == "__main__":
    main()
