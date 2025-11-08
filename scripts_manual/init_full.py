#!/usr/bin/env python3
"""Initialisation complète de l'environnement local.

Étapes:
1. (Optionnel) --force-reset : supprime le fichier poc.db s'il existe
2. Création des tables via SQLModel (idempotent)
3. Application des migrations legacy (006, 007) si non présentes
4. (Optionnel) --with-vocab : initialise les vocabulaires (tools/init_vocabularies.py)
5. Seed de données: minimal par défaut (Patient+Dossier+Venue+Mouvement) ou riche avec --rich-seed

Flags:
    --force-reset   : recrée totalement la base
    --with-vocab    : lance l'initialisation des vocabulaires
    --rich-seed     : insère plusieurs patients/dossiers/venues/mouvements

Usage:
        python scripts_manual/init_full.py                         # init simple
        python scripts_manual/init_full.py --with-vocab            # init + vocabulaires
        python scripts_manual/init_full.py --rich-seed             # init + seed étendu
        python scripts_manual/init_full.py --force-reset --rich-seed --with-vocab

Le script est idempotent: le seed est ignoré s'il existe déjà des patients.
"""
from __future__ import annotations
import argparse
import os
import sqlite3
from datetime import datetime
from pathlib import Path

from sqlmodel import Session, select

from app.db import init_db, engine, get_next_sequence
from app.models import Patient, Dossier, Venue, Mouvement, DossierType, Sequence
from app.models_structure_fhir import GHTContext, EntiteJuridique, EntiteGeographique
from app.models_structure import Pole, Service, UniteFonctionnelle, LocationPhysicalType, LocationServiceType
from subprocess import CalledProcessError, run

DB_PATH = Path("poc.db")

# --- Migrations legacy (006, 007) ---
MIGRATION_CMDS = [
    ("006", "entite_juridique_id", "ALTER TABLE systemendpoint ADD COLUMN entite_juridique_id INTEGER REFERENCES entitejuridique(id);", "CREATE INDEX IF NOT EXISTS idx_systemendpoint_entite_juridique_id ON systemendpoint(entite_juridique_id);") ,
    ("007", "inbox_path", "ALTER TABLE systemendpoint ADD COLUMN inbox_path TEXT; ALTER TABLE systemendpoint ADD COLUMN outbox_path TEXT; ALTER TABLE systemendpoint ADD COLUMN archive_path TEXT; ALTER TABLE systemendpoint ADD COLUMN error_path TEXT; ALTER TABLE systemendpoint ADD COLUMN file_extensions TEXT;", None),
]


def apply_legacy_migrations():
    if not DB_PATH.exists():
        print("Base non créée encore (tables vont être créées). Migrations différées.")
        return
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(systemendpoint)")
        cols = [r[1] for r in cursor.fetchall()]
        for code, marker_col, sql_up, sql_extra in MIGRATION_CMDS:
            if marker_col not in cols:
                print(f"→ Migration {code} en cours…")
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
            else:
                print(f"✓ Migration {code} déjà appliquée")
        conn.commit()
    finally:
        conn.close()


def seed_minimal():
    with Session(engine) as session:
        patient_count = session.exec(select(Patient).limit(1)).first()
        if patient_count:
            print("Seed ignoré (données déjà présentes).")
            return
        # Séquences (optionnel) - juste pour montrer l'utilisation
        for seq_name in ["dossier", "venue", "mouvement"]:
            if not session.get(Sequence, seq_name):
                session.add(Sequence(name=seq_name, value=0))
        session.commit()

        # Patient
        patient = Patient(
            family="DURAND",
            given="Alice",
            birth_date="1985-04-12",
            gender="female",
            city="Paris",
            postal_code="75001",
            country="FR",
            identity_reliability_code="VALI",
            identity_reliability_date="2024-01-15",
            identity_reliability_source="CNI",
        )
        session.add(patient)
        session.commit()
        session.refresh(patient)

        # Dossier
        dossier = Dossier(
            dossier_seq=get_next_sequence(session, "dossier"),
            patient_id=patient.id,
            uf_responsabilite="UF-100",
            admit_time=datetime.utcnow(),
            dossier_type=DossierType.HOSPITALISE,
            reason="Admission initiale",
        )
        session.add(dossier)
        session.commit()
        session.refresh(dossier)

        # Venue
        venue = Venue(
            venue_seq=get_next_sequence(session, "venue"),
            dossier_id=dossier.id,
            uf_responsabilite="UF-100",
            start_time=datetime.utcnow(),
            code="CHIR-A",
            label="Chirurgie A",
            operational_status="active",
        )
        session.add(venue)
        session.commit()
        session.refresh(venue)

        # Mouvement
        mouvement = Mouvement(
            mouvement_seq=get_next_sequence(session, "mouvement"),
            venue_id=venue.id,
            when=datetime.utcnow(),
            location="CHIR-A/SALLE-1",
            trigger_event="A01",
            movement_type="Admission",
        )
        session.add(mouvement)
        session.commit()

        print("✓ Seed minimal inséré (Patient + Dossier + Venue + Mouvement).")


