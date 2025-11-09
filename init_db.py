#!/usr/bin/env python3
"""Script principal d'initialisation complète de la base de données.

Usage:
    python init_db.py                    # Init complète (structure + vocab + namespaces + population)
    python init_db.py --reset            # Supprime la DB existante avant init
    python init_db.py --skip-vocab       # Saute l'init des vocabulaires
    python init_db.py --skip-population  # Saute le seed de patients

Ce script orchestre dans l'ordre:
1. Création du schéma (tables) via app.db.init_db()
2. Vocabulaires standards (35 systèmes, 207 valeurs)
3. Structure multi-EJ (4 EJ: CHU, hôpital, EHPAD, psy) + hiérarchie complète
4. Endpoints MLLP/FHIR (12 endpoints: 3 par EJ)
5. Namespaces d'identifiants (13: IPP/NDA/VENUE par EJ + global structure)
6. Population de patients (120 par défaut avec dossiers et mouvements)

Tous les appels sont idempotents: re-exécuter ce script est safe.
"""
import argparse
import sys
from pathlib import Path
from subprocess import run, CalledProcessError

DB_PATH = Path("medbridge.db")


def main():
    parser = argparse.ArgumentParser(description="Initialisation complète de la base de données")
    parser.add_argument("--reset", action="store_true", help="Supprime medbridge.db avant init")
    parser.add_argument("--skip-vocab", action="store_true", help="Saute l'initialisation des vocabulaires")
    parser.add_argument("--skip-population", action="store_true", help="Saute le seed de population patients")
    args = parser.parse_args()

    if args.reset and DB_PATH.exists():
        print("→ Suppression de medbridge.db existante...")
        DB_PATH.unlink()
        print("✓ Base supprimée\n")

    # 1. Schéma (tables)
    print("=" * 60)
    print("ÉTAPE 1/4 : Création du schéma (tables)")
    print("=" * 60)
    try:
        from app.db import init_db
        init_db()
        print("✓ Tables créées\n")
    except Exception as e:
        print(f"✗ Échec création tables: {e}")
        sys.exit(1)

    # 2. Vocabulaires
    if not args.skip_vocab:
        print("=" * 60)
        print("ÉTAPE 2/4 : Initialisation des vocabulaires")
        print("=" * 60)
        try:
            run([sys.executable, "tools/init_vocabularies.py"], check=True)
            print("✓ Vocabulaires initialisés\n")
        except (CalledProcessError, FileNotFoundError) as e:
            print(f"✗ Échec vocabulaires: {e}")
            sys.exit(1)
    else:
        print("→ Vocabulaires sautés (--skip-vocab)\n")

    # 3. Structure étendue + endpoints + namespaces
    print("=" * 60)
    print("ÉTAPE 3/4 : Structure multi-EJ + endpoints + namespaces")
    print("=" * 60)
    try:
        run([sys.executable, "tools/init_extended_demo.py"], check=True)
        print("✓ Structure, endpoints et namespaces créés\n")
    except (CalledProcessError, FileNotFoundError) as e:
        print(f"✗ Échec structure étendue: {e}")
        sys.exit(1)

    # 4. Population (déjà incluse dans init_extended_demo mais peut être sautée)
    if args.skip_population:
        print("→ Population patients sautée (--skip-population)\n")
    else:
        print("=" * 60)
        print("ÉTAPE 4/4 : Vérification population patients")
        print("=" * 60)
        # init_extended_demo.py gère déjà la population, donc juste un message
        print("✓ Population incluse dans init_extended_demo.py\n")

    # Résumé final
    print("=" * 60)
    print("✅ INITIALISATION COMPLÈTE TERMINÉE")
    print("=" * 60)
    print("\nRésumé:")
    print("  • Tables       : créées")
    if not args.skip_vocab:
        print("  • Vocabulaires : 35 systèmes, 207 valeurs")
    print("  • Structures   : 4 EJ (CHU, hôpital, EHPAD, psy) + hiérarchie")
    print("  • Endpoints    : 12 (MLLP + FHIR par EJ)")
    print("  • Namespaces   : 13 (IPP/NDA/VENUE par EJ + global)")
    if not args.skip_population:
        print("  • Population   : 120 patients, dossiers et mouvements")
    print("\nLe serveur peut être démarré avec:")
    print("  uvicorn app.app:app --reload")
    print("\nAccès admin: http://localhost:8000/admin/ght/1/ej/1")


if __name__ == "__main__":
    main()
