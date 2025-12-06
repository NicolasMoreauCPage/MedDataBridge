#!/usr/bin/env python3
"""Créer un endpoint FILE dans l'EJ 5 pour importer les messages IHE PAM de test.

Configure un endpoint de type FILE pointant vers tests/exemples/Fichier_test_pam/
pour permettre l'intégration automatique des messages IHE PAM.
"""
import sys
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db import session_factory
from app.models_shared import SystemEndpoint, EndpointKind, EndpointRole
from app.models_structure import EntiteJuridique
from sqlmodel import select

PAM_DIR = ROOT / "tests" / "exemples" / "Fichier_test_pam"
EJ_ID = 5


def main():
    print("=== Création Endpoint FILE pour EJ 5 ===\n")
    
    with session_factory() as session:
        # Vérifier que l'EJ 5 existe
        ej = session.get(EntiteJuridique, EJ_ID)
        if not ej:
            print(f"❌ EJ avec id={EJ_ID} introuvable")
            return 1
        
        print(f"✓ EJ trouvée: {ej.name} (FINESS: {ej.finess_ej})")
        
        # Vérifier le dossier de messages
        if not PAM_DIR.exists():
            print(f"⚠️  Dossier introuvable: {PAM_DIR}")
            return 1
        
        # Compter les fichiers HL7
        hl7_files = list(PAM_DIR.glob("*.hl7"))
        print(f"✓ Dossier trouvé: {PAM_DIR}")
        print(f"  Contient {len(hl7_files)} fichiers .hl7\n")
        
        # Vérifier si un endpoint FILE existe déjà pour cette EJ
        existing = session.exec(
            select(SystemEndpoint)
            .where(SystemEndpoint.entite_juridique_id == EJ_ID)
            .where(SystemEndpoint.kind == EndpointKind.FILE)
        ).first()
        
        if existing:
            print(f"⚠️  Endpoint FILE existant trouvé: {existing.name}")
            response = input("Voulez-vous le remplacer ? (o/N) ")
            if response.lower() != 'o':
                print("Annulé.")
                return 0
            session.delete(existing)
            session.commit()
            print(f"  ✓ Endpoint existant supprimé\n")
        
        # Créer le nouvel endpoint FILE
        endpoint = SystemEndpoint(
            name=f"IHE PAM FILE Import - {ej.short_name}",
            kind=EndpointKind.FILE,
            role=EndpointRole.RECEIVER,
            is_enabled=True,
            entite_juridique_id=ej.id,
            ght_context_id=ej.ght_context_id,
            inbox_path=str(PAM_DIR.absolute()),
            outbox_path=str((PAM_DIR.parent / "pam_export").absolute()),
            archive_path=str((PAM_DIR.parent / "pam_archive").absolute()),
            error_path=str((PAM_DIR.parent / "pam_errors").absolute()),
            file_extensions=".hl7",
        )
        
        session.add(endpoint)
        session.commit()
        session.refresh(endpoint)
        
        print(f"✅ Endpoint créé avec succès!")
        print(f"\n📋 Configuration:")
        print(f"  - ID: {endpoint.id}")
        print(f"  - Nom: {endpoint.name}")
        print(f"  - Type: {endpoint.kind}")
        print(f"  - Rôle: {endpoint.role}")
        print(f"  - EJ: {ej.name} (id={ej.id})")
        print(f"  - Inbox: {endpoint.inbox_path}")
        print(f"  - Outbox: {endpoint.outbox_path}")
        print(f"  - Archive: {endpoint.archive_path}")
        print(f"  - Erreurs: {endpoint.error_path}")
        print(f"  - Extensions: {endpoint.file_extensions}")
        
        print(f"\n💡 Pour activer le polling:")
        print(f"  - Le service FilePollerService doit être démarré")
        print(f"  - Les messages seront automatiquement importés depuis {PAM_DIR}")
        print(f"  - Les messages traités seront archivés")
        
        return 0


if __name__ == "__main__":
    sys.exit(main())