def seed_rich():
    """Seed plus riche multi-patients/multi-venues/mouvements.

    Génère:
      - 100 patients avec données variées (noms français, dates aléatoires)
      - Pour chaque patient: 1-2 dossiers avec UF aléatoires
      - Pour chaque dossier: 1-3 venues
      - Pour chaque venue: 2-5 mouvements (admission, transferts, sorties)
    """
    import random
    from datetime import timedelta
    
    with Session(engine) as session:
        existing = session.exec(select(Patient).limit(1)).first()
        if existing:
            print("Seed riche ignoré (données déjà présentes).")
            return

        # Séquences initiales
        for seq_name in ["patient", "dossier", "venue", "mouvement"]:
            if not session.get(Sequence, seq_name):
                session.add(Sequence(name=seq_name, value=0))
        session.commit()

        # Listes pour varier les données
        first_names = ["Jean", "Marie", "Pierre", "Sophie", "Luc", "Anne", "Paul", "Julie", "Marc", "Claire",
                       "Francois", "Isabelle", "Jacques", "Nathalie", "Michel", "Catherine", "Andre", "Sylvie",
                       "Philippe", "Monique", "Alain", "Francoise", "Bernard", "Nicole", "Georges", "Emilie",
                       "Thomas", "Camille", "Nicolas", "Laura", "David", "Sarah", "Julien", "Marine"]
        last_names = ["Dupont", "Martin", "Bernard", "Dubois", "Thomas", "Robert", "Richard", "Petit",
                      "Durand", "Leroy", "Moreau", "Simon", "Laurent", "Lefebvre", "Michel", "Garcia",
                      "David", "Bertrand", "Roux", "Vincent", "Fournier", "Morel", "Girard", "Andre",
                      "Mercier", "Blanc", "Guerin", "Boyer", "Garnier", "Chevalier", "Francois", "Legrand"]
        genders = ["M", "F"]
        uf_codes = ["001", "002", "003", "UF_MED", "UF_SOINS", "UF_HEB", "CHIR"]
        
        now = datetime.utcnow()
        
        print("🚀 Création du seed riche (100 patients)...")
        
        for i in range(1, 101):
            patient_seq = get_next_sequence(session, "patient")
            
            gender = random.choice(genders)
            first_name = random.choice(first_names)
            last_name = random.choice(last_names)
            # Date de naissance entre 18 et 80 ans
            birth_days_ago = random.randint(365*18, 365*80)
            birth_date = (now - timedelta(days=birth_days_ago)).strftime("%Y%m%d")
            
            patient = Patient(
                patient_seq=patient_seq,
                identifier=f"PAT{patient_seq:06d}",
                family=last_name,
                given=first_name,
                birth_date=birth_date,
                gender="female" if gender == "F" else "male",
                city="Paris",
                postal_code=f"750{random.randint(10,20):02d}",
                country="FR",
                identity_reliability_code="VALI",
                identity_reliability_date="2024-01-15",
                identity_reliability_source="CNI",
            )
            session.add(patient)
            session.flush()

            # 1-2 dossiers par patient
            num_dossiers = random.randint(1, 2)
            for d in range(num_dossiers):
                dossier_seq = get_next_sequence(session, "dossier")
                admit_days_ago = random.randint(0, 180)
                admit_time = now - timedelta(days=admit_days_ago)
                
                dossier = Dossier(
                    dossier_seq=dossier_seq,
                    patient_id=patient.id,
                    uf_responsabilite=random.choice(uf_codes),
                    uf_medicale=random.choice(uf_codes) if random.random() > 0.3 else None,
                    uf_hebergement=random.choice(uf_codes) if random.random() > 0.5 else None,
                    uf_soins=random.choice(uf_codes) if random.random() > 0.7 else None,
                    admit_time=admit_time,
                    discharge_time=admit_time + timedelta(days=random.randint(1, 14)) if random.random() > 0.3 else None,
                    dossier_type=DossierType.HOSPITALISE,
                    reason="Admission automatique seed riche",
                )
                session.add(dossier)
                session.flush()

                # 1-3 venues par dossier
                num_venues = random.randint(1, 3)
                for v in range(num_venues):
                    venue_seq = get_next_sequence(session, "venue")
                    venue_start = admit_time + timedelta(hours=v*24)
                    
                    venue = Venue(
                        venue_seq=venue_seq,
                        dossier_id=dossier.id,
                        uf_responsabilite=random.choice(uf_codes),
                        start_time=venue_start,
                        code=f"LOC-{patient_seq}-{v}",
                        label=f"Location {patient_seq}-{v}",
                        operational_status="active",
                    )
                    session.add(venue)
                    session.flush()

                    # 2-5 mouvements par venue
                    num_mouvements = random.randint(2, 5)
                    movement_types = ["admission", "transfer", "discharge", "update"]
                    for m in range(num_mouvements):
                        mouv_seq = get_next_sequence(session, "mouvement")
                        mouv_time = venue_start + timedelta(hours=m*12)
                        
                        mouvement = Mouvement(
                            mouvement_seq=mouv_seq,
                            venue_id=venue.id,
                            type="ADT^A01" if m == 0 else f"ADT^A0{random.randint(1,8)}",
                            when=mouv_time,
                            movement_type=movement_types[min(m, len(movement_types)-1)],
                            trigger_event=f"A0{random.randint(1,8)}",
                            location=f"{random.choice(uf_codes)}^B{random.randint(1,5)}^{random.randint(1,20):03d}"
                        )
                        session.add(mouvement)
            
            if i % 10 == 0:
                session.commit()
                print(f"   ✓ {i} patients créés...")

        session.commit()
        
        # Statistiques finales
        from sqlmodel import func
        total_patients = session.exec(select(func.count(Patient.id))).one()
        total_dossiers = session.exec(select(func.count(Dossier.id))).one()
        total_venues = session.exec(select(func.count(Venue.id))).one()
        total_mouvements = session.exec(select(func.count(Mouvement.id))).one()
        
        print(f"\n✅ Seed riche inséré avec succès!")
        print(f"   • Patients: {total_patients}")
        print(f"   • Dossiers: {total_dossiers}")
        print(f"   • Venues: {total_venues}")
        print(f"   • Mouvements: {total_mouvements}")


