#!/usr/bin/env python3
"""Seed complet GHT DEMO: structure + identités + mouvements.

Crée un GHT DEMO avec:
  - Entité juridique + namespaces (IPP, NDA, VENUE)
  - Structure hiérarchique complète: EG → Poles → Services → UF → UH → CH → Lits
  - Patients avec IPP + identité (nom, prénom, date naissance, adresse)
  - Dossiers avec NDA
  - Venues avec numéro de venue
  - Mouvements IHE PAM réalistes (A01 admission, A02 transfert, A03 sortie, A11 annulation)

Usage:
    python tools/seed_demo_complete.py [--reset]
"""
import sys, argparse
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlmodel import Session, select
from app.db import engine, init_db, get_next_sequence
from app.models import Patient, Dossier, Venue, Mouvement, DossierType, Sequence
from app.models_identifiers import Identifier, IdentifierType
from app.models_structure import GHTContext, EntiteJuridique, EntiteGeographique, IdentifierNamespace
from app.models_structure import Pole, Service, UniteFonctionnelle, UniteHebergement, Chambre, Lit
from app.models_structure import LocationPhysicalType, LocationServiceType

def _reset_db():
    from sqlmodel import SQLModel
    print("⚠️  Suppression complète de la base...")
    SQLModel.metadata.drop_all(engine)
    init_db()
    print("✓ Base réinitialisée")

def _get_or_create_ght(session: Session) -> GHTContext:
    # Créer le GHT d'abord
    ght = session.exec(select(GHTContext).where(GHTContext.code == "GHT-DEMO")).first()
    if not ght:
        ght = GHTContext(
            name="GHT DEMO Complet",
            code="GHT-DEMO",
            description="GHT de démonstration avec structure et identités complètes",
            oid_racine="1.2.250.1.213.1.1",
            fhir_server_url="http://localhost:8000/fhir",
            is_active=True
        )
        session.add(ght); session.commit(); session.refresh(ght)
        print("✓ GHT DEMO créé")
    else:
        print("✓ GHT DEMO existant")
    # Endpoint MLLP GHT pour structure HL7 MFN (émission et réception)
    from app.models_shared import SystemEndpoint, EndpointKind, EndpointRole
    mfn_endpoint = session.exec(select(SystemEndpoint).where(SystemEndpoint.name == "HL7 MFN GHT DEMO")).first()
    if not mfn_endpoint:
        mfn_endpoint = SystemEndpoint(
            name="HL7 MFN GHT DEMO",
            kind=EndpointKind.MLLP,
            role=EndpointRole.BOTH,
            is_enabled=True,
            ght_context_id=ght.id,
            host="localhost",
            port=2575,
            sending_app="MEDBRIDGE",
            sending_facility="GHT-DEMO",
            receiving_app="STRUCTURE_SYSTEM",
            receiving_facility="GHT-DEMO"
        )
        session.add(mfn_endpoint); session.commit(); session.refresh(mfn_endpoint)
        print("✓ Endpoint HL7 MFN GHT DEMO (émission/réception) créé")
    # Créer un endpoint FHIR pour le GHT si absent
    endpoint = session.exec(select(SystemEndpoint).where(SystemEndpoint.name == "FHIR GHT DEMO")).first()
    if not endpoint:
        endpoint = SystemEndpoint(
            name="FHIR GHT DEMO",
            kind=EndpointKind.FHIR,
            role=EndpointRole.BOTH,
            is_enabled=True,
            ght_context_id=ght.id,
            base_url="http://localhost:8000/fhir",
            auth_kind="none"
        )
        session.add(endpoint); session.commit(); session.refresh(endpoint)
        print("✓ Endpoint FHIR GHT DEMO créé")
    ght = session.exec(select(GHTContext).where(GHTContext.code == "GHT-DEMO")).first()
    if not ght:
        ght = GHTContext(
            name="GHT DEMO Complet",
            code="GHT-DEMO",
            description="GHT de démonstration avec structure et identités complètes",
            oid_racine="1.2.250.1.213.1.1",
            fhir_server_url="http://localhost:8000/fhir",
            is_active=True
        )
        session.add(ght); session.commit(); session.refresh(ght)
        print("✓ GHT DEMO créé")
    else:
        print("✓ GHT DEMO existant")
    return ght

