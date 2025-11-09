#!/usr/bin/env python3
"""Initialisation complète de l'environnement local.

Étapes:
1. --force-reset : supprime le fichier medbridge.db si présent
2. Création des tables (idempotent)
3. Application migrations legacy basiques (006/007)
4. Structure étendue optionnelle (--extended-structure) : multi-EJ + endpoints + namespaces
5. Seed minimal ou riche
6. Scénarios démo optionnels
7. Vocabulaires (auto si --extended-structure, ou explicit avec --with-vocab)

Le script est idempotent: on ne réinsère pas le seed minimal/rich si des patients existent déjà.
"""
from __future__ import annotations
import argparse
import sqlite3
from datetime import datetime
from pathlib import Path
from random import choice

from sqlmodel import Session, select
from subprocess import CalledProcessError, run

from app.db import init_db, engine, get_next_sequence
from app.models import Patient, Dossier, Venue, Mouvement, DossierType, Sequence
from app.models_structure_fhir import GHTContext, EntiteJuridique, EntiteGeographique, IdentifierNamespace
from app.models_structure import (
    Pole,
    Service,
    UniteFonctionnelle,
    UniteHebergement,
    Chambre,
    Lit,
    LocationPhysicalType,
    LocationServiceType,
)

DB_PATH = Path("medbridge.db")

MIGRATION_CMDS = [
    (
        "006",
        "entite_juridique_id",
        "ALTER TABLE systemendpoint ADD COLUMN entite_juridique_id INTEGER REFERENCES entitejuridique(id);",
        "CREATE INDEX IF NOT EXISTS idx_systemendpoint_entite_juridique_id ON systemendpoint(entite_juridique_id);",
    ),
    (
        "007",
        "inbox_path",
        "ALTER TABLE systemendpoint ADD COLUMN inbox_path TEXT; ALTER TABLE systemendpoint ADD COLUMN outbox_path TEXT; ALTER TABLE systemendpoint ADD COLUMN archive_path TEXT; ALTER TABLE systemendpoint ADD COLUMN error_path TEXT; ALTER TABLE systemendpoint ADD COLUMN file_extensions TEXT;",
        None,
    ),
]


def apply_legacy_migrations() -> None:
    if not DB_PATH.exists():
        return
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(systemendpoint)")
    cols = [r[1] for r in cursor.fetchall()]
    for code, marker_col, sql_up, sql_extra in MIGRATION_CMDS:
        if marker_col not in cols:
            print(f"→ Migration {code}…")
            for stmt in sql_up.split(";"):
                s = stmt.strip()
                if s:
                    cursor.execute(s)
            if sql_extra:
                for stmt in sql_extra.split(";"):
                    s = stmt.strip()
                    if s:
                        cursor.execute(s)
            print(f"✓ Migration {code} appliquée")
    conn.commit()
    conn.close()


def ensure_extended_structure(create_demo_ght: bool = True) -> None:
    """Appelle tools/init_extended_demo.py pour structure multi-EJ complète + endpoints + namespaces."""
    import sys
    try:
        run([sys.executable, "tools/init_extended_demo.py"], check=True)
        print("✓ Structure étendue (multi-EJ, endpoints, namespaces) initialisée")
        return True
    except CalledProcessError as e:
        print(f"✗ Échec init structure étendue: {e}")
    except FileNotFoundError as e:
        print(f"✗ Script init_extended_demo.py introuvable: {e}")
    return False


