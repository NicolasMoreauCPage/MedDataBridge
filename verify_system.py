#!/usr/bin/env python3
"""
Script de vérification complète du système MedDataBridge.

Vérifie:
- Configuration de la base de données
- Chargement des modules
- Disponibilité des API
- État des tests
- Métriques de performance
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import click
from sqlmodel import Session, select
from app.db import engine, init_db
from app.models_structure import GHTContext, EntiteJuridique


@click.command()
@click.option('--verbose', is_flag=True, help='Affichage détaillé')
def verify_system(verbose: bool):
    """Vérifie l'intégrité du système MedDataBridge."""
    
    print("\n" + "="*80)
    print("🔍 VÉRIFICATION SYSTÈME MEDATABRIDGE")
    print("="*80 + "\n")
    
    checks_passed = 0
    checks_total = 0
    
    # 1. Vérification de la base de données
    checks_total += 1
    print("📊 Vérification base de données...")
    try:
        init_db()
        with Session(engine) as session:
            # Compter les GHT
            ght_count = session.exec(select(GHTContext)).count()
            ej_count = session.exec(select(EntiteJuridique)).count()
            
            print(f"  ✓ Base de données accessible")
            print(f"  ✓ {ght_count} GHT configuré(s)")
            print(f"  ✓ {ej_count} Entité(s) Juridique(s)")
            checks_passed += 1
    except Exception as e:
        print(f"  ✗ Erreur base de données: {e}")
    
    # 2. Vérification de l'application
    checks_total += 1
    print("\n🚀 Vérification application FastAPI...")
    try:
        from app.app import create_app
        app = create_app()
        route_count = len([r for r in app.routes])
        print(f"  ✓ Application créée")
        print(f"  ✓ {route_count} routes chargées")
        checks_passed += 1
    except Exception as e:
        print(f"  ✗ Erreur application: {e}")
    
    # 3. Vérification des modules critiques
    checks_total += 1
    print("\n📦 Vérification modules critiques...")
    critical_modules = [
        'app.services.fhir_export_service',
        'app.converters.fhir_converter',
        'app.validators.hl7_validators',
        'app.utils.structured_logging',
        'app.utils.error_handling',
    ]
    
    all_modules_ok = True
    for module_name in critical_modules:
        try:
            __import__(module_name)
            if verbose:
                print(f"  ✓ {module_name}")
        except ImportError as e:
            print(f"  ✗ {module_name}: {e}")
            all_modules_ok = False
    
    if all_modules_ok:
        print(f"  ✓ Tous les modules critiques chargés")
        checks_passed += 1
    else:
        print(f"  ✗ Certains modules manquants")
    
    # 4. Vérification des APIs
    checks_total += 1
    print("\n🔌 Vérification endpoints API...")
    critical_endpoints = [
        '/api/fhir/export/structure/{ej_id}',
        '/api/fhir/export/patients/{ej_id}',
        '/api/fhir/export/venues/{ej_id}',
        '/api/fhir/import/bundle',
        '/api/metrics/operations',
        '/api/metrics/health',
    ]
    
    endpoints_ok = True
    for endpoint in critical_endpoints:
        # Vérifier que l'endpoint existe dans l'app
        found = any(endpoint.replace('{ej_id}', '1') in str(route.path) 
                   for route in app.routes)
        if verbose and found:
            print(f"  ✓ {endpoint}")
        elif not found:
            print(f"  ✗ {endpoint} non trouvé")
            endpoints_ok = False
    
    if endpoints_ok:
        print(f"  ✓ Tous les endpoints critiques disponibles")
        checks_passed += 1
    else:
        print(f"  ✗ Certains endpoints manquants")
    
    # 5. Vérification des tests
    checks_total += 1
    print("\n🧪 Vérification tests...")
    test_files = list(Path('tests').glob('test_*.py'))
    print(f"  ✓ {len(test_files)} fichiers de tests trouvés")
    
    # Essayer de lancer les tests FHIR rapidement
    try:
        import subprocess
        result = subprocess.run(
            ['python3', '-m', 'pytest', 'tests/test_fhir_converter.py', '-v', '--tb=no'],
            capture_output=True,
            timeout=30,
            text=True
        )
        if result.returncode == 0:
            print(f"  ✓ Tests FHIR passent")
            checks_passed += 1
        else:
            print(f"  ⚠ Certains tests échouent")
            if verbose:
                print(result.stdout)
    except Exception as e:
        print(f"  ⚠ Impossible de lancer les tests: {e}")
    
    # 6. Vérification des outils
    checks_total += 1
    print("\n🔧 Vérification outils...")
    tools = ['cli.py', 'tools/code_analyzer.py']
    tools_ok = all(Path(tool).exists() for tool in tools)
    
    if tools_ok:
        print(f"  ✓ Tous les outils disponibles")
        checks_passed += 1
    else:
        print(f"  ✗ Certains outils manquants")
    
    # 7. Vérification de la documentation
    checks_total += 1
    print("\n📚 Vérification documentation...")
    docs = ['Doc/FHIR_API.md', 'PROGRESS_REPORT.md', 'README.md']
    docs_ok = all(Path(doc).exists() for doc in docs)
    
    if docs_ok:
        print(f"  ✓ Documentation disponible")
        checks_passed += 1
    else:
        print(f"  ⚠ Certains documents manquants")
    
    # Résumé
    print("\n" + "="*80)
    print(f"📊 RÉSULTAT: {checks_passed}/{checks_total} vérifications réussies")
    
    if checks_passed == checks_total:
        print("✅ Système opérationnel!")
        status = 0
    elif checks_passed >= checks_total * 0.8:
        print("⚠️  Système fonctionnel avec avertissements")
        status = 0
    else:
        print("❌ Problèmes critiques détectés")
        status = 1
    
    print("="*80 + "\n")
    
    # Afficher les commandes utiles
    print("💡 Commandes utiles:")
    print("  - Lancer l'application: uvicorn app.app:app --reload")
    print("  - Exporter FHIR: python cli.py export-fhir --ej-id 1")
    print("  - Valider HL7: python cli.py validate-hl7 --input message.hl7")
    print("  - Analyser code: python tools/code_analyzer.py app/")
    print("  - Tests: pytest tests/ -v")
    print()
    
    sys.exit(status)


if __name__ == '__main__':
    verify_system()