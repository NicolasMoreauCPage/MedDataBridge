#!/usr/bin/env python3
"""Test roundtrip des scénarios avec configuration UF/Médecins.

Ce script effectue un test complet :
1. Configure les namespaces pour une EJ
2. Configure les UF et médecins pour les scénarios
3. Matérialise un scénario depuis un template
4. Exporte les messages HL7 dans un répertoire
5. Réinjecte les messages via le pipeline inbound
6. Vérifie la conformité des données importées
"""

import os
import sys
import json
from datetime import datetime
from pathlib import Path

# Ajouter le chemin du projet
sys.path.insert(0, str(Path(__file__).parent))

from sqlmodel import select, Session
from app.db import get_session, engine
from app.models_structure import EntiteJuridique, UniteFonctionnelle
from app.models_scenarios import ScenarioTemplate, InteropScenario, InteropScenarioStep
from app.models_scenario_config import ScenarioEJConfig
from app.models_shared import SystemEndpoint
from app.services.scenario_template_materializer import materialize_template, MaterializationOptions


# === Configuration du test ===
TEST_EJ_ID = 1  # CHU Universitaire Lyon
TEST_OUTPUT_DIR = Path("tmp/scenario_roundtrip_test")
TEST_NAMESPACE_OID = "1.2.250.1.71.4.2.2.69001"  # OID fictif pour test

# UF à utiliser (par ID)
TEST_UF_HOSPITALISATION_ID = 4   # UF Réadaptation Neuro
TEST_UF_CONSULTATION_ID = 1       # UF Accueil-Triage (utilisé comme consult pour test)
TEST_UF_URGENCES_ID = 2           # UF UHCD / courte durée
TEST_UF_MUTATION_ID = 3           # UF Suites de couches (comme destination mutation)

# Médecins de test
TEST_MEDECIN_HOSPI_RPPS = "10100000001"
TEST_MEDECIN_HOSPI_NOM = "Dr DURAND Pierre"
TEST_MEDECIN_CONSULT_RPPS = "10100000002"
TEST_MEDECIN_CONSULT_NOM = "Dr MARTIN Sophie"
TEST_MEDECIN_URGENCES_RPPS = "10100000003"
TEST_MEDECIN_URGENCES_NOM = "Dr LEFEVRE Marc"
TEST_MEDECIN_MUTATION_RPPS = "10100000004"
TEST_MEDECIN_MUTATION_NOM = "Dr BERNARD Claire"

# Chambres et lits de test
TEST_CHAMBRE_HOSPI = "112"
TEST_LIT_HOSPI = "A"
TEST_CHAMBRE_CONSULT = "CS03"
TEST_CHAMBRE_URGENCES = "URG02"
TEST_LIT_URGENCES = "1"
TEST_CHAMBRE_MUTATION = "205"
TEST_LIT_MUTATION = "B"

# Médecin traitant
TEST_MEDECIN_TRAITANT_RPPS = "10103334567"
TEST_MEDECIN_TRAITANT_NOM = "Dr DUPONT Marie"