def seed_demo_scenarios():
    """Scénarios complexes de mouvements pour un GHT DEMO.

    Crée un GHT 'GHT DEMO' si absent puis insère 3 patients avec des séquences
    de mouvements illustrant des cas métier: transferts multiples, annulation,
    transferts multiples, annulation (A11) et sortie (A03) sans utiliser A08 (non supporté PAM FR).
    """
    from sqlmodel import select
    with Session(engine) as session:
        # GHT DEMO
        ght = session.exec(select(GHTContext).where(GHTContext.code == "GHT-DEMO")).first()
        if not ght:
            ght = GHTContext(name="GHT DEMO", code="GHT-DEMO", description="Contexte de démonstration")
            session.add(ght)
            session.commit()
            session.refresh(ght)
            print("✓ GHT DEMO créé")
        else:
            print("✓ GHT DEMO déjà présent")

        # --- Structure démo enrichie (Entités Juridiques + géographie + services + UF) ---
        existing_ej = session.exec(select(EntiteJuridique).where(EntiteJuridique.ght_context_id == ght.id)).all()
        if not existing_ej:
            print("→ Création des Entités Juridiques de démonstration…")
            ej_defs = [
                {"name": "Centre Hospitalier DEMO Nord", "short_name": "CH DEMO N", "finess_ej": "010000000"},
                {"name": "Centre Hospitalier DEMO Sud", "short_name": "CH DEMO S", "finess_ej": "020000000"},
            ]
            ej_objs = []
            for ej_def in ej_defs:
                ej = EntiteJuridique(
                    name=ej_def["name"],
                    short_name=ej_def["short_name"],
                    finess_ej=ej_def["finess_ej"],
                    description="EJ de démonstration pour scénarios mouvements",
                    ght_context_id=ght.id,
                )
                session.add(ej)
                session.flush()
                ej_objs.append(ej)
            session.commit()
            print(f"   ✓ {len(ej_objs)} EJ créées")

            # Pour chaque EJ on crée 1 entité géographique, 1 pôle, 1 service, 2 UF (activité hospitalisation + urgences)
            for idx, ej in enumerate(ej_objs, start=1):
                geo = EntiteGeographique(
                    identifier=f"EGE-{idx}",
                    name=f"Site {idx} DEMO",
                    finess=f"1000000{idx}",
                    description="Entité géographique de démonstration",
                    entite_juridique_id=ej.id,
                )
                session.add(geo)
                session.flush()

                pole = Pole(
                    identifier=f"POLE-{idx}",
                    name=f"Pôle Général {idx}",
                    physical_type=LocationPhysicalType.SI,
                    entite_geo_id=geo.id,
                )
                session.add(pole)
                session.flush()

                service = Service(
                    identifier=f"SERV-{idx}",
                    name=f"Service MCO {idx}",
                    physical_type=LocationPhysicalType.SI,
                    service_type=LocationServiceType.MCO,
                    pole_id=pole.id,
                )
                session.add(service)
                session.flush()

                for u in range(1, 3):
                    uf = UniteFonctionnelle(
                        identifier=f"UF-{idx}-{u}",
                        name=f"UF DEMO {idx}-{u}",
                        physical_type=LocationPhysicalType.SI,
                        service_id=service.id,
                    )
                    session.add(uf)
                session.commit()
            print("   ✓ Structure hiérarchique (geo+pôle+service+UF) créée pour chaque EJ")
        else:
            print(f"✓ {len(existing_ej)} EJ déjà présentes (structure non régénérée)")

        # Ne pas dupliquer les patients si déjà scénarisés
        existing_demo = session.exec(select(Patient).where(Patient.family.like("SCENARIO-%")).limit(1)).first()
        if existing_demo:
            print("Scénarios DEMO ignorés (déjà présents).")
            return

        # Assurer les séquences
        for seq_name in ["dossier", "venue", "mouvement"]:
            if not session.get(Sequence, seq_name):
                session.add(Sequence(name=seq_name, value=0))
        session.commit()

        from app.db import get_next_sequence
        now = datetime.utcnow()

        # Récupérer la hiérarchie des UF créées pour chaque EJ afin d'utiliser
        # des identifiants réels dans les dossiers/venues/mouvements (meilleure cohérence).
    # Import déjà effectué en tête de fichier (Pole, Service, UniteFonctionnelle)
        ej_uf_map: dict[int, list[UniteFonctionnelle]] = {}
        for ej in session.exec(select(EntiteJuridique)).all():
            # Parcours indirect: EJ -> EntiteGeographique -> Pole -> Service -> UF
            ufs = session.exec(
                select(UniteFonctionnelle)
                .join(Service)
                .join(Pole)
                .join(EntiteGeographique)
                .where(EntiteGeographique.entite_juridique_id == ej.id)
            ).all()
            if ufs:
                ej_uf_map[ej.id] = ufs

        scenario_defs = [
            {
                "patient_family": "SCENARIO-TRANSFERTS",
                "flows": [
                    ("Admission", "A01"),
                    ("Transfert", "A02"),
                    ("Transfert", "A02"),
                    ("Sortie", "A03"),
                ],
            },
            {
                "patient_family": "SCENARIO-ANNULATION",
                "flows": [
                    ("Admission", "A01"),
                    ("Annulation admission", "A11"),
                    ("Nouvelle admission", "A01"),
                    ("Transfert", "A02"),
                    ("Sortie", "A03"),
                ],
            },
            {
                "patient_family": "SCENARIO-TRANSFERT-MULTI",
                "flows": [
                    ("Admission", "A01"),
                    ("Transfert", "A02"),
                    ("Transfert secondaire", "A02"),
                    ("Transfert tertiaire", "A02"),
                    ("Sortie", "A03"),
                ],
            },
        ]

        # Utiliser round-robin sur les EJ disponibles pour distribuer les scénarios
        ej_ids = list(ej_uf_map.keys())
        if not ej_ids:
            print("⚠ Aucune UF trouvée pour lier les scénarios (structure absente).")
        for scen_idx, scen in enumerate(scenario_defs, start=1):
            ej_id = ej_ids[(scen_idx - 1) % len(ej_ids)] if ej_ids else None
            ufs_for_ej = ej_uf_map.get(ej_id, [])
            primary_uf = ufs_for_ej[0] if ufs_for_ej else None
            secondary_uf = ufs_for_ej[1] if len(ufs_for_ej) > 1 else primary_uf

            patient = Patient(
                family=scen["patient_family"],
                given="Demo",
                birth_date="1980-01-01",
                gender="other",
                city="DemoVille",
                postal_code="00000",
                country="FR",
                identity_reliability_code="VALI",
                identity_reliability_date="2024-01-15",
                identity_reliability_source="CNI",
            )
            session.add(patient)
            session.commit()
            session.refresh(patient)

            dossier_seq = get_next_sequence(session, "dossier")
            dossier = Dossier(
                dossier_seq=dossier_seq,
                patient_id=patient.id,
                uf_responsabilite=primary_uf.identifier if primary_uf else f"UF-DEMO-{scen_idx}",
                admit_time=now,
                dossier_type=DossierType.HOSPITALISE,
                reason="Scenario démo",
            )
            session.add(dossier)
            session.commit()
            session.refresh(dossier)

            # Créer 2 venues pour permettre transferts, en utilisant UF primaire / secondaire
            venues = []
            for v_num, uf_ref in [(1, primary_uf), (2, secondary_uf)]:
                venue_seq = get_next_sequence(session, "venue")
                venue = Venue(
                    venue_seq=venue_seq,
                    dossier_id=dossier.id,
                    uf_responsabilite=(uf_ref.identifier if uf_ref else dossier.uf_responsabilite),
                    start_time=now,
                    code=f"DEMO-{scen_idx}-{v_num}",
                    label=f"Unité Démo {scen_idx}-{v_num}",
                    operational_status="active",
                )
                session.add(venue)
                session.commit()
                session.refresh(venue)
                venues.append(venue)

            current_venue_index = 0
            current_uf = primary_uf
            for flow_idx, (movement_type, trigger) in enumerate(scen["flows"], start=1):
                if trigger == "A02":  # transfert -> changer de venue/UF
                    current_venue_index = 1 - current_venue_index
                    current_uf = secondary_uf if current_venue_index == 1 else primary_uf
                venue = venues[current_venue_index]
                mouvement_seq = get_next_sequence(session, "mouvement")
                location_components = [
                    (current_uf.identifier if current_uf else venue.uf_responsabilite),
                    f"BOX-{flow_idx}",
                    f"CH-{flow_idx:02d}",
                ]
                mouvement = Mouvement(
                    mouvement_seq=mouvement_seq,
                    venue_id=venue.id,
                    when=now,
                    location="^".join(location_components),
                    trigger_event=trigger,
                    movement_type=movement_type,
                    from_location=venues[1 - current_venue_index].uf_responsabilite if trigger == "A02" else None,
                    to_location=venue.uf_responsabilite if trigger == "A02" else None,
                )
                session.add(mouvement)
                session.commit()

        print("✓ Scénarios complexes DEMO insérés (3 patients scénarisés, liés aux UF réelles).")