def _create_ej(session: Session, ght: GHTContext) -> EntiteJuridique:
    ej = session.exec(select(EntiteJuridique).where(EntiteJuridique.finess_ej == "750000001")).first()
    if not ej:
        ej = EntiteJuridique(
            name="CHU Démo Paris",
            short_name="CHU DEMO",
            finess_ej="750000001",
            siren="123456789",
            siret="12345678900001",
            address_line="1 Rue de l'Hôpital",
            postal_code="75001",
            city="Paris",
            ght_context_id=ght.id,
            is_active=True,
            strict_pam_fr=True
        )
        session.add(ej); session.commit(); session.refresh(ej)
        print("✓ Entité juridique créée")
    else:
        print("✓ EJ existante")

    # Créer les endpoints pour l'EJ après création effective
    from app.models_shared import SystemEndpoint, EndpointKind, EndpointRole
    # Supprimer les endpoints existants pour cette EJ
    existing_endpoints = session.exec(select(SystemEndpoint).where(SystemEndpoint.entite_juridique_id == ej.id)).all()
    for ep in existing_endpoints:
        session.delete(ep)
    session.commit()
    
    pam_recv = SystemEndpoint(
        name=f"IHE PAM RECV {ej.short_name}",
        kind=EndpointKind.MLLP,
        role=EndpointRole.RECEIVER,
        is_enabled=True,
        entite_juridique_id=ej.id,
        host="localhost",
        port=2575,
        sending_app="MEDBRIDGE",
        sending_facility=ej.short_name,
        receiving_app="PAM_SYSTEM",
        receiving_facility=ej.short_name
    )
    pam_send = SystemEndpoint(
        name=f"IHE PAM SEND {ej.short_name}",
        kind=EndpointKind.MLLP,
        role=EndpointRole.SENDER,
        is_enabled=True,
        entite_juridique_id=ej.id,
        host="localhost",
        port=2575,
        sending_app="MEDBRIDGE",
        sending_facility=ej.short_name,
        receiving_app="PAM_SYSTEM",
        receiving_facility=ej.short_name
    )
    pam_endpoint = SystemEndpoint(
        name=f"IHE PAM {ej.short_name}",
        kind=EndpointKind.MLLP,
        role=EndpointRole.BOTH,
        is_enabled=True,
        entite_juridique_id=ej.id,
        host="localhost",
        port=2575,
        sending_app="MEDBRIDGE",
        sending_facility=ej.short_name,
        receiving_app="PAM_SYSTEM",
        receiving_facility=ej.short_name
    )
    endpoint = SystemEndpoint(
        name=f"FHIR {ej.short_name}",
        kind=EndpointKind.FHIR,
        role=EndpointRole.BOTH,
        is_enabled=True,
        entite_juridique_id=ej.id,
        base_url="http://localhost:8000/fhir",
        auth_kind="none"
    )
    session.add(pam_recv)
    session.add(pam_send)
    session.add(pam_endpoint)
    session.add(endpoint)
    session.commit()
    print(f"✓ Endpoints créés pour {ej.short_name}")
    return ej

def _create_namespaces(session: Session, ght: GHTContext, ej: EntiteJuridique):
    ns_specs = [
        {"name": "IPP CHU DEMO", "system": "urn:oid:1.2.250.1.213.1.1.1", "type": "IPP", "ej": True},
        {"name": "NDA CHU DEMO", "system": "urn:oid:1.2.250.1.213.1.1.2", "type": "NDA", "ej": True},
        {"name": "VENUE CHU DEMO", "system": "urn:oid:1.2.250.1.213.1.1.3", "type": "VENUE", "ej": False},
        {"name": "STRUCTURE GHT", "system": "STRUCT-GHT-DEMO", "type": "STRUCTURE", "ej": False},
    ]
    for spec in ns_specs:
        existing = session.exec(
            select(IdentifierNamespace).where(
                IdentifierNamespace.system == spec["system"],
                IdentifierNamespace.ght_context_id == ght.id
            )
        ).first()
        if not existing:
            ns = IdentifierNamespace(
                name=spec["name"],
                system=spec["system"],
                type=spec["type"],
                ght_context_id=ght.id,
                entite_juridique_id=ej.id if spec["ej"] else None,
                is_active=True
            )
            session.add(ns)
    session.commit()
    print("✓ Namespaces créés")

