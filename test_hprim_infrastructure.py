#!/usr/bin/env python3
"""
Test rapide de l'infrastructure HPRIM
Vérification que les services se chargent correctement
"""

import sys
import os
from datetime import datetime
from decimal import Decimal

# Activer l'environnement virtuel
venv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.venv', 'bin', 'activate_this.py')
if os.path.exists(venv_path):
    with open(venv_path) as f:
        exec(f.read(), {'__file__': venv_path})

# Ajouter le répertoire courant au path pour les imports
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

try:
    # Test d'import des modèles
    from app.models.hprim_models import (
        HprimMessage, HprimEnteteMessage, HprimPatient, HprimProfessionnel,
        HprimActeCCAM, HprimMessageType, HprimAction, HprimMontant, HprimModificateur
    )
    print("✅ Modèles HPRIM importés avec succès")

    # Test d'import des services
    from app.services.hprim import HprimService, HprimValidator, HprimXmlService
    print("✅ Services HPRIM importés avec succès")

    # Test de création d'un acte CCAM simple
    service = HprimService()
    print("✅ Service HPRIM instancié")

    # Créer un acte de test
    acte = service.creer_acte_ccam_simple(
        code_acte="AAFA001",
        code_activite="01",
        code_phase="00",
        executant_rpps="12345678901",
        date_execution=datetime.now(),
        quantite=1,
        modificateurs=["K"],
        montant=25.50
    )
    print("✅ Acte CCAM créé avec succès")
    print(f"   - Code: {acte.code_acte}")
    print(f"   - Modificateurs: {[m.code for m in acte.modificateurs]}")
    print(f"   - Montant: {acte.montant.valeur if acte.montant else 'N/A'} €")

    # Créer un patient de test
    patient = HprimPatient(
        identifiant_id="123456789",
        identifiant_clef="123456789",
        nom="DUPONT",
        prenom="JEAN",
        date_naissance="1980-01-01"
    )
    print("✅ Patient créé")

    # Créer un professionnel de test
    medecin = HprimProfessionnel(
        nom="MARTIN",
        prenom="PIERRE",
        numero_rpps="12345678901",
        specialite="Médecine générale"
    )
    print("✅ Professionnel créé")

    # Créer un message complet
    message = service.creer_message_actes_ccam(
        emetteur_id="FINESS_123456789",
        emetteur_nom="EHPAD LES ROSIERS",
        destinataire_id="FINESS_987654321",
        destinataire_nom="CENTRE HOSPITALIER",
        patient=patient,
        acteur=medecin,
        actes=[acte]
    )
    print("✅ Message HPRIM créé")

    # Valider le message
    erreurs = service.valider_message(message)
    if erreurs:
        print(f"❌ Erreurs de validation: {len(erreurs)}")
        for err in erreurs[:3]:  # Afficher max 3 erreurs
            print(f"   - {err.code}: {err.message}")
    else:
        print("✅ Message validé sans erreur")

    # Générer le XML
    try:
        xml_output = service.generer_xml(message, valider=False)
        print("✅ XML généré avec succès")
        print(f"   - Taille: {len(xml_output)} caractères")
        print(f"   - Contient 'evenementsServeurActes': {'evenementsServeurActes' in xml_output}")
        print(f"   - Contient code acte: {'AAFA001' in xml_output}")

        # Aperçu du XML (premières lignes)
        lines = xml_output.split('\n')[:10]
        print("   - Aperçu:")
        for line in lines:
            if line.strip():
                print(f"     {line}")

    except Exception as e:
        print(f"❌ Erreur génération XML: {e}")

    print("\n🎉 Test d'infrastructure HPRIM terminé avec succès !")

except ImportError as e:
    print(f"❌ Erreur d'import: {e}")
    sys.exit(1)
except Exception as e:
    print(f"❌ Erreur inattendue: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)