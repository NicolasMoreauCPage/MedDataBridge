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
from app.models import Patient, Dossier, Venue, Mouvement, DossierType
from app.models import Sequence
from app.models_identifiers import Identifier, IdentifierType
from app.models_structure import GHTContext, EntiteJuridique, EntiteGeographique, IdentifierNamespace
from app.models_structure import Pole, Service, UniteFonctionnelle, UniteHebergement, Chambre, Lit
from app.models_structure import LocationPhysicalType, LocationServiceType

def _create_realistic_cotations(session: Session, dossier: Dossier, admission_reason: str, admit_time: datetime, stay_days: int):
    """Crée des cotations réalistes basées sur le motif d'admission"""
    
    # Récupérer un médecin responsable pour les actes
    from app.models_practitioners import MedecinResponsable
    medecin = session.exec(select(MedecinResponsable)).first()
    if not medecin:
        # Créer un médecin par défaut si aucun n'existe
        medecin = MedecinResponsable(
            rpps="12345678901",
            nom="DUPONT",
            prenom="Jean",
            specialite="Médecine générale"
        )
        session.add(medecin)
        session.commit()
        session.refresh(medecin)
    
    cotations = []
    
    if "Infarctus" in admission_reason:
        # Actes pour infarctus du myocarde
        cotations.extend([
            # CCAM: Coronarographie
            {"type": "CCAM", "code": "DEQP001", "activite": "01", "designation": "Coronarographie", "montant": 450.0, "days_offset": 0},
            # CCAM: Angioplastie
            {"type": "CCAM", "code": "DEQP003", "activite": "01", "designation": "Angioplastie coronaire", "montant": 1200.0, "days_offset": 1},
            # NGAP: Consultation cardiologie
            {"type": "NGAP", "lettre": "C", "coefficient": 45, "designation": "Consultation cardiologie", "days_offset": 0},
            # UCD: Médicaments cardiovasculaires
            {"type": "UCD", "cip": "3400932345678", "designation": "Clopidogrel 75mg", "quantite": 30, "prix_unit": 12.5, "days_offset": 2},
        ])
    
    elif "Pneumonie" in admission_reason:
        # Actes pour pneumonie
        cotations.extend([
            # CCAM: Radiographie thoracique
            {"type": "CCAM", "code": "DEQP002", "activite": "01", "designation": "Radiographie thoracique", "montant": 25.0, "days_offset": 0},
            # CCAM: Fibroscopie bronchique
            {"type": "CCAM", "code": "DEQP004", "activite": "01", "designation": "Fibroscopie bronchique", "montant": 180.0, "days_offset": 1},
            # NGAP: Consultation pneumologie
            {"type": "NGAP", "lettre": "C", "coefficient": 42, "designation": "Consultation pneumologie", "days_offset": 0},
            # UCD: Antibiotiques
            {"type": "UCD", "cip": "3400933456789", "designation": "Amoxicilline 1g", "quantite": 20, "prix_unit": 8.5, "days_offset": 0},
        ])
    
    elif "Accouchement" in admission_reason:
        # Actes pour accouchement
        cotations.extend([
            # CCAM: Césarienne
            {"type": "CCAM", "code": "DEQP005", "activite": "01", "designation": "Césarienne", "montant": 850.0, "days_offset": 0},
            # NGAP: Accouchement
            {"type": "NGAP", "lettre": "P", "coefficient": 120, "designation": "Accouchement par césarienne", "days_offset": 0},
            # UCD: Médicaments obstétricaux
            {"type": "UCD", "cip": "3400934567890", "designation": "Ocytocine 5UI", "quantite": 2, "prix_unit": 15.0, "days_offset": 0},
        ])
    
    elif "Fracture" in admission_reason:
        # Actes pour fracture du fémur
        cotations.extend([
            # CCAM: Ostéosynthèse
            {"type": "CCAM", "code": "DEQP006", "activite": "01", "designation": "Ostéosynthèse fémur", "montant": 950.0, "days_offset": 0},
            # CCAM: Radiographie
            {"type": "CCAM", "code": "DEQP007", "activite": "01", "designation": "Radiographie membre inférieur", "montant": 35.0, "days_offset": 0},
            # NGAP: Consultation orthopédie
            {"type": "NGAP", "lettre": "C", "coefficient": 48, "designation": "Consultation orthopédie", "days_offset": 0},
            # LPP: Prothèse
            {"type": "LPP", "code": "1234567890123", "designation": "Prothèse totale de hanche", "quantite": 1, "prix_unit": 2500.0, "days_offset": 3},
        ])
    
    elif "Appendicite" in admission_reason:
        # Actes pour appendicite
        cotations.extend([
            # CCAM: Appendicectomie
            {"type": "CCAM", "code": "DEQP008", "activite": "01", "designation": "Appendicectomie par cœlioscopie", "montant": 650.0, "days_offset": 0},
            # CCAM: Échographie
            {"type": "CCAM", "code": "DEQP009", "activite": "01", "designation": "Échographie abdominale", "montant": 45.0, "days_offset": 0},
            # NGAP: Consultation chirurgie
            {"type": "NGAP", "lettre": "C", "coefficient": 50, "designation": "Consultation chirurgie digestive", "days_offset": 0},
            # UCD: Antibiotiques
            {"type": "UCD", "cip": "3400935678901", "designation": "Ceftriaxone 1g", "quantite": 5, "prix_unit": 22.0, "days_offset": 0},
        ])
    
    elif "Chirurgie de la hanche" in admission_reason:
        # Actes pour PTH
        cotations.extend([
            # CCAM: PTH
            {"type": "CCAM", "code": "DEQP010", "activite": "01", "designation": "Prothèse totale de hanche", "montant": 1800.0, "days_offset": 0},
            # CCAM: Radiographie pré-op
            {"type": "CCAM", "code": "DEQP011", "activite": "01", "designation": "Radiographie hanche", "montant": 30.0, "days_offset": -1},
            # NGAP: Consultation orthopédie
            {"type": "NGAP", "lettre": "C", "coefficient": 48, "designation": "Consultation orthopédie", "days_offset": -7},
            # LPP: Prothèse
            {"type": "LPP", "code": "2345678901234", "designation": "Prothèse totale de hanche cimentée", "quantite": 1, "prix_unit": 2800.0, "days_offset": 0},
        ])
    
    elif "Insuffisance rénale" in admission_reason:
        # Actes pour IRC
        cotations.extend([
            # CCAM: Hémodialyse
            {"type": "CCAM", "code": "DEQP012", "activite": "01", "designation": "Séance d'hémodialyse", "montant": 320.0, "days_offset": 0},
            # CCAM: Bilan sanguin
            {"type": "CCAM", "code": "DEQP013", "activite": "01", "designation": "Bilan rénal complet", "montant": 85.0, "days_offset": 0},
            # NGAP: Consultation néphrologie
            {"type": "NGAP", "lettre": "C", "coefficient": 46, "designation": "Consultation néphrologie", "days_offset": 0},
            # UCD: Médicaments néphro
            {"type": "UCD", "cip": "3400936789012", "designation": "Erythropoïétine 2000UI", "quantite": 1, "prix_unit": 45.0, "days_offset": 2},
        ])
    
    elif "Cancer" in admission_reason:
        # Actes pour cancer colorectal
        cotations.extend([
            # CCAM: Coloscopie
            {"type": "CCAM", "code": "DEQP014", "activite": "01", "designation": "Coloscopie totale", "montant": 120.0, "days_offset": -3},
            # CCAM: Chirurgie colorectale
            {"type": "CCAM", "code": "DEQP015", "activite": "01", "designation": "Résection colorectale", "montant": 2200.0, "days_offset": 0},
            # NGAP: Consultation oncologie
            {"type": "NGAP", "lettre": "C", "coefficient": 52, "designation": "Consultation oncologie", "days_offset": -7},
            # UCD: Chimiothérapie
            {"type": "UCD", "cip": "3400937890123", "designation": "5-FU 500mg", "quantite": 1, "prix_unit": 85.0, "days_offset": 5},
        ])
    
    elif "AVC" in admission_reason:
        # Actes pour AVC
        cotations.extend([
            # CCAM: Scanner cérébral
            {"type": "CCAM", "code": "DEQP016", "activite": "01", "designation": "Scanner cérébral", "montant": 95.0, "days_offset": 0},
            # CCAM: IRM cérébrale
            {"type": "CCAM", "code": "DEQP017", "activite": "01", "designation": "IRM cérébrale", "montant": 180.0, "days_offset": 1},
            # NGAP: Consultation neurologie
            {"type": "NGAP", "lettre": "C", "coefficient": 44, "designation": "Consultation neurologie", "days_offset": 0},
            # UCD: Anticoagulants
            {"type": "UCD", "cip": "3400938901234", "designation": "Héparine 5000UI", "quantite": 10, "prix_unit": 18.0, "days_offset": 0},
        ])
    
    else:
        # Cas par défaut - actes génériques
        cotations.extend([
            # CCAM: Consultation
            {"type": "CCAM", "code": "DEQP018", "activite": "01", "designation": "Consultation spécialisée", "montant": 60.0, "days_offset": 0},
            # NGAP: Visite
            {"type": "NGAP", "lettre": "V", "coefficient": 25, "designation": "Visite médicale", "days_offset": 1},
            # UCD: Médicaments génériques
            {"type": "UCD", "cip": "3400939012345", "designation": "Paracétamol 1000mg", "quantite": 20, "prix_unit": 2.5, "days_offset": 0},
        ])
    
    # Créer les actes dans la base
    for cotation in cotations:
        execute_date = admit_time + timedelta(days=cotation["days_offset"])
        
        if cotation["type"] == "CCAM":
            acte = CCAMAct(
                dossier_id=dossier.id,
                code_acte=cotation["code"],
                code_activite=cotation["activite"],
                execute_date=execute_date,
                montant=cotation["montant"],
                executant_id=medecin.id,
                commentaire=cotation["designation"]
            )
        elif cotation["type"] == "NGAP":
            acte = NGAPAct(
                dossier_id=dossier.id,
                lettre_cle=cotation["lettre"],
                coefficient=cotation["coefficient"],
                execute_date=execute_date,
                montant=cotation["coefficient"] * 0.5,  # Tarif approximatif
                prestataire_id=medecin.id,
                commentaire=cotation["designation"]
            )
        elif cotation["type"] == "UCD":
            acte = UCDAct(
                dossier_id=dossier.id,
                code_cip=cotation["cip"],
                designation=cotation["designation"],
                quantite=cotation["quantite"],
                prix_unitaire=cotation["prix_unit"],
                montant_total=cotation["quantite"] * cotation["prix_unit"],
                execute_date=execute_date,
                prestataire_id=medecin.id
            )
        elif cotation["type"] == "LPP":
            acte = LPPAct(
                dossier_id=dossier.id,
                code_lpp=cotation["code"],
                libelle=cotation["designation"],
                quantite=cotation["quantite"],
                prix_unitaire=cotation["prix_unit"],
                montant_total=cotation["quantite"] * cotation["prix_unit"],
                execute_date=execute_date,
                prestataire_id=medecin.id
            )
        
        session.add(acte)
    
    session.commit()