def _create_structure(session: Session, ej: EntiteJuridique):
    # EG : identifiant unique par EJ
    eg_id = f"EG-{ej.finess_ej}"
    eg = session.exec(select(EntiteGeographique).where(EntiteGeographique.identifier == eg_id)).first()
    if not eg:
        eg = EntiteGeographique(
            identifier=eg_id,
            name=f"Site {ej.short_name}",
            short_name=f"{ej.short_name}-CENTRAL",
            finess=f"{ej.finess_ej}2",
            address_line1=ej.address_line,
            address_postalcode=ej.postal_code,
            address_city=ej.city,
            category_sae="MCO",
            type="MCO",
            physical_type="si",
            entite_juridique_id=ej.id,
            is_active=True
        )
        session.add(eg); session.commit(); session.refresh(eg)
        print(f"✓ EG créée pour {ej.short_name}")
    else:
        print(f"✓ EG existante pour {ej.short_name}")
    
    # Poles : identifiants uniques par EJ
    pole_specs = [
        {"id": f"POLE-MED-{ej.finess_ej}", "name": f"Pôle Médecine {ej.short_name}"},
        {"id": f"POLE-CHIR-{ej.finess_ej}", "name": f"Pôle Chirurgie {ej.short_name}"},
    ]
    poles = {}
    for ps in pole_specs:
        p = session.exec(select(Pole).where(Pole.identifier == ps["id"])).first()
        if not p:
            p = Pole(identifier=ps["id"], name=ps["name"], physical_type=LocationPhysicalType.AREA, entite_geo_id=eg.id, is_virtual=False)
            session.add(p); session.commit(); session.refresh(p)
        poles[ps["id"]] = p
    print(f"✓ {len(poles)} Pôles créés pour {ej.short_name}")
    
    # Services : identifiants uniques par EJ
    service_specs = [
        {"id": f"SVC-MED-CARDIO-{ej.finess_ej}", "name": f"Cardiologie {ej.short_name}", "pole": f"POLE-MED-{ej.finess_ej}", "type": LocationServiceType.MCO},
        {"id": f"SVC-MED-PNEUMO-{ej.finess_ej}", "name": f"Pneumologie {ej.short_name}", "pole": f"POLE-MED-{ej.finess_ej}", "type": LocationServiceType.MCO},
        {"id": f"SVC-CHIR-ORTHO-{ej.finess_ej}", "name": f"Chirurgie Orthopédique {ej.short_name}", "pole": f"POLE-CHIR-{ej.finess_ej}", "type": LocationServiceType.MCO},
    ]
    services = {}
    for ss in service_specs:
        s = session.exec(select(Service).where(Service.identifier == ss["id"])).first()
        if not s:
            s = Service(
                identifier=ss["id"], name=ss["name"], physical_type=LocationPhysicalType.SI,
                service_type=ss["type"], pole_id=poles[ss["pole"]].id, is_virtual=False
            )
            session.add(s); session.commit(); session.refresh(s)
        services[ss["id"]] = s
    print(f"✓ {len(services)} Services créés pour {ej.short_name}")
    
    # UF : identifiants uniques par EJ
    uf_specs = [
        {"id": f"UF-CARDIO-H-{ej.finess_ej}", "name": f"UF Cardio Hospitalisation {ej.short_name}", "service": f"SVC-MED-CARDIO-{ej.finess_ej}"},
        {"id": f"UF-PNEUMO-H-{ej.finess_ej}", "name": f"UF Pneumo Hospitalisation {ej.short_name}", "service": f"SVC-MED-PNEUMO-{ej.finess_ej}"},
        {"id": f"UF-ORTHO-H-{ej.finess_ej}", "name": f"UF Ortho Hospitalisation {ej.short_name}", "service": f"SVC-CHIR-ORTHO-{ej.finess_ej}"},
    ]
    ufs = {}
    for us in uf_specs:
        u = session.exec(select(UniteFonctionnelle).where(UniteFonctionnelle.identifier == us["id"])).first()
        if not u:
            u = UniteFonctionnelle(
                identifier=us["id"], name=us["name"], physical_type=LocationPhysicalType.SI,
                service_id=services[us["service"]].id
            )
            session.add(u); session.commit(); session.refresh(u)
        ufs[us["id"]] = u
    print(f"✓ {len(ufs)} UF créées pour {ej.short_name}")
    
    # UH : identifiants uniques par EJ
    uh_specs = [
        {"id": f"UH-CARDIO-1-{ej.finess_ej}", "name": f"UH Cardio Étage 1 {ej.short_name}", "uf": f"UF-CARDIO-H-{ej.finess_ej}"},
        {"id": f"UH-PNEUMO-2-{ej.finess_ej}", "name": f"UH Pneumo Étage 2 {ej.short_name}", "uf": f"UF-PNEUMO-H-{ej.finess_ej}"},
        {"id": f"UH-ORTHO-3-{ej.finess_ej}", "name": f"UH Ortho Étage 3 {ej.short_name}", "uf": f"UF-ORTHO-H-{ej.finess_ej}"},
    ]
    uhs = {}
    for uh_s in uh_specs:
        uh = session.exec(select(UniteHebergement).where(UniteHebergement.identifier == uh_s["id"])).first()
        if not uh:
            uh = UniteHebergement(
                identifier=uh_s["id"], name=uh_s["name"], physical_type=LocationPhysicalType.WI,
                unite_fonctionnelle_id=ufs[uh_s["uf"]].id
            )
            session.add(uh); session.commit(); session.refresh(uh)
        uhs[uh_s["id"]] = uh
    print(f"✓ {len(uhs)} UH créées pour {ej.short_name}")
    
    # Chambres + Lits (2 chambres / UH, 2 lits / chambre) : identifiants uniques par EJ
    ch_count = 0
    lit_count = 0
    for uh_id, uh in uhs.items():
        for ch_num in [1, 2]:
            ch_id = f"{uh_id}-CH{ch_num}-{ej.finess_ej}"
            ch = session.exec(select(Chambre).where(Chambre.identifier == ch_id)).first()
            if not ch:
                ch = Chambre(
                    identifier=ch_id, name=f"Chambre {ch_num} {ej.short_name}", physical_type=LocationPhysicalType.RO,
                    unite_hebergement_id=uh.id
                )
                session.add(ch); session.commit(); session.refresh(ch)
                ch_count += 1
            for lit_num in [1, 2]:
                lit_id = f"{ch_id}-LIT{lit_num}-{ej.finess_ej}"
                lit = session.exec(select(Lit).where(Lit.identifier == lit_id)).first()
                if not lit:
                    lit = Lit(
                        identifier=lit_id, name=f"Lit {lit_num} {ej.short_name}", physical_type=LocationPhysicalType.BD,
                        operational_status="O", chambre_id=ch.id
                    )
                    session.add(lit); session.commit()
                    lit_count += 1
    print(f"✓ {ch_count} Chambres, {lit_count} Lits créés pour {ej.short_name}")
    return eg, poles, services, ufs, uhs