def _legacy_ensure_extended_structure(create_demo_ght: bool = True) -> None:
    """DEPRECATED: Ancienne logique basique (conservée pour compatibilité)."""
    with Session(engine) as session:
        ght = session.exec(select(GHTContext).where(GHTContext.code == "GHT-EXT")).first()
        if not ght:
            ght = GHTContext(name="GHT Étendu Démo", code="GHT-EXT", description="Structure étendue pour seed")
            session.add(ght)
            session.commit()
            session.refresh(ght)
            print("✓ GHT étendu créé")

        ejs = session.exec(select(EntiteJuridique).where(EntiteJuridique.ght_context_id == ght.id)).all()
        if not ejs:
            for idx in [1, 2]:
                ej = EntiteJuridique(
                    name=f"Centre Hospitalier Étendu {idx}",
                    short_name=f"CH EXT {idx}",
                    finess_ej=f"{100000000 + idx}",
                    description="EJ étendue",
                    ght_context_id=ght.id,
                )
                session.add(ej)
            session.commit()
            ejs = session.exec(select(EntiteJuridique).where(EntiteJuridique.ght_context_id == ght.id)).all()
            print("✓ EJ étendues créées (2)")
        else:
            print(f"✓ {len(ejs)} EJ déjà présentes")

        # NOTE: Ce code legacy a été déplacé dans _legacy_ensure_extended_structure
        # La nouvelle logique appelle directement tools/init_extended_demo.py
        for ej in ejs:
            geo = session.exec(select(EntiteGeographique).where(EntiteGeographique.entite_juridique_id == ej.id)).first()
            if geo:
                continue
            geo = EntiteGeographique(
                identifier=f"EGE-EXT-{ej.id}",
                name=f"Site Étendu EJ {ej.id}",
                finess=f"2000000{ej.id}",
                description="Site étendu",
                entite_juridique_id=ej.id,
            )
            session.add(geo)
            session.flush()
            pole = Pole(
                identifier=f"POLE-EXT-{ej.id}",
                name=f"Pôle Central EJ {ej.id}",
                physical_type=LocationPhysicalType.SI,
                entite_geo_id=geo.id,
            )
            session.add(pole)
            session.flush()
            for svc_idx, svc_label in [(1, "MCO"), (2, "URGENCES")]:
                service = Service(
                    identifier=f"SERV-EXT-{ej.id}-{svc_idx}",
                    name=f"Service {svc_label} EJ {ej.id}",
                    physical_type=LocationPhysicalType.SI,
                    service_type=LocationServiceType.MCO,
                    pole_id=pole.id,
                )
                session.add(service)
                session.flush()
                for uf_idx in range(1, 4):
                    uf = UniteFonctionnelle(
                        identifier=f"UF-EXT-{ej.id}-{svc_idx}-{uf_idx}",
                        name=f"UF {svc_label} {uf_idx} EJ {ej.id}",
                        physical_type=LocationPhysicalType.SI,
                        service_id=service.id,
                    )
                    session.add(uf)
                    session.flush()
                    # Hébergement simple
                    uh = UniteHebergement(
                        identifier=f"UH-EXT-{ej.id}-{svc_idx}-{uf_idx}",
                        name=f"UH {svc_label} {uf_idx} EJ {ej.id}",
                        physical_type=LocationPhysicalType.SI,
                        unite_fonctionnelle_id=uf.id,
                    )
                    session.add(uh)
                    session.flush()
                    for ch_idx in range(1, 3):
                        chambre = Chambre(
                            identifier=f"CH-EXT-{ej.id}-{svc_idx}-{uf_idx}-{ch_idx}",
                            name=f"Chambre {uf_idx}-{ch_idx} EJ {ej.id}",
                            physical_type=LocationPhysicalType.RO,
                            unite_hebergement_id=uh.id,
                        )
                        session.add(chambre)
                        session.flush()
                        for lit_idx in range(1, 3):
                            lit = Lit(
                                identifier=f"LIT-EXT-{ej.id}-{svc_idx}-{uf_idx}-{ch_idx}-{lit_idx}",
                                name=f"Lit {uf_idx}-{ch_idx}-{lit_idx} EJ {ej.id}",
                                physical_type=LocationPhysicalType.BD,
                                chambre_id=chambre.id,
                            )
                            session.add(lit)
            session.commit()
            print(f"   ✓ Hiérarchie complète créée pour EJ {ej.finess_ej}")

        existing_ns = session.exec(select(IdentifierNamespace)).all()
        ns_map = {(n.type, n.entite_juridique_id) for n in existing_ns}
        to_add = []
        for ej in ejs:
            for typ in ["IPP", "NDA", "VN", "MVT"]:
                if (typ, ej.id) not in ns_map:
                    to_add.append(
                        IdentifierNamespace(
                            name=f"Namespace {typ} EJ {ej.id}",
                            system=f"urn:oid:1.2.250.1.{ej.id}.{typ.lower()}",
                            oid=f"1.2.250.1.{ej.id}.{typ.lower()}",
                            type=typ,
                            ght_context_id=ght.id,
                            entite_juridique_id=ej.id,
                        )
                    )
        if not any(n.type == "STRUCT" for n in existing_ns):
            to_add.append(
                IdentifierNamespace(
                    name="Namespace Structure GHT",
                    system="urn:oid:1.2.250.1.STRUCT",
                    oid="1.2.250.1.STRUCT",
                    type="STRUCT",
                    ght_context_id=ght.id,
                )
            )
        if to_add:
            session.add_all(to_add)
            session.commit()
            print(f"✓ Namespaces ajoutés ({len(to_add)})")
        else:
            print("✓ Namespaces déjà présents")


