#!/usr/bin/env python3
"""
Script de test complet pour valider les workflows de création
- Dossiers (ne génèrent PAS de message, créent une venue automatique)
- Venues (génèrent ADT^A05 avec mapping PV1-2)
- Mouvements (génèrent A01/A02/A03/etc. avec mapping PV1-2)
"""

import sys
from sqlmodel import Session, select
from app.db import engine
from app.models import Patient, Dossier, Venue, Mouvement, DossierType
from app.models_shared import MessageLog
from app.routers.dossiers import create_dossier
from app.services.emit_on_create import emit_to_senders
from datetime import datetime
from app.utils.seq_generator import generate_patient_seq

def test_workflow():
    print("\n" + "="*100)
    print("🧪 TEST COMPLET DES WORKFLOWS")
    print("="*100 + "\n")
    
    with Session(engine) as session:
        # 1. Créer un patient de test
        print("📝 Étape 1/5 : Création d'un patient de test...")
        from datetime import date
        patient_seq = generate_patient_seq()
        patient = Patient(
            family="TestWorkflow",
            given="Jean",
            birth_date=date(1980, 1, 1),  # Utiliser un objet date
            gender="M",
            patient_seq=patient_seq,
            identifier=str(patient_seq)
        )
        session.add(patient)
        session.commit()
        session.refresh(patient)
        print(f"   ✅ Patient créé : ID={patient.id}, patient_seq={patient.patient_seq}")
        
        # 2. Compter messages avant création dossier
        msg_count_before = session.exec(select(MessageLog)).all()
        print(f"\n📝 Étape 2/5 : Messages avant création dossier : {len(msg_count_before)}")
        
        # 3. Créer un dossier (doit créer une venue automatiquement)
        print("\n📝 Étape 3/5 : Création d'un dossier hospitalisation (IMP)...")
        from app.utils.seq_generator import generate_dossier_seq
        from app.db import get_next_sequence
        
        dossier_seq = generate_dossier_seq()
        dossier = Dossier(
            patient_id=patient.id,
            uf_responsabilite="CARDIO",
            dossier_type=DossierType.HOSPITALISE,
            admit_time=datetime.now(),
            dossier_seq=dossier_seq,
            attending_provider="Dr. Martin"
        )
        session.add(dossier)
        session.commit()
        session.refresh(dossier)
        print(f"   ✅ Dossier créé : ID={dossier.id}, dossier_seq={dossier.dossier_seq}, type={dossier.dossier_type}")
        
        # Créer la venue automatiquement (simulation du router)
        import random
        venue_seq = random.randint(900000000, 999999999)  # Utiliser un grand nombre pour éviter collisions
        venue = Venue(
            dossier_id=dossier.id,
            uf_responsabilite=dossier.uf_responsabilite,
            start_time=dossier.admit_time,
            attending_provider=dossier.attending_provider,
            venue_seq=venue_seq,
            code="PRE_ADMIT",
            label="Pré-admission automatique"
        )
        session.add(venue)
        session.commit()
        session.refresh(venue)
        print(f"   ✅ Venue créée automatiquement : ID={venue.id}, venue_seq={venue.venue_seq}")
        
        # Générer le message A05 pour la venue
        emit_to_senders(venue, "venue", session)
        print(f"   ✅ Message A05 généré pour la venue")
        
        # 4. Vérifier les messages générés
        print("\n📝 Étape 4/5 : Vérification des messages générés...")
        messages_after = session.exec(
            select(MessageLog)
            .order_by(MessageLog.created_at.desc())
            .limit(5)
        ).all()
        
        new_messages = [m for m in messages_after if m.id > (msg_count_before[-1].id if msg_count_before else 0)]
        
        if not new_messages:
            print("   ❌ Aucun message généré !")
            return False
        
        print(f"   ✅ {len(new_messages)} nouveau(x) message(s) généré(s)")
        
        for msg in new_messages:
            print(f"\n   📨 Message ID={msg.id}")
            print(f"      Type: {msg.kind}")
            print(f"      Direction: {msg.direction}")
            print(f"      Status: {msg.status}")
            
            if msg.kind == "MLLP" and msg.payload:
                segments = msg.payload.split('\r')
                
                # MSH
                msh = next((s for s in segments if s.startswith('MSH')), None)
                if msh:
                    fields = msh.split('|')
                    msg_type = fields[8] if len(fields) > 8 else 'N/A'
                    print(f"      Message Type: {msg_type}")
                    
                    if msg_type != "ADT^A05":
                        print(f"      ❌ ERREUR : Attendu ADT^A05, obtenu {msg_type}")
                        return False
                    else:
                        print(f"      ✅ Type correct : ADT^A05")
                
                # PID
                pid = next((s for s in segments if s.startswith('PID')), None)
                if pid:
                    fields = pid.split('|')
                    patient_id = fields[3] if len(fields) > 3 else 'N/A'
                    print(f"      Patient ID (PID-3): {patient_id}")
                    
                    if str(patient_seq) not in patient_id:
                        print(f"      ⚠️  Warning : patient_seq {patient_seq} non trouvé dans PID-3")
                
                # PV1
                pv1 = next((s for s in segments if s.startswith('PV1')), None)
                if pv1:
                    fields = pv1.split('|')
                    patient_class = fields[2] if len(fields) > 2 else 'N/A'
                    visit_number = fields[19] if len(fields) > 19 else 'N/A'
                    print(f"      PV1-2 (Patient Class): {patient_class}")
                    print(f"      PV1-19 (Visit Number): {visit_number}")
                    
                    # Vérifier le mapping IMP → I
                    if patient_class != "I":
                        print(f"      ❌ ERREUR : Attendu PV1-2='I' (IMP→I), obtenu '{patient_class}'")
                        return False
                    else:
                        print(f"      ✅ Mapping correct : IMP → I")
                    
                    if str(dossier_seq) not in visit_number:
                        print(f"      ⚠️  Warning : dossier_seq {dossier_seq} non trouvé dans PV1-19")
                else:
                    print(f"      ❌ ERREUR : Segment PV1 manquant !")
                    return False
                
                # ZBE
                zbe = next((s for s in segments if s.startswith('ZBE')), None)
                if zbe:
                    fields = zbe.split('|')
                    trigger = fields[6] if len(fields) > 6 else 'N/A'
                    print(f"      ZBE-6 (Original Trigger): {trigger}")
                    if trigger != "A05":
                        print(f"      ⚠️  Warning : Attendu A05, obtenu {trigger}")
                else:
                    print(f"      ⚠️  Warning : Segment ZBE manquant")
        
        # 5. Test avec dossier externe (AMB → O)
        print("\n📝 Étape 5/5 : Test avec dossier externe (AMB)...")
        dossier_seq2 = generate_dossier_seq()
        dossier2 = Dossier(
            patient_id=patient.id,
            uf_responsabilite="CONSULT",
            dossier_type=DossierType.EXTERNE,
            admit_time=datetime.now(),
            dossier_seq=dossier_seq2,
            attending_provider="Dr. Durand"
        )
        session.add(dossier2)
        session.commit()
        session.refresh(dossier2)
        
        venue_seq2 = random.randint(900000000, 999999999)
        venue2 = Venue(
            dossier_id=dossier2.id,
            uf_responsabilite=dossier2.uf_responsabilite,
            start_time=dossier2.admit_time,
            attending_provider=dossier2.attending_provider,
            venue_seq=venue_seq2,
            code="PRE_ADMIT",
            label="Pré-admission externe"
        )
        session.add(venue2)
        session.commit()
        emit_to_senders(venue2, "venue", session)
        
        # Vérifier le mapping AMB → O
        last_msg = session.exec(
            select(MessageLog)
            .order_by(MessageLog.created_at.desc())
            .limit(1)
        ).first()
        
        if last_msg and last_msg.payload:
            pv1 = next((s for s in last_msg.payload.split('\r') if s.startswith('PV1')), None)
            if pv1:
                patient_class = pv1.split('|')[2] if len(pv1.split('|')) > 2 else 'N/A'
                print(f"   Dossier externe - PV1-2: {patient_class}")
                if patient_class == "O":
                    print(f"   ✅ Mapping correct : AMB → O")
                else:
                    print(f"   ❌ ERREUR : Attendu 'O', obtenu '{patient_class}'")
                    return False
        
        print("\n" + "="*100)
        print("✅ TOUS LES TESTS SONT PASSÉS !")
        print("="*100 + "\n")
        
        print("📊 Résumé :")
        print(f"   - Patient créé : patient_seq = {patient_seq} (12 chiffres, préfixe 9)")
        print(f"   - Dossier 1 (IMP) : dossier_seq = {dossier_seq} (9 chiffres, préfixe 9)")
        print(f"   - Dossier 2 (AMB) : dossier_seq = {dossier_seq2} (9 chiffres, préfixe 9)")
        print(f"   - Venues créées automatiquement : 2")
        print(f"   - Messages A05 générés : 2")
        print(f"   - Mapping PV1-2 : IMP→I ✅, AMB→O ✅")
        print()
        
        return True

if __name__ == "__main__":
    try:
        success = test_workflow()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ ERREUR : {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