def _create_patients_and_movements(session: Session):
    # Charger GHT et namespaces
    ght = session.exec(select(GHTContext).where(GHTContext.code == "GHT-DEMO")).first()
    namespaces_list = session.exec(
        select(IdentifierNamespace).where(IdentifierNamespace.ght_context_id == ght.id)
    ).all()
    namespaces = {ns.type: ns for ns in namespaces_list}
    
    # Séquences
    for seq_name in ["dossier", "venue", "mouvement"]:
        if not session.get(Sequence, seq_name):
            session.add(Sequence(name=seq_name, value=0))
    session.commit()
    
    now = datetime.utcnow()
    patient_specs = [
        {"family": "MARTIN", "given": "Alice", "birth": "1980-05-12", "gender": "female", "city": "Paris", "postal": "75001"},
        {"family": "DUPONT", "given": "Bernard", "birth": "1975-08-22", "gender": "male", "city": "Lyon", "postal": "69001"},
        {"family": "BERNARD", "given": "Claire", "birth": "1990-02-15", "gender": "female", "city": "Marseille", "postal": "13001"},
        {"family": "DURAND", "given": "David", "birth": "1985-03-10", "gender": "male", "city": "Toulouse", "postal": "31000"},
        {"family": "PETIT", "given": "Emma", "birth": "1992-11-28", "gender": "female", "city": "Nice", "postal": "06000"},
        {"family": "ROBERT", "given": "François", "birth": "1978-07-05", "gender": "male", "city": "Nantes", "postal": "44000"},
        {"family": "RICHARD", "given": "Gabrielle", "birth": "1988-12-18", "gender": "female", "city": "Strasbourg", "postal": "67000"},
        {"family": "SIMON", "given": "Henri", "birth": "1972-09-30", "gender": "male", "city": "Bordeaux", "postal": "33000"},
        {"family": "MICHEL", "given": "Isabelle", "birth": "1983-04-22", "gender": "female", "city": "Lille", "postal": "59000"},
    ]
    
    # Récupérer toutes les EJ et leur structure
    from app.models_structure import EntiteJuridique
    ejs = session.exec(select(EntiteJuridique)).all()
    # Pour chaque patient, répartir sur les EJ
    for idx, ps in enumerate(patient_specs, start=1):
        # Affectation équilibrée sur les EJ
        ej = ejs[(idx - 1) % len(ejs)]
        existing = session.exec(select(Patient).where(Patient.family == ps["family"], Patient.given == ps["given"], Patient.entite_juridique_id == ej.id)).first()
        if existing:
            continue
        from app.utils.seq_generator import generate_patient_seq
        patient = Patient(
            id=generate_patient_seq(),
            family=ps["family"], given=ps["given"], birth_date=ps["birth"], gender=ps["gender"],
            city=ps["city"], postal_code=ps["postal"], country="FR",
            identity_reliability_code="VALI", identity_reliability_date="2024-01-15", identity_reliability_source="CNI",
            entite_juridique_id=ej.id,
            ght_context_id=ej.ght_context_id
        )
        session.add(patient); session.commit(); session.refresh(patient)
        # Récupérer une UF hospitalisation de l'EJ
        from app.models_structure import UniteFonctionnelle
        ufs_hosp = session.exec(select(UniteFonctionnelle).where(UniteFonctionnelle.name.ilike('%hospitalisation%'))).all()
        uf_hosp = None
        for uf in ufs_hosp:
            # Vérifie que l'UF appartient à un service d'une EJ
            if uf.service and uf.service.pole and uf.service.pole.entite_geo and uf.service.pole.entite_geo.entite_juridique_id == ej.id:
                uf_hosp = uf
                break
        dossier = Dossier(
            dossier_seq=get_next_sequence(session, "dossier"),
            patient_id=patient.id,
            admit_time=now, dossier_type=DossierType.HOSPITALISE, reason="Admission démonstration"
        )
        session.add(dossier); session.commit(); session.refresh(dossier)
        # Créer identifiant IPP pour le patient
        ipp_ns = namespaces.get("IPP")
        if ipp_ns:
            ipp = Identifier(
                value=f"IPP{idx:06d}",
                type=IdentifierType.IPP,
                system=ipp_ns.system,
                oid=ipp_ns.system.split(":")[-1],
                patient_id=patient.id,
                status="active"
            )
            session.add(ipp)
        # Créer identifiant NDA pour le dossier
        nda_ns = namespaces.get("NDA")
        if nda_ns:
            nda = Identifier(
                value=f"NDA{dossier.dossier_seq:08d}",
                type=IdentifierType.NDA,
                system=nda_ns.system,
                oid=nda_ns.system.split(":")[-1],
                dossier_id=dossier.id,
                status="active"
            )
            session.add(nda)
        # Utiliser l'UF hospitalisation réelle ou None pour la venue
        venue = Venue(
            venue_seq=get_next_sequence(session, "venue"),
            dossier_id=dossier.id, uf_responsabilite=uf_hosp.identifier if uf_hosp else None,
            start_time=now, code=f"V-{ej.short_name}-{idx}", label=f"Venue {ej.short_name} {idx}", operational_status="active"
        )
        session.add(venue); session.commit(); session.refresh(venue)
        # Créer identifiant VENUE (Visit Number)
        venue_ns = namespaces.get("VENUE")
        if venue_ns:
            venue_id = Identifier(
                value=f"VEN{venue.venue_seq:08d}",
                type=IdentifierType.VN,  # VN = Visit Number
                system=venue_ns.system,
                oid=venue_ns.system.split(":")[-1],
                venue_id=venue.id,
                status="active"
            )
            session.add(venue_id)
        
        # Mouvements IHE PAM: A01 admission → A02 transfert → A03 sortie
            # Affectation cohérente du lit selon la structure
            # Récupérer un lit réel lié à l'UF hospitalisation
            lit_adm = None
            lit_trans = None
            lit_sortie = None
            if uf_hosp:
                # Récupérer une UH liée à l'UF hospitalisation
                uh = session.exec(select(UniteHebergement).where(UniteHebergement.unite_fonctionnelle_id == uf_hosp.id)).first()
                if uh:
                    # Récupérer les chambres et lits
                    chambres = session.exec(select(Chambre).where(Chambre.unite_hebergement_id == uh.id)).all()
                    chambre1 = chambres[0] if len(chambres) > 0 else None
                    chambre2 = chambres[1] if len(chambres) > 1 else None
                    if chambre1:
                        lit_adm = session.exec(select(Lit).where(Lit.chambre_id == chambre1.id)).first()
                    if chambre2:
                        lit_trans = session.exec(select(Lit).where(Lit.chambre_id == chambre2.id)).first()
                        lit_sortie = lit_trans
            movements = [
                ("Admission", "A01", lit_adm.identifier if lit_adm else None),
                ("Transfert", "A02", lit_trans.identifier if lit_trans else None),
                ("Sortie", "A03", lit_sortie.identifier if lit_sortie else None),
            ]
        # Récupérer les UF réelles de la structure liées à la venue
        # On suppose que venue.dossier_id permet de retrouver le dossier, puis l'UF de responsabilité
        uf_responsabilite = None
        if venue.uf_responsabilite:
            uf_responsabilite = session.exec(select(UniteFonctionnelle).where(UniteFonctionnelle.identifier == venue.uf_responsabilite)).first()
        # Recherche des UF médicales, soins, hébergement associées au service de l'UF de responsabilité
        uf_medicale = None
        uf_soins = None
        uf_hebergement = None
        if uf_responsabilite:
            service = uf_responsabilite.service
            # UF médicale : typologie ou nom contient 'médicale'
            uf_medicale = session.exec(select(UniteFonctionnelle).where(UniteFonctionnelle.service_id == service.id, UniteFonctionnelle.name.ilike('%med%'))).first()
            # UF soins : typologie ou nom contient 'soins'
            uf_soins = session.exec(select(UniteFonctionnelle).where(UniteFonctionnelle.service_id == service.id, UniteFonctionnelle.name.ilike('%soin%'))).first()
            # UF hébergement : typologie ou nom contient 'hébergement'
            uf_hebergement = session.exec(select(UniteFonctionnelle).where(UniteFonctionnelle.service_id == service.id, UniteFonctionnelle.name.ilike('%hébergement%'))).first()
        for m_idx, (mt, trigger, loc) in enumerate(movements, start=1):
            mouvement = Mouvement(
                mouvement_seq=get_next_sequence(session, "mouvement"),
                venue_id=venue.id, when=now + timedelta(hours=m_idx),
                location=loc, trigger_event=trigger, movement_type=mt,
                uf_medicale_code=uf_medicale.um_code if uf_medicale else None,
                uf_medicale_label=uf_medicale.name if uf_medicale else None,
                uf_soins_code=uf_soins.um_code if uf_soins else None,
                uf_soins_label=uf_soins.name if uf_soins else None,
                uf_hebergement_code=uf_hebergement.um_code if uf_hebergement else None,
                uf_hebergement_label=uf_hebergement.name if uf_hebergement else None
            )
            session.add(mouvement)
        session.commit()
    
    patient_count = len(session.exec(select(Patient)).all())
    print(f"✓ {patient_count} Patients + Dossiers + Venues + Mouvements créés")

