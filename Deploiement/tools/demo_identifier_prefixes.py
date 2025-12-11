#!/usr/bin/env python3
"""
Script de démonstration: Génération d'identifiants avec préfixes pour scénarios IHE.

Ce script montre comment:
1. Afficher les patterns de préfixe disponibles
2. Générer des identifiants selon différents patterns
3. Montrer le remplacement dans un message HL7 (simulation)
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


# Message HL7 d'exemple (ADT A04 - Admission)
SAMPLE_HL7_MESSAGE = """MSH|^~\\&|CPAGE|CPAGE|ANTARES|ANTARES|20250513081608||ADT^A04^ADT_A01|1000467197|P|2.5^FRA^2.4|||||FRA|8859/1
EVN||20250513081608|||int^ADMIN^ADM INTER^^^^^^CPAGE&1.2.250.1.154&ISO|20250513081608
PID|||123456^^^HOSP^PI~789012^^^INS-NIR^NH||MARTIN^Jean^Pierre||19800115|M|||12 rue de la Paix^^Paris^^75001^FR
PV1||I|CARDIO^101^01^HOSP||||||||||||||||654321^^^HOSP^VN|||||||||||||||||||||||||20250513081500"""


def demo_prefix_configuration():
    """Démontre la configuration des préfixes dans les namespaces."""
    print("=" * 80)
    print("1. CONFIGURATION DES PRÉFIXES DANS LES NAMESPACES")
    print("=" * 80)
    
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    
    with Session(engine) as session:
        # Créer GHT de test
        ght = GHTContext(name="GHT Demo", code="DEMO", is_active=True)
        session.add(ght)
        session.commit()
        session.refresh(ght)
        
        # Namespace IPP avec préfixe "9..." (plage 9000-9999)
        ipp_ns = IdentifierNamespace(
            name="IPP Test",
            system="urn:oid:1.2.250.1.213.1.1.1",
            type="IPP",
            description="IPP pour tests avec préfixe 9",
            prefix_pattern="9...",
            prefix_mode="fixed",
            ght_context_id=ght.id
        )
        
        # Namespace NDA avec plage numérique 501000-501999
        nda_ns = IdentifierNamespace(
            name="NDA Test",
            system="urn:oid:1.2.250.1.213.1.1.2",
            type="NDA",
            description="NDA pour tests avec plage 501xxx",
            prefix_mode="range",
            prefix_min=501000,
            prefix_max=501999,
            ght_context_id=ght.id
        )
        
        session.add_all([ipp_ns, nda_ns])
        session.commit()
        session.refresh(ipp_ns)
        session.refresh(nda_ns)
        
        print(f"\n✅ Namespace IPP créé:")
        print(f"   - Nom: {ipp_ns.name}")
        print(f"   - Pattern: {ipp_ns.prefix_pattern}")
        print(f"   - Identifiants disponibles: {count_available_identifiers(ipp_ns)}")
        
        print(f"\n✅ Namespace NDA créé:")
        print(f"   - Nom: {nda_ns.name}")
        print(f"   - Plage: {nda_ns.prefix_min} - {nda_ns.prefix_max}")
        print(f"   - Identifiants disponibles: {count_available_identifiers(nda_ns)}")
        
        return session, ipp_ns, nda_ns


def demo_identifier_generation(session, ipp_ns, nda_ns):
    """Démontre la génération d'identifiants avec préfixes."""
    print("\n" + "=" * 80)
    print("2. GÉNÉRATION D'IDENTIFIANTS AVEC PRÉFIXES")
    print("=" * 80)
    
    # Générer 5 ensembles d'identifiants
    print("\n📋 Génération de 5 ensembles IPP/NDA:")
    for i in range(5):
        ids = generate_identifier_set(
            session=session,
            ipp_namespace=ipp_ns,
            nda_namespace=nda_ns
        )
        print(f"   #{i+1}: IPP={ids['ipp']}, NDA={ids['nda']}")
    
    # Générer avec override de préfixe
    print("\n📋 Génération avec override de préfixe (91....):")
    ids_override = generate_identifier_set(
        session=session,
        ipp_namespace=ipp_ns,
        nda_namespace=nda_ns,
        ipp_prefix_override="91....",
        nda_prefix_override="502..."
    )
    print(f"   IPP={ids_override['ipp']}, NDA={ids_override['nda']}")
    
    return ids