from app.models import CCAMAct, NGAPAct, UCDAct, LPPAct

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
        # Patients avec pathologies diverses et âges variés
        {"family": "MARTIN", "given": "Alice", "birth": "1980-05-12", "gender": "female", "city": "Paris", "postal": "75001", "admission_reason": "Infarctus du myocarde", "stay_days": 7},
        {"family": "DUPONT", "given": "Bernard", "birth": "1975-08-22", "gender": "male", "city": "Lyon", "postal": "69001", "admission_reason": "Pneumonie communautaire", "stay_days": 5},
        {"family": "BERNARD", "given": "Claire", "birth": "1990-02-15", "gender": "female", "city": "Marseille", "postal": "13001", "admission_reason": "Accouchement par césarienne", "stay_days": 4},
        {"family": "DURAND", "given": "David", "birth": "1985-03-10", "gender": "male", "city": "Toulouse", "postal": "31000", "admission_reason": "Fracture du fémur", "stay_days": 12},
        {"family": "PETIT", "given": "Emma", "birth": "1992-11-28", "gender": "female", "city": "Nice", "postal": "06000", "admission_reason": "Appendicite aiguë", "stay_days": 3},
        {"family": "ROBERT", "given": "François", "birth": "1978-07-05", "gender": "male", "city": "Nantes", "postal": "44000", "admission_reason": "Chirurgie de la hanche", "stay_days": 8},
        {"family": "RICHARD", "given": "Gabrielle", "birth": "1988-12-18", "gender": "female", "city": "Strasbourg", "postal": "67000", "admission_reason": "Insuffisance rénale chronique", "stay_days": 15},
        {"family": "SIMON", "given": "Henri", "birth": "1972-09-30", "gender": "male", "city": "Bordeaux", "postal": "33000", "admission_reason": "Cancer colorectal", "stay_days": 21},
        {"family": "MICHEL", "given": "Isabelle", "birth": "1983-04-22", "gender": "female", "city": "Lille", "postal": "59000", "admission_reason": "AVC ischémique", "stay_days": 10},
        # Patients supplémentaires pour plus de variété
        {"family": "THOMAS", "given": "Jean-Pierre", "birth": "1965-06-14", "gender": "male", "city": "Rouen", "postal": "76000", "admission_reason": "Bronchopneumopathie chronique obstructive", "stay_days": 6},
        {"family": "LEGRAND", "given": "Marie-Claire", "birth": "1948-09-03", "gender": "female", "city": "Reims", "postal": "51100", "admission_reason": "Arthrose sévère", "stay_days": 9},
        {"family": "MOREAU", "given": "Pierre-Louis", "birth": "1995-01-20", "gender": "male", "city": "Grenoble", "postal": "38000", "admission_reason": "Traumatisme crânien", "stay_days": 5},
        {"family": "ROUSSEAU", "given": "Sophie", "birth": "1987-11-11", "gender": "female", "city": "Dijon", "postal": "21000", "admission_reason": "Grossesse extra-utérine", "stay_days": 2},
        {"family": "GARNIER", "given": "Michel", "birth": "1959-12-25", "gender": "male", "city": "Tours", "postal": "37000", "admission_reason": "Chirurgie cardiaque", "stay_days": 14},
        {"family": "FAURE", "given": "Catherine", "birth": "1976-04-08", "gender": "female", "city": "Clermont-Ferrand", "postal": "63000", "admission_reason": "Thyroïdectomie", "stay_days": 4},
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
            admit_time=now, dossier_type=DossierType.HOSPITALISE, reason=ps["admission_reason"]
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
            # Calculer le timing basé sur la durée de séjour
            if trigger == "A01":  # Admission
                movement_time = now
            elif trigger == "A02":  # Transfert (milieu du séjour)
                movement_time = now + timedelta(days=ps["stay_days"] // 2)
            else:  # A03 Sortie
                movement_time = now + timedelta(days=ps["stay_days"])
            
            mouvement = Mouvement(
                mouvement_seq=get_next_sequence(session, "mouvement"),
                venue_id=venue.id, when=movement_time,
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
        
        # Créer des cotations réalistes basées sur le motif d'admission
        _create_realistic_cotations(session, dossier, ps["admission_reason"], now, ps["stay_days"])
    
    patient_count = len(session.exec(select(Patient)).all())
    mouvement_count = len(session.exec(select(Mouvement)).all())
    ccam_count = len(session.exec(select(CCAMAct)).all())
    ngap_count = len(session.exec(select(NGAPAct)).all())
    ucd_count = len(session.exec(select(UCDAct)).all())
    lpp_count = len(session.exec(select(LPPAct)).all())
    
    print(f"✓ {patient_count} Patients + Dossiers + Venues + {mouvement_count} Mouvements créés")
    print(f"✓ Cotations créées: {ccam_count} CCAM, {ngap_count} NGAP, {ucd_count} UCD, {lpp_count} LPP")

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