def _ensure_sequences(session: Session) -> None:
    for name in ["patient", "dossier", "venue", "mouvement"]:
        if not session.get(Sequence, name):
            session.add(Sequence(name=name, value=0))
    session.commit()


def seed_minimal() -> None:
    with Session(engine) as session:
        existing = session.exec(select(Patient).limit(1)).first()
        if existing:
            print("Seed minimal ignoré (patients déjà présents).")
            return
        _ensure_sequences(session)
        patient = Patient(
            family="DOE",
            given="John",
            birth_date="1985-05-05",
            gender="male",
            city="Paris",
            postal_code="75000",
            country="FR",
            identity_reliability_code="VALI",
            identity_reliability_date="2024-01-01",
            identity_reliability_source="CNI",
        )
        session.add(patient)
        session.commit()
        session.refresh(patient)

        dossier_seq = get_next_sequence(session, "dossier")
        dossier = Dossier(
            dossier_seq=dossier_seq,
            patient_id=patient.id,
            uf_responsabilite="UF-EXT-1-1-1",  # sera valide si structure étendue; sinon valeur libre
            admit_time=datetime.utcnow(),
            dossier_type=DossierType.HOSPITALISE,
            reason="Admission initiale",
        )
        session.add(dossier)
        session.commit()
        session.refresh(dossier)

        venue_seq = get_next_sequence(session, "venue")
        venue = Venue(
            venue_seq=venue_seq,
            dossier_id=dossier.id,
            uf_responsabilite=dossier.uf_responsabilite,
            start_time=datetime.utcnow(),
            code="VENUE-1",
            label="Unité Initiale",
            operational_status="active",
        )
        session.add(venue)
        session.commit()
        session.refresh(venue)

        mouvement_seq = get_next_sequence(session, "mouvement")
        mouvement = Mouvement(
            mouvement_seq=mouvement_seq,
            venue_id=venue.id,
            when=datetime.utcnow(),
            location=f"{venue.uf_responsabilite}^BOX-1^CH-01",
            trigger_event="A01",
            movement_type="Admission",
        )
        session.add(mouvement)
        session.commit()
        print("✓ Seed minimal inséré")