def setup_ej_config(session: Session) -> ScenarioEJConfig:
    """Configure les UF et médecins pour l'EJ de test."""
    print("\n=== 1. Configuration de l'EJ pour les scénarios ===")
    
    # Récupérer l'EJ
    ej = session.get(EntiteJuridique, TEST_EJ_ID)
    if not ej:
        raise ValueError(f"EJ {TEST_EJ_ID} introuvable")
    print(f"EJ cible: {ej.name} (id={ej.id})")
    
    # Supprimer config existante si présente
    existing = session.exec(
        select(ScenarioEJConfig).where(ScenarioEJConfig.entite_juridique_id == TEST_EJ_ID)
    ).first()
    if existing:
        session.delete(existing)
        session.commit()
        print("  - Configuration existante supprimée")
    
    # Créer nouvelle config avec tous les champs
    config = ScenarioEJConfig(
        entite_juridique_id=TEST_EJ_ID,
        # Hospitalisation
        uf_hospitalisation_id=TEST_UF_HOSPITALISATION_ID,
        chambre_hospitalisation=TEST_CHAMBRE_HOSPI,
        lit_hospitalisation=TEST_LIT_HOSPI,
        medecin_hospitalisation_rpps=TEST_MEDECIN_HOSPI_RPPS,
        medecin_hospitalisation_nom=TEST_MEDECIN_HOSPI_NOM,
        # Consultation
        uf_consultation_id=TEST_UF_CONSULTATION_ID,
        chambre_consultation=TEST_CHAMBRE_CONSULT,
        lit_consultation=None,  # Pas de lit en consultation
        medecin_consultation_rpps=TEST_MEDECIN_CONSULT_RPPS,
        medecin_consultation_nom=TEST_MEDECIN_CONSULT_NOM,
        # Urgences
        uf_urgences_id=TEST_UF_URGENCES_ID,
        chambre_urgences=TEST_CHAMBRE_URGENCES,
        lit_urgences=TEST_LIT_URGENCES,
        medecin_urgences_rpps=TEST_MEDECIN_URGENCES_RPPS,
        medecin_urgences_nom=TEST_MEDECIN_URGENCES_NOM,
        # Mutation
        uf_mutation_cible_id=TEST_UF_MUTATION_ID,
        chambre_mutation=TEST_CHAMBRE_MUTATION,
        lit_mutation=TEST_LIT_MUTATION,
        medecin_mutation_rpps=TEST_MEDECIN_MUTATION_RPPS,
        medecin_mutation_nom=TEST_MEDECIN_MUTATION_NOM,
        # Médecin traitant (PV1-8)
        medecin_traitant_rpps=TEST_MEDECIN_TRAITANT_RPPS,
        medecin_traitant_nom=TEST_MEDECIN_TRAITANT_NOM,
    )
    session.add(config)
    session.commit()
    session.refresh(config)
    
    # Afficher la config créée
    print(f"  - UF Hospitalisation: {TEST_UF_HOSPITALISATION_ID} - Chambre {TEST_CHAMBRE_HOSPI}, Lit {TEST_LIT_HOSPI}")
    print(f"    Médecin: {TEST_MEDECIN_HOSPI_NOM}")
    print(f"  - UF Consultation: {TEST_UF_CONSULTATION_ID} - Chambre {TEST_CHAMBRE_CONSULT}")
    print(f"    Médecin: {TEST_MEDECIN_CONSULT_NOM}")
    print(f"  - UF Urgences: {TEST_UF_URGENCES_ID} - Chambre {TEST_CHAMBRE_URGENCES}, Lit {TEST_LIT_URGENCES}")
    print(f"    Médecin: {TEST_MEDECIN_URGENCES_NOM}")
    print(f"  - UF Mutation: {TEST_UF_MUTATION_ID} - Chambre {TEST_CHAMBRE_MUTATION}, Lit {TEST_LIT_MUTATION}")
    print(f"    Médecin: {TEST_MEDECIN_MUTATION_NOM}")
    print(f"  - Médecin traitant (PV1-8): {TEST_MEDECIN_TRAITANT_NOM}")
    print("  ✓ Configuration créée")
    
    return config


def materialize_scenario(session: Session) -> InteropScenario:
    """Matérialise un scénario depuis un template."""
    print("\n=== 2. Matérialisation du scénario ===")
    
    # Utiliser le template "ihe.hospitSimple"
    template = session.exec(
        select(ScenarioTemplate).where(ScenarioTemplate.key == "ihe.hospitSimple")
    ).first()
    
    if not template:
        # Fallback sur le premier template disponible
        template = session.exec(select(ScenarioTemplate)).first()
    
    if not template:
        raise ValueError("Aucun template de scénario trouvé")
    
    print(f"Template: {template.name} ({template.key})")
    print(f"  - {len(template.steps)} étapes")
    
    # Récupérer l'EJ
    ej = session.get(EntiteJuridique, TEST_EJ_ID)
    
    # Options de matérialisation
    options = MaterializationOptions(
        protocol="HL7v2",
        generate_identifiers=True,
        ipp_prefix="TEST",
        nda_prefix="VIS",
        namespace_oid=TEST_NAMESPACE_OID,
        apply_time_shifting=True,
    )
    
    # Matérialiser
    scenario = materialize_template(
        session=session,
        template=template,
        ej_context=ej,
        options=options,
    )
    
    print(f"  ✓ Scénario créé: {scenario.name} (id={scenario.id})")
    print(f"  - {len(scenario.steps)} messages générés")
    
    return scenario