def demo_message_replacement(session, ipp_ns, nda_ns):
    """Démontre le remplacement d'identifiants dans un message HL7."""
    print("\n" + "=" * 80)
    print("3. REMPLACEMENT DES IDENTIFIANTS DANS MESSAGE HL7")
    print("=" * 80)
    
    # Aperçu avant remplacement
    print("\n🔍 Aperçu des identifiants qui seront générés:")
    preview = preview_identifier_replacement(
        message=SAMPLE_HL7_MESSAGE,
        session=session,
        ipp_namespace=ipp_ns,
        nda_namespace=nda_ns
    )
    
    print(f"\n   Identifiants générés:")
    print(f"   - IPP: {preview['generated_ids']['ipp']} (pattern: {preview['namespaces']['ipp']['pattern']})")
    print(f"   - NDA: {preview['generated_ids']['nda']} (pattern: {preview['namespaces']['nda']['pattern']})")
    
    print(f"\n   PID-3 original: {preview['original_pid3']}")
    print(f"   PID-3 nouveau:  {preview['new_pid3']}")
    
    print(f"\n   PV1-19 original: {preview['original_pv1_19']}")
    print(f"   PV1-19 nouveau:  {preview['new_pv1_19']}")
    
    # Remplacement effectif
    print("\n🔄 Remplacement des identifiants dans le message...")
    modified_msg, generated_ids = replace_identifiers_in_hl7_message(
        message=SAMPLE_HL7_MESSAGE,
        session=session,
        ipp_namespace=ipp_ns,
        nda_namespace=nda_ns
    )
    
    print("\n✅ Message modifié:")
    print("-" * 80)
    for line in modified_msg.split('\r'):
        if line.startswith(('PID', 'PV1')):
            print(f"   {line}")
    print("-" * 80)
    
    print(f"\n   Identifiants utilisés: IPP={generated_ids['ipp']}, NDA={generated_ids['nda']}")


def demo_collision_avoidance(session, ipp_ns):
    """Démontre l'évitement de collisions."""
    print("\n" + "=" * 80)
    print("4. ÉVITEMENT DE COLLISIONS")
    print("=" * 80)
    
    # Créer un identifiant existant
    existing_ipp = "9123"
    existing_ident = Identifier(
        value=existing_ipp,
        type=IdentifierType.IPP,
        system=ipp_ns.system,
        status="active"
    )
    session.add(existing_ident)
    session.commit()
    
    print(f"\n📌 Identifiant existant créé: {existing_ipp}")
    print(f"\n🔄 Génération de 20 nouveaux identifiants...")
    
    generated = set()
    for _ in range(20):
        from app.services.identifier_generator import generate_identifier
        ident = generate_identifier(
            session=session,
            namespace=ipp_ns,
            identifier_type=IdentifierType.IPP
        )
        generated.add(ident)
    
    print(f"\n✅ {len(generated)} identifiants uniques générés")
    print(f"   Exemples: {', '.join(list(generated)[:10])}")
    
    if existing_ipp in generated:
        print(f"\n❌ ERREUR: Collision détectée avec {existing_ipp}")
    else:
        print(f"\n✅ Aucune collision avec {existing_ipp}")


def main():
    """Point d'entrée principal."""
    print("\n" + "=" * 80)
    print("DÉMONSTRATION: GÉNÉRATION D'IDENTIFIANTS AVEC PRÉFIXES POUR SCÉNARIOS IHE")
    print("=" * 80)
    
    try:
        # 1. Configuration
        session, ipp_ns, nda_ns = demo_prefix_configuration()
        
        # 2. Génération
        ids = demo_identifier_generation(session, ipp_ns, nda_ns)
        
        # 3. Remplacement dans message
        demo_message_replacement(session, ipp_ns, nda_ns)
        
        # 4. Évitement de collisions
        demo_collision_avoidance(session, ipp_ns)
        
        print("\n" + "=" * 80)
        print("✅ DÉMONSTRATION TERMINÉE AVEC SUCCÈS")
        print("=" * 80)
        print("\nPour utiliser cette fonctionnalité:")
        print("1. Configurez les préfixes dans les namespaces via l'UI /admin/ght/{id}/namespaces")
        print("2. Lors de l'exécution d'un scénario, spécifiez les préfixes IPP/NDA")
        print("3. Les identifiants seront générés automatiquement et remplacés dans les messages")
        print("4. La traçabilité est conservée dans ScenarioBinding.generated_ipp/nda")
        print()
        
    except Exception as e:
        print(f"\n❌ ERREUR: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