def seed_rich(nb_patients: int = 40) -> None:
    with Session(engine) as session:
        existing = session.exec(select(Patient).limit(1)).first()
        if existing:
            print("Seed riche ignoré (patients déjà présents).")
            return
        _ensure_sequences(session)

        # Collect UF codes si structure présente
        uf_codes = [uf.identifier for uf in session.exec(select(UniteFonctionnelle)).all()]
        if not uf_codes:
            uf_codes = ["UF-RICH-1", "UF-RICH-2"]

        for i in range(1, nb_patients + 1):
            patient = Patient(
                family=f"RICH-{i:03d}",
                given=choice(["Alice", "Bob", "Chloé", "David", "Eva"]),
                birth_date="1970-01-01",
                gender="other",
                city="VilleX",
                postal_code="00000",
                country="FR",
                identity_reliability_code="VALI",
                identity_reliability_date="2024-02-01",
                identity_reliability_source="CNI",
            )
            session.add(patient)
            session.commit()
            session.refresh(patient)

            dossier_seq = get_next_sequence(session, "dossier")
            uf_resp = choice(uf_codes)
            dossier = Dossier(
                dossier_seq=dossier_seq,
                patient_id=patient.id,
                uf_responsabilite=uf_resp,
                admit_time=datetime.utcnow(),
                dossier_type=DossierType.HOSPITALISE,
                reason="Admission auto",
            )
            session.add(dossier)
            session.commit()
            session.refresh(dossier)

            # 2 venues
            venues = []
            for v in range(1, 3):
                venue_seq = get_next_sequence(session, "venue")
                venue = Venue(
                    venue_seq=venue_seq,
                    dossier_id=dossier.id,
                    uf_responsabilite=uf_resp,
                    start_time=datetime.utcnow(),
                    code=f"VENUE-{i}-{v}",
                    label=f"Unité {v}",
                    operational_status="active",
                )
                session.add(venue)
                session.commit()
                session.refresh(venue)
                venues.append(venue)

            # mouvements (admission + transfert + sortie)
            triggers = [("Admission", "A01"), ("Transfert", "A02"), ("Sortie", "A03")]
            current_index = 0
            for step_idx, (m_type, trig) in enumerate(triggers, start=1):
                if trig == "A02":
                    current_index = 1 - current_index
                venue = venues[current_index]
                mouvement_seq = get_next_sequence(session, "mouvement")
                mouvement = Mouvement(
                    mouvement_seq=mouvement_seq,
                    venue_id=venue.id,
                    when=datetime.utcnow(),
                    location=f"{venue.uf_responsabilite}^BOX-{step_idx}^CH-{step_idx:02d}",
                    trigger_event=trig,
                    movement_type=m_type,
                    from_location=venues[1 - current_index].uf_responsabilite if trig == "A02" else None,
                    to_location=venue.uf_responsabilite if trig == "A02" else None,
                )
                session.add(mouvement)
                session.commit()
            if i % 10 == 0:
                print(f"   … {i} patients créés")

        print(f"✓ Seed riche inséré ({nb_patients} patients)")