def main():
    parser = argparse.ArgumentParser(description="Initialisation complète locale")
    parser.add_argument("--force-reset", action="store_true", help="Supprime poc.db avant recréation")
    parser.add_argument("--with-vocab", action="store_true", help="Initialise les vocabulaires")
    parser.add_argument("--rich-seed", action="store_true", help="Insère un jeu de données plus riche (multi) au lieu du seed minimal")
    parser.add_argument("--demo-scenarios", action="store_true", help="Insère scénarios complexes de mouvements liés à un GHT DEMO")
    args = parser.parse_args()

    if args.force_reset and DB_PATH.exists():
        print("→ Suppression ancienne base poc.db")
        DB_PATH.unlink()

    print("→ Création des tables (idempotent)…")
    init_db()

    print("→ Application migrations legacy…")
    apply_legacy_migrations()

    if args.rich_seed:
        print("→ Seed riche…")
        seed_rich()
    else:
        print("→ Seed minimal…")
        seed_minimal()

    if args.demo_scenarios:
        print("→ Scénarios complexes GHT DEMO…")
        seed_demo_scenarios()

    if args.with_vocab:
        print("→ Initialisation des vocabulaires…")
        try:
            import sys
            # Utiliser l'interpréteur courant pour éviter FileNotFoundError (python peut ne pas être dans PATH)
            result = run([sys.executable, "tools/init_vocabularies.py"], check=True)
            print("✓ Vocabulaires initialisés")
        except CalledProcessError as e:
            print(f"✗ Échec init vocabulaires: retour code {e.returncode}")
        except FileNotFoundError as e:
            print(f"✗ Interpréteur introuvable pour init vocab: {e}")

    print("\n✅ Initialisation complète terminée.")

if __name__ == "__main__":
    main()
