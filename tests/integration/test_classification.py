#!/usr/bin/env python3
"""Test de la classification des identifiants"""
import pytest
import sys
sys.path.insert(0, '.')

# Import all models to resolve relationships
from app.models import *
from app.db import get_session, session_factory
from app.services.identifier_namespace_classifier import classify_incoming_identifiers
from app.models_identifiers import IdentifierType


def test_classify_incoming_identifiers():
    """Test de classification des identifiants entrants"""
    with session_factory() as session:

        # Simuler des identifiants reçus dans un message HL7
        identifiers_data = [
            ("900006654054", "CPAGE", IdentifierType.IPP),           # Devrait être INTERNE
            ("212017231012386", "ASIP-SANTE-NIR", IdentifierType.NDA), # Devrait être EXTERNE
        ]

        print("=== TEST DE CLASSIFICATION ===\n")
        print("Identifiants reçus:")
        for value, system, id_type in identifiers_data:
            print(f"  - {value} (system={system}, type={id_type.value})")

        print("\n--- Classification pour EJ 1 (CHU Lyon) ---\n")

        result = classify_incoming_identifiers(
            session=session,
            identifiers_data=identifiers_data,
            entity_type='patient',
            ej_id=1
        )

        print(f"✅ main_identifier: {result.get('main_identifier')}")
        print(f"📝 external_id: {result.get('external_id')}")
        print(f"\n🔑 external_identifiers:")
        for ext_id in result.get('external_identifiers', []):
            print(f"  - {ext_id['value']} (system={ext_id['system']}, type={ext_id['type'].value})")

        print("\n--- Interprétation ---\n")
        if result.get('main_identifier'):
            print(f"✅ L'identifiant CPAGE {result.get('main_identifier')} sera utilisé comme patient.identifier")
        else:
            print("⚠️ Aucun identifiant interne trouvé, un ID sera généré")

        if result.get('external_identifiers'):
            print(f"📦 {len(result.get('external_identifiers'))} identifiant(s) externe(s) seront stockés dans la table identifier")

    # Basic assertions
    assert result is not None
    assert 'main_identifier' in result
    assert 'external_identifiers' in result