def seed_demo_scenarios() -> None:
    """Insère 3 patients avec scénarios de transferts / annulations."""
    with Session(engine) as session:
        existing_demo = session.exec(select(Patient).where(Patient.family.like("SCENARIO-%")).limit(1)).first()
        if existing_demo:
            print("Scénarios démo déjà présents.")
            return
        _ensure_sequences(session)
        now = datetime.utcnow()
        scenario_defs = [
            ("SCENARIO-TRANSFERTS", ["A01", "A02", "A02", "A03"]),
            ("SCENARIO-ANNULATION", ["A01", "A11", "A01", "A02", "A03"]),
            ("SCENARIO-TRANSFERT-MULTI", ["A01", "A02", "A02", "A02", "A03"]),
        ]
        uf_codes = [uf.identifier for uf in session.exec(select(UniteFonctionnelle)).all()] or ["UF-DEMO-1", "UF-DEMO-2"]
        for scen_idx, (family_name, triggers) in enumerate(scenario_defs, start=1):
            patient = Patient(
                family=family_name,
                given="Demo",
                birth_date="1980-01-01",
                gender="other",
                city="DemoVille",
                postal_code="00000",
                country="FR",
                identity_reliability_code="VALI",
                identity_reliability_date="2024-03-01",
                identity_reliability_source="CNI",
            )
            session.add(patient)
            session.commit()
            session.refresh(patient)
            dossier_seq = get_next_sequence(session, "dossier")
            uf_resp = choice(uf_codes)
            dossier = Dossier(
                dossier_seq=dossier_seq,
                patient_id=patient.id,
                uf_responsabilite=uf_resp,
                admit_time=now,
                dossier_type=DossierType.HOSPITALISE,
                reason="Scenario démo",
            )
            session.add(dossier)
            session.commit()
            session.refresh(dossier)
            venues = []
            for v in range(1, 3):
                venue_seq = get_next_sequence(session, "venue")
                venue = Venue(
                    venue_seq=venue_seq,
                    dossier_id=dossier.id,
                    uf_responsabilite=choice(uf_codes),
                    start_time=now,
                    code=f"SC-{scen_idx}-{v}",
                    label=f"Unité Scénario {v}",
                    operational_status="active",
                )
                session.add(venue)
                session.commit()
                session.refresh(venue)
                venues.append(venue)
            current_index = 0
            for step_idx, trig in enumerate(triggers, start=1):
                if trig == "A02":
                    current_index = 1 - current_index
                venue = venues[current_index]
                mouvement_seq = get_next_sequence(session, "mouvement")
                mouvement = Mouvement(
                    mouvement_seq=mouvement_seq,
                    venue_id=venue.id,
                    when=now,
                    location=f"{venue.uf_responsabilite}^BOX-{step_idx}^CH-{step_idx:02d}",
                    trigger_event=trig,
                    movement_type="Transfert" if trig == "A02" else ("Annulation" if trig == "A11" else "Admission/Sortie"),
                    from_location=venues[1 - current_index].uf_responsabilite if trig == "A02" else None,
                    to_location=venue.uf_responsabilite if trig == "A02" else None,
                )
                session.add(mouvement)
                session.commit()
        print("✓ Scénarios démo insérés")


def _load_vocabularies(tag: str = "") -> bool:
    """Charge les vocabulaires; retourne True si succès."""
    try:
        import sys
        run([sys.executable, "tools/init_vocabularies.py"], check=True)
        print(f"✓ Vocabulaires initialisés{f' ({tag})' if tag else ''}")
        return True
    except CalledProcessError as e:
        print(f"✗ Échec init vocabulaires{f' ({tag})' if tag else ''}: {e}")
    except FileNotFoundError as e:
        print(f"✗ Script vocab introuvable{f' ({tag})' if tag else ''}: {e}")
    return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Initialisation complète locale")
    parser.add_argument("--force-reset", action="store_true", help="Supprime medbridge.db avant recréation")
    parser.add_argument("--with-vocab", action="store_true", help="Initialise les vocabulaires")
    parser.add_argument("--rich-seed", action="store_true", help="Seed riche (multi patients)")
    parser.add_argument("--demo-scenarios", action="store_true", help="Insère scénarios complexes")
    parser.add_argument("--extended-structure", action="store_true", help="Crée structure étendue avant seeds")
    args = parser.parse_args()

    if args.force_reset and DB_PATH.exists():
        print("→ Suppression ancienne base medbridge.db")
        DB_PATH.unlink()

    print("→ Création tables…")
    init_db()
    print("→ Migrations legacy…")
    apply_legacy_migrations()

    auto_vocab_requested = False
    if args.extended_structure:
        print("→ Structure étendue…")
        ensure_extended_structure()
        if not args.with_vocab:
            print("→ Vocabulaires (auto car structure étendue)…")
            auto_vocab_requested = _load_vocabularies("auto")

    if args.rich_seed:
        seed_rich()
    else:
        seed_minimal()

    if args.demo_scenarios:
        seed_demo_scenarios()

    if args.with_vocab and not auto_vocab_requested:
        print("→ Vocabulaires…")
        _load_vocabularies()

    print("\n✅ Initialisation terminée")


if __name__ == "__main__":
    main()