def main():
    parser = argparse.ArgumentParser(description="Seed complet GHT DEMO")
    parser.add_argument("--reset", action="store_true", help="Réinitialiser la base avant seed")
    args = parser.parse_args()
    
    if args.reset:
        _reset_db()
    else:
        init_db()
    
    with Session(engine) as session:
        print("🚀 Seed GHT DEMO multi-EJ...\n")
        ght = _get_or_create_ght(session)
        ej_specs = [
            {"name": "CHU Démo Paris", "short_name": "CHU DEMO", "finess_ej": "750000001", "siren": "123456789", "siret": "12345678900001", "address_line": "1 Rue de l'Hôpital", "postal_code": "75001", "city": "Paris"},
            {"name": "Hôpital Sud", "short_name": "HOP SUD", "finess_ej": "750000010", "siren": "987654321", "siret": "98765432100010", "address_line": "10 Avenue du Sud", "postal_code": "75010", "city": "Paris"},
            {"name": "Clinique Est", "short_name": "CLIN EST", "finess_ej": "750000020", "siren": "192837465", "siret": "19283746500020", "address_line": "20 Boulevard de l'Est", "postal_code": "75020", "city": "Paris"}
        ]
        ejs = []
        structures = []
        for ej_spec in ej_specs:
            ej = session.exec(select(EntiteJuridique).where(EntiteJuridique.finess_ej == ej_spec["finess_ej"])).first()
            if not ej:
                ej = EntiteJuridique(
                    name=ej_spec["name"], short_name=ej_spec["short_name"], finess_ej=ej_spec["finess_ej"],
                    siren=ej_spec["siren"], siret=ej_spec["siret"], address_line=ej_spec["address_line"],
                    postal_code=ej_spec["postal_code"], city=ej_spec["city"], ght_context_id=ght.id,
                    is_active=True, strict_pam_fr=True
                )
                session.add(ej); session.commit(); session.refresh(ej)
                print(f"✓ EJ créée : {ej.name}")
            else:
                print(f"✓ EJ existante : {ej.name}")
            # Création des endpoints pour chaque EJ
            from app.models_shared import SystemEndpoint, EndpointKind, EndpointRole
            # Supprimer les endpoints existants pour cette EJ
            existing_endpoints = session.exec(select(SystemEndpoint).where(SystemEndpoint.entite_juridique_id == ej.id)).all()
            for ep in existing_endpoints:
                session.delete(ep)
            session.commit()
            
            pam_recv = SystemEndpoint(
                name=f"IHE PAM RECV {ej.short_name}",
                kind=EndpointKind.MLLP,
                role=EndpointRole.RECEIVER,
                is_enabled=True,
                entite_juridique_id=ej.id,
                host="localhost",
                port=2575,
                sending_app="MEDBRIDGE",
                sending_facility=ej.short_name,
                receiving_app="PAM_SYSTEM",
                receiving_facility=ej.short_name
            )
            pam_send = SystemEndpoint(
                name=f"IHE PAM SEND {ej.short_name}",
                kind=EndpointKind.MLLP,
                role=EndpointRole.SENDER,
                is_enabled=True,
                entite_juridique_id=ej.id,
                host="localhost",
                port=2575,
                sending_app="MEDBRIDGE",
                sending_facility=ej.short_name,
                receiving_app="PAM_SYSTEM",
                receiving_facility=ej.short_name
            )
            pam_endpoint = SystemEndpoint(
                name=f"IHE PAM {ej.short_name}",
                kind=EndpointKind.MLLP,
                role=EndpointRole.BOTH,
                is_enabled=True,
                entite_juridique_id=ej.id,
                host="localhost",
                port=2575,
                sending_app="MEDBRIDGE",
                sending_facility=ej.short_name,
                receiving_app="PAM_SYSTEM",
                receiving_facility=ej.short_name
            )
            endpoint = SystemEndpoint(
                name=f"FHIR {ej.short_name}",
                kind=EndpointKind.FHIR,
                role=EndpointRole.BOTH,
                is_enabled=True,
                entite_juridique_id=ej.id,
                base_url="http://localhost:8000/fhir",
                auth_kind="none"
            )
            session.add(pam_recv)
            session.add(pam_send)
            session.add(pam_endpoint)
            session.add(endpoint)
            session.commit()
            print(f"✓ Endpoints créés pour {ej.short_name}")
            _create_namespaces(session, ght, ej)
            eg, poles, services, ufs, uhs = _create_structure(session, ej)
            structures.append({"ej": ej, "eg": eg, "poles": poles, "services": services, "ufs": ufs, "uhs": uhs})
            ejs.append(ej)
        # À FAIRE : répartir les patients/dossiers/mouvements sur toutes les EJ/structures
        _create_patients_and_movements(session)  # À adapter pour multi-EJ
        print("\n✅ Seed multi-EJ terminé")
        print(f"   GHT: {ght.name} (code={ght.code})")
        print(f"   EJ: {[ej.name for ej in ejs]}")
        print(f"   Structure: EG → Poles → Services → UF → UH → CH → Lits pour chaque EJ")
        print(f"   Identités: Patients avec IPP, Dossiers avec NDA, Venues")
        print(f"   Mouvements: IHE PAM (A01/A02/A03)")

if __name__ == "__main__":
    main()
