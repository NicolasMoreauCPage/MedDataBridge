#!/usr/bin/env python3
"""
Script rapide pour voir les derniers messages créés
Usage: python check_last_messages.py [nombre]
"""

import sys
from sqlmodel import Session, select
from app.db import engine
from app.models_shared import MessageLog

def main():
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    
    print(f"\n{'='*100}")
    print(f"📨 LES {limit} DERNIERS MESSAGES")
    print(f"{'='*100}\n")
    
    with Session(engine) as session:
        messages = session.exec(
            select(MessageLog)
            .order_by(MessageLog.created_at.desc())
            .limit(limit)
        ).all()
        
        if not messages:
            print("⚠️  Aucun message trouvé")
            return
        
        for i, msg in enumerate(messages, 1):
            print(f"\n{'─'*100}")
            print(f"📋 Message #{i} (ID={msg.id})")
            print(f"{'─'*100}")
            print(f"⏰ Date:      {msg.created_at}")
            print(f"📡 Type:      {msg.kind}")
            print(f"🔀 Direction: {msg.direction}")
            print(f"✅ Status:    {msg.status}")
            
            if msg.kind == 'MLLP' and msg.payload:
                segments = msg.payload.split('\r')
                
                # MSH - Message Header
                msh = next((s for s in segments if s.startswith('MSH')), None)
                if msh:
                    fields = msh.split('|')
                    msg_type = fields[8] if len(fields) > 8 else 'N/A'
                    print(f"📨 Type msg:  {msg_type}")
                
                # PID - Patient Identification
                pid = next((s for s in segments if s.startswith('PID')), None)
                if pid:
                    fields = pid.split('|')
                    patient_id = fields[3] if len(fields) > 3 else 'N/A'
                    patient_name = fields[5] if len(fields) > 5 else 'N/A'
                    sex = fields[8] if len(fields) > 8 else 'N/A'
                    print(f"👤 Patient:   {patient_name} (ID: {patient_id}, Sexe: {sex})")
                
                # PV1 - Patient Visit
                pv1 = next((s for s in segments if s.startswith('PV1')), None)
                if pv1:
                    fields = pv1.split('|')
                    patient_class = fields[2] if len(fields) > 2 else 'N/A'
                    visit_number = fields[19] if len(fields) > 19 else 'N/A'
                    location = fields[3] if len(fields) > 3 else 'N/A'
                    print(f"🏥 PV1-2:     {patient_class} {'✅ (I/O/E)' if patient_class in ['I', 'O', 'E'] else '❌ (invalide)'}")
                    print(f"🔢 NDA:       {visit_number}")
                    print(f"📍 Location:  {location}")
                
                # ZBE - Mouvement
                zbe = next((s for s in segments if s.startswith('ZBE')), None)
                if zbe:
                    fields = zbe.split('|')
                    mvt_id = fields[1] if len(fields) > 1 else 'N/A'
                    print(f"🔄 Mouvement:  {mvt_id}")
            
            elif msg.kind == 'FHIR' and msg.payload:
                try:
                    import json
                    data = json.loads(msg.payload)
                    if data:
                        resource_type = data.get('resourceType', 'N/A')
                        print(f"🔷 FHIR:      {resource_type}")
                        
                        if resource_type == 'Bundle':
                            entries = data.get('entry', [])
                            print(f"📦 Entries:   {len(entries)} ressources")
                            for entry in entries[:3]:  # 3 premières
                                res = entry.get('resource', {})
                                res_type = res.get('resourceType', '?')
                                print(f"   └─ {res_type}")
                except:
                    print("⚠️  Erreur parsing FHIR")
        
        print(f"\n{'='*100}\n")
        
        # Statistiques
        hl7_count = sum(1 for m in messages if m.kind == 'MLLP')
        fhir_count = sum(1 for m in messages if m.kind == 'FHIR')
        
        print(f"📊 Statistiques:")
        print(f"   HL7:  {hl7_count} messages")
        print(f"   FHIR: {fhir_count} messages")
        print()

if __name__ == '__main__':
    main()
