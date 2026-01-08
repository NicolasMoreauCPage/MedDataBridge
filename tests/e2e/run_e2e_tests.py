#!/usr/bin/env python3
"""
Script d'exécution des tests E2E Phase 5
Usage:
  python run_e2e_tests.py [options]
  
Options:
  --phase [5.1|5.2|5.3|integration|all] : Phase à tester (default: all)
  --headless [true|false] : Mode headless (default: true)
  --record-video : Enregistrer vidéos des tests
  --record-har : Enregistrer trafic réseau
  --parallel : Exécuter tests en parallèle
  --debug : Mode debug avec logs console
  --report : Générer rapport HTML détaillé
"""

import os
import sys
import argparse
import subprocess
import time
from pathlib import Path


class E2ETestRunner:
    """Runner pour les tests E2E Phase 5."""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.test_dir = self.project_root / "tests" / "e2e"
        self.artifacts_dir = self.project_root / "tests" / "artifacts"
        
        # Créer les répertoires nécessaires
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        (self.artifacts_dir / "screenshots").mkdir(exist_ok=True)
        (self.artifacts_dir / "videos").mkdir(exist_ok=True)
        (self.artifacts_dir / "reports").mkdir(exist_ok=True)
    
    def setup_environment(self, args):
        """Configure l'environnement de test."""
        env = os.environ.copy()
        
        # Variables d'environnement pour les tests
        env["TESTING"] = "1"
        env["E2E_TESTING"] = "1"
        
        if not args.headless:
            env["HEADED"] = "1"
        
        if args.record_video:
            env["RECORD_VIDEO"] = "1"
            
        if args.record_har:
            env["RECORD_HAR"] = "1"
            
        if args.debug:
            env["DEBUG_CONSOLE"] = "1"
            env["PYTEST_CURRENT_TEST"] = "1"
        
        return env
    
    def get_test_markers(self, phase):
        """Retourne les markers pytest selon la phase."""
        marker_map = {
            "5.1": "e2e_phase5_1",
            "5.2": "e2e_phase5_2", 
            "5.3": "e2e_phase5_3",
            "integration": "e2e_integration",
            "all": None  # Tous les tests E2E
        }
        return marker_map.get(phase)
    
    def build_pytest_command(self, args):
        """Construit la commande pytest."""
        cmd = [
            sys.executable, "-m", "pytest",
            str(self.test_dir),
            "-v",  # Verbose
            "--tb=short",  # Traceback court
            f"--maxfail={args.maxfail}",
        ]
        
        # Marker pour la phase
        marker = self.get_test_markers(args.phase)
        if marker:
            cmd.extend(["-m", marker])
        
        # Exécution parallèle
        if args.parallel:
            cmd.extend(["-n", "auto"])
        
        # Rapport HTML
        if args.report:
            report_path = self.artifacts_dir / "reports" / f"e2e_report_{int(time.time())}.html"
            cmd.extend(["--html", str(report_path), "--self-contained-html"])
        
        # Options de sortie
        if args.debug:
            cmd.append("-s")  # Ne pas capturer stdout
        
        # Coverage si demandé
        if args.coverage:
            cmd.extend(["--cov=app", "--cov-report=html", "--cov-report=term"])
            
        return cmd
    
    def check_server_running(self):
        """Vérifie que le serveur de test est démarré."""
        try:
            import requests
            response = requests.get("http://localhost:8000/", timeout=5)
            return response.status_code == 200
        except:
            return False
    
    def start_test_server(self):
        """Démarre le serveur de test si nécessaire."""
        if self.check_server_running():
            print("✅ Serveur de test déjà en cours d'exécution")
            return None
        
        print("🚀 Démarrage du serveur de test...")
        
        # Commande pour démarrer le serveur
        server_cmd = [
            sys.executable, "-m", "uvicorn",
            "app.app:app",
            "--host", "127.0.0.1",
            "--port", "8000",
            "--reload"
        ]
        
        # Démarrer le serveur en arrière-plan
        process = subprocess.Popen(
            server_cmd,
            cwd=self.project_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=os.environ.copy()
        )
        
        # Attendre que le serveur soit prêt
        max_retries = 30
        for i in range(max_retries):
            if self.check_server_running():
                print("✅ Serveur de test prêt")
                return process
            time.sleep(1)
            if i % 5 == 0:
                print(f"⏳ Attente du serveur... ({i + 1}/{max_retries})")
        
        # Timeout
        print("❌ Échec du démarrage du serveur")
        process.terminate()
        return None
    
    def install_playwright_browsers(self):
        """Installe les navigateurs Playwright si nécessaire."""
        try:
            import playwright
            print("✅ Playwright déjà installé")
            
            # Vérifier si les navigateurs sont installés
            result = subprocess.run([
                sys.executable, "-m", "playwright", "install", "--help"
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                print("🔧 Installation des navigateurs Playwright...")
                subprocess.run([
                    sys.executable, "-m", "playwright", "install", "chromium"
                ], check=True)
                print("✅ Navigateurs Playwright installés")
            
        except ImportError:
            print("❌ Playwright non trouvé. Installation...")
            subprocess.run([
                sys.executable, "-m", "pip", "install", 
                "playwright", "pytest-playwright"
            ], check=True)
            
            subprocess.run([
                sys.executable, "-m", "playwright", "install", "chromium"
            ], check=True)
            
            print("✅ Playwright installé avec succès")
    
    def run_tests(self, args):
        """Exécute les tests E2E."""
        print("🧪 Lancement des tests E2E Phase 5")
        print(f"Phase ciblée: {args.phase}")
        print(f"Mode headless: {args.headless}")
        print("-" * 50)
        
        # 1. Installer Playwright si nécessaire
        self.install_playwright_browsers()
        
        # 2. Démarrer le serveur de test
        server_process = self.start_test_server()
        
        try:
            # 3. Configurer l'environnement
            env = self.setup_environment(args)
            
            # 4. Construire la commande pytest
            cmd = self.build_pytest_command(args)
            
            print(f"🔧 Commande: {' '.join(cmd)}")
            print("-" * 50)
            
            # 5. Exécuter les tests
            start_time = time.time()
            result = subprocess.run(cmd, cwd=self.project_root, env=env)
            end_time = time.time()
            
            # 6. Résultats
            duration = end_time - start_time
            print("-" * 50)
            print(f"⏱️  Durée d'exécution: {duration:.2f}s")
            
            if result.returncode == 0:
                print("✅ Tous les tests E2E ont réussi!")
            else:
                print(f"❌ Tests E2E échoués (code: {result.returncode})")
                
            # Informations sur les artifacts
            if args.record_video or args.record_har or args.report:
                print(f"📁 Artifacts disponibles dans: {self.artifacts_dir}")
                
            return result.returncode
            
        finally:
            # 7. Nettoyer le serveur de test
            if server_process:
                print("🛑 Arrêt du serveur de test...")
                server_process.terminate()
                try:
                    server_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    server_process.kill()
                print("✅ Serveur de test arrêté")


def main():
    parser = argparse.ArgumentParser(
        description="Runner pour les tests E2E Phase 5",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        "--phase",
        choices=["5.1", "5.2", "5.3", "integration", "all"],
        default="all",
        help="Phase à tester (default: all)"
    )
    
    parser.add_argument(
        "--headless",
        type=lambda x: x.lower() == 'true',
        default=True,
        help="Mode headless (default: true)"
    )
    
    parser.add_argument(
        "--record-video",
        action="store_true",
        help="Enregistrer vidéos des tests"
    )
    
    parser.add_argument(
        "--record-har", 
        action="store_true",
        help="Enregistrer trafic réseau HAR"
    )
    
    parser.add_argument(
        "--parallel",
        action="store_true",
        help="Exécuter tests en parallèle"
    )
    
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Mode debug avec logs console"
    )
    
    parser.add_argument(
        "--report",
        action="store_true",
        help="Générer rapport HTML détaillé"
    )
    
    parser.add_argument(
        "--coverage",
        action="store_true",
        help="Mesurer la couverture de code"
    )
    
    parser.add_argument(
        "--maxfail",
        type=int,
        default=5,
        help="Arrêter après N échecs (default: 5)"
    )
    
    args = parser.parse_args()
    
    # Lancer les tests
    runner = E2ETestRunner()
    exit_code = runner.run_tests(args)
    
    sys.exit(exit_code)


if __name__ == "__main__":
    main()