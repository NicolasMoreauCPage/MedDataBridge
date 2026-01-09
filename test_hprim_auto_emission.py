#!/usr/bin/env python3
"""
Script de test pour vérifier l'auto-émission HPRIM des cotations.

Usage:
    .venv/bin/python3 test_hprim_auto_emission.py
"""
from datetime import datetime
from sqlmodel import Session, select
from app.db import engine
from app.models import CCAMAct, NGAPAct, Dossier, Patient
from app.models_endpoints import SystemEndpoint, MessageLog

def test_hprim_auto_emission():
    """Vérifie que les endpoints HPRIM sont configurés et prêts."""
    with Session(engine) as session:
        # 1. Vérifier s'il existe des endpoints HPRIM
        hprim_endpoints = session.exec(
            select(SystemEndpoint)
            .where(SystemEndpoint.kind == "HPRIM")
            .where(SystemEndpoint.is_enabled == True)
        ).all()
        
        print(f"📡 Endpoints HPRIM configurés: {len(hprim_endpoints)}")
        for ep in hprim_endpoints:
            role = ep.role or "unknown"
            print(f"   - ID {ep.id}: {ep.name} (role={role}, host={ep.host})")
        
        if not hprim_endpoints:
            print("⚠️  Aucun endpoint HPRIM configuré. L'auto-émission ne se déclenchera pas.")
            print("   Pour tester, créez un endpoint HPRIM avec role='sender' ou 'both'")
            return
        
        # 2. Vérifier qu'il existe des dossiers avec actes
        dossiers_with_acts = session.exec(
            select(Dossier)
            .join(CCAMAct, CCAMAct.dossier_id == Dossier.id, isouter=True)
            .where(CCAMAct.id.isnot(None))
        ).all()
        
        print(f"\n📋 Dossiers avec actes CCAM: {len(dossiers_with_acts)}")
        
        # 3. Vérifier les messages HPRIM émis
        hprim_messages = session.exec(
            select(MessageLog)
            .where(MessageLog.entity_type.in_(["ccam_act", "ngap_act", "ucd_act", "lpp_act"]))
            .order_by(MessageLog.created_at.desc())
        ).all()
        
        print(f"\n📨 Messages HPRIM cotation émis: {len(hprim_messages)}")
        for msg in hprim_messages[:5]:  # Afficher les 5 derniers
            status_icon = "✅" if msg.status == "sent" else "⏳" if msg.status == "pending" else "❌"
            print(f"   {status_icon} {msg.entity_type} ID={msg.entity_id} | Status={msg.status} | Endpoint={msg.endpoint_id}")
        
        if not hprim_messages:
            print("   ℹ️  Aucun message HPRIM émis pour le moment.")
            print("   Créez un acte CCAM/NGAP via /cotations/api/ccam ou /cotations/api/ngap")
        
        print("\n" + "="*60)
        print("✅ Configuration HPRIM auto-émission vérifiée")
        print("="*60)
        print("\nÉtapes suivantes:")
        print("1. Assurez-vous qu'un endpoint HPRIM est configuré (role='sender')")
        print("2. Créez un acte via l'interface de cotation")
        print("3. Vérifiez les logs pour voir l'auto-émission:")
        print("   tail -f logs/app.log | grep HPRIM")
        print("4. Consultez la table MessageLog pour voir les messages émis")

if __name__ == "__main__":
    test_hprim_auto_emission()