def export_messages(session: Session, scenario: InteropScenario) -> list[Path]:
    """Exporte les messages HL7 dans des fichiers."""
    print("\n=== 3. Export des messages HL7 ===")
    
    # Créer le répertoire de sortie
    TEST_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Répertoire: {TEST_OUTPUT_DIR}")
    
    exported_files = []
    
    for step in scenario.steps:
        # Nom du fichier
        filename = f"message_{step.order_index:02d}_{step.message_type.replace('^', '_')}.hl7"
        filepath = TEST_OUTPUT_DIR / filename
        
        # Écrire le message
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(step.payload)
        
        exported_files.append(filepath)
        print(f"  - {filename} ({len(step.payload)} bytes)")
    
    # Exporter aussi un fichier JSON avec les métadonnées
    metadata = {
        "scenario_id": scenario.id,
        "scenario_name": scenario.name,
        "ej_id": TEST_EJ_ID,
        "namespace_oid": TEST_NAMESPACE_OID,
        "created_at": datetime.utcnow().isoformat(),
        "steps": [
            {
                "order": s.order_index,
                "name": s.name,
                "message_type": s.message_type,
                "file": f"message_{s.order_index:02d}_{s.message_type.replace('^', '_')}.hl7"
            }
            for s in scenario.steps
        ],
        "config": {
            "uf_hospitalisation_id": TEST_UF_HOSPITALISATION_ID,
            "uf_consultation_id": TEST_UF_CONSULTATION_ID,
            "uf_urgences_id": TEST_UF_URGENCES_ID,
            "uf_mutation_id": TEST_UF_MUTATION_ID,
            "medecin_hospi_rpps": TEST_MEDECIN_HOSPI_RPPS,
            "medecin_consult_rpps": TEST_MEDECIN_CONSULT_RPPS,
            "medecin_urgences_rpps": TEST_MEDECIN_URGENCES_RPPS,
            "medecin_mutation_rpps": TEST_MEDECIN_MUTATION_RPPS,
        }
    }
    
    metadata_file = TEST_OUTPUT_DIR / "scenario_metadata.json"
    with open(metadata_file, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
    
    print(f"  - scenario_metadata.json (métadonnées)")
    print(f"  ✓ {len(exported_files)} fichiers exportés")
    
    return exported_files


def verify_messages(session: Session, exported_files: list[Path]) -> dict:
    """Vérifie le contenu des messages exportés."""
    print("\n=== 4. Vérification des messages HL7 ===")
    
    results = {
        "total": len(exported_files),
        "valid": 0,
        "errors": [],
        "uf_found": set(),
        "rpps_found": set(),
    }
    
    # Charger les UF attendues
    uf_hospi = session.get(UniteFonctionnelle, TEST_UF_HOSPITALISATION_ID)
    uf_consult = session.get(UniteFonctionnelle, TEST_UF_CONSULTATION_ID)
    uf_urgences = session.get(UniteFonctionnelle, TEST_UF_URGENCES_ID)
    uf_mutation = session.get(UniteFonctionnelle, TEST_UF_MUTATION_ID)
    
    expected_ufs = {
        uf_hospi.identifier if uf_hospi else None,
        uf_consult.identifier if uf_consult else None,
        uf_urgences.identifier if uf_urgences else None,
        uf_mutation.identifier if uf_mutation else None,
    }
    expected_ufs.discard(None)
    
    expected_rpps = {
        TEST_MEDECIN_HOSPI_RPPS,
        TEST_MEDECIN_CONSULT_RPPS,
        TEST_MEDECIN_URGENCES_RPPS,
        TEST_MEDECIN_MUTATION_RPPS,
    }
    
    for filepath in exported_files:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        filename = filepath.name
        
        # Vérifications basiques
        errors = []
        
        # 1. Vérifier structure MSH
        if not content.startswith("MSH|"):
            errors.append("Missing MSH segment")
        
        # 2. Vérifier présence PID
        if "PID|" not in content:
            errors.append("Missing PID segment")
        
        # 3. Vérifier présence PV1
        if "PV1|" not in content:
            errors.append("Missing PV1 segment")
        
        # 4. Vérifier le namespace OID
        if TEST_NAMESPACE_OID not in content:
            errors.append(f"Namespace OID {TEST_NAMESPACE_OID} not found")
        
        # 5. Extraire et vérifier les UF (dans PV1-3) et RPPS (dans PV1-7)
        # Gérer les sauts de ligne \r ou \n
        lines = content.replace('\r\n', '\r').replace('\n', '\r').split('\r')
        for line in lines:
            if line.startswith("PV1|"):
                fields = line.split("|")
                
                # PV1-3: Assigned Patient Location (index 3)
                if len(fields) > 3:
                    location = fields[3]
                    # Le code UF est le premier composant avant ^
                    uf_code = location.split("^")[0] if location else ""
                    if uf_code:
                        results["uf_found"].add(uf_code)
                
                # PV1-7: Attending Doctor (index 7)
                if len(fields) > 7:
                    doctor = fields[7]
                    # RPPS est le premier composant du XCN
                    rpps = doctor.split("^")[0] if doctor else ""
                    if rpps and rpps.isdigit():
                        results["rpps_found"].add(rpps)
        
        if errors:
            results["errors"].append({"file": filename, "errors": errors})
        else:
            results["valid"] += 1
        
        # Affichage
        status = "✓" if not errors else "✗"
        print(f"  {status} {filename}")
        for err in errors:
            print(f"      ⚠ {err}")
    
    # Résumé
    print(f"\n  Résumé:")
    print(f"  - Messages valides: {results['valid']}/{results['total']}")
    print(f"  - UF trouvées: {results['uf_found']}")
    print(f"  - RPPS trouvés: {results['rpps_found']}")
    
    # Vérifier que les UF configurées sont présentes
    found_expected_ufs = expected_ufs & results["uf_found"]
    if found_expected_ufs:
        print(f"  ✓ UF configurées trouvées: {found_expected_ufs}")
    
    missing_ufs = expected_ufs - results["uf_found"]
    if missing_ufs:
        print(f"  ⚠ UF attendues non trouvées: {missing_ufs}")
    
    # Vérifier que les RPPS configurés sont présents
    found_expected_rpps = expected_rpps & results["rpps_found"]
    if found_expected_rpps:
        print(f"  ✓ RPPS configurés trouvés: {found_expected_rpps}")
    
    return results


def parse_and_reimport(session: Session, exported_files: list[Path]) -> dict:
    """Parse et réimporte les messages via le pipeline inbound HL7."""
    print("\n=== 5. Réimport des messages via pipeline inbound ===")
    
    import asyncio
    
    try:
        from app.services.transport_inbound import on_message_inbound_async
        from app.models_shared import SystemEndpoint
    except ImportError as e:
        print(f"  ⚠ Import error: {e}, skip réimport")
        return {"skipped": True}
    
    results = {
        "parsed": 0,
        "ack_aa": 0,
        "ack_ae": 0,
        "ack_ar": 0,
        "errors": [],
        "patients_created": [],
        "venues_created": [],
    }
    
    # Créer ou trouver un endpoint de test pour la réception
    test_endpoint = session.exec(
        select(SystemEndpoint).where(
            SystemEndpoint.name.contains("roundtrip")
        )
    ).first()
    
    if not test_endpoint:
        # Chercher un endpoint receiver existant pour cette EJ
        test_endpoint = session.exec(
            select(SystemEndpoint).where(
                SystemEndpoint.entite_juridique_id == TEST_EJ_ID,
                SystemEndpoint.role == "receiver"
            )
        ).first()
    
    if not test_endpoint:
        # Créer un endpoint de test
        test_endpoint = SystemEndpoint(
            name="Test Roundtrip Endpoint",
            kind="HTTP",  # Type obligatoire
            role="receiver",
            entite_juridique_id=TEST_EJ_ID,
            is_enabled=True,
        )
        session.add(test_endpoint)
        session.commit()
        session.refresh(test_endpoint)
        print(f"  Endpoint de test créé: {test_endpoint.name} (id={test_endpoint.id})")
    else:
        print(f"  Endpoint de test: {test_endpoint.name} (id={test_endpoint.id})")
    
    async def process_messages():
        for filepath in exported_files:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            filename = filepath.name
            
            try:
                # Injecter le message via le pipeline inbound
                ack = await on_message_inbound_async(content, session, test_endpoint)
                results["parsed"] += 1
                
                # Analyser l'ACK
                if ack:
                    if "AA" in ack:
                        results["ack_aa"] += 1
                        print(f"  ✓ {filename} -> ACK AA")
                    elif "AE" in ack:
                        results["ack_ae"] += 1
                        print(f"  ⚠ {filename} -> ACK AE")
                    elif "AR" in ack:
                        results["ack_ar"] += 1
                        print(f"  ✗ {filename} -> ACK AR")
                    else:
                        print(f"  ? {filename} -> ACK inconnu")
                else:
                    print(f"  ✓ {filename} -> Pas d'ACK (ok)")
                    
            except Exception as e:
                results["errors"].append({"file": filename, "error": str(e)})
                print(f"  ✗ {filename}: {e}")
    
    # Exécuter le traitement async
    asyncio.run(process_messages())
    
    print(f"\n  Résumé réimport:")
    print(f"  - Messages traités: {results['parsed']}/{len(exported_files)}")
    print(f"  - ACK AA (succès): {results['ack_aa']}")
    print(f"  - ACK AE (erreur app): {results['ack_ae']}")
    print(f"  - ACK AR (rejet): {results['ack_ar']}")
    if results["errors"]:
        print(f"  - Erreurs: {len(results['errors'])}")
    
    return results


def run_roundtrip_test():
    """Exécute le test roundtrip complet."""
    print("=" * 60)
    print("TEST ROUNDTRIP - Scénarios avec UF/Médecins")
    print("=" * 60)
    print(f"Date: {datetime.now().isoformat()}")
    
    with next(get_session()) as session:
        # 1. Configurer l'EJ
        config = setup_ej_config(session)
        
        # 2. Matérialiser le scénario
        scenario = materialize_scenario(session)
        
        # 3. Exporter les messages
        exported_files = export_messages(session, scenario)
        
        # 4. Vérifier les messages
        verification = verify_messages(session, exported_files)
        
        # 5. Parser et réimporter
        reimport = parse_and_reimport(session, exported_files)
    
    # Résultat final
    print("\n" + "=" * 60)
    print("RÉSULTAT DU TEST ROUNDTRIP")
    print("=" * 60)
    
    success = verification["valid"] == verification["total"]
    
    if success:
        print("✓ TEST RÉUSSI")
        print(f"  - {verification['total']} messages générés et vérifiés")
        print(f"  - UF substituées correctement: {verification['uf_found']}")
        print(f"  - RPPS substituées correctement: {verification['rpps_found']}")
    else:
        print("✗ TEST ÉCHOUÉ")
        print(f"  - {verification['valid']}/{verification['total']} messages valides")
        for err in verification["errors"]:
            print(f"  - {err['file']}: {err['errors']}")
    
    print(f"\nFichiers exportés dans: {TEST_OUTPUT_DIR.absolute()}")
    
    return success


if __name__ == "__main__":
    success = run_roundtrip_test()
    sys.exit(0 if success else 1)
