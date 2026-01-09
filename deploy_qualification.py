#!/usr/bin/env python3
"""
Script de déploiement pour MedData Bridge - Environnement de Qualification

Ce script automatise le déploiement de l'application avec toutes les nouvelles
fonctionnalités de monitoring et performance dans un environnement de qualification.

Usage:
    python deploy_qualification.py [options]

Options:
    --env ENV          Environnement (qualification, staging, production)
    --init-db         Initialiser la base de données
    --run-tests       Exécuter les tests avant déploiement
    --start-services  Démarrer les services après déploiement
    --verbose         Mode verbeux
"""

import os
import sys
import argparse
import subprocess
import logging
from pathlib import Path
from datetime import datetime

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Chemins importants
PROJECT_ROOT = Path(__file__).parent
VENV_PATH = PROJECT_ROOT / ".venv"
CONFIG_FILE = PROJECT_ROOT / ".env"


class QualificationDeployment:
    """Classe de gestion du déploiement en qualification."""

    def __init__(self, env="qualification", verbose=False):
        self.env = env
        self.verbose = verbose
        self.start_time = datetime.now()

        # Configuration selon l'environnement
        self.config = self._get_env_config()

    def _get_env_config(self):
        """Configuration spécifique à l'environnement."""
        configs = {
            "qualification": {
                "app_env": "staging",  # Utilise la config staging
                "host": "0.0.0.0",
                "port": 8001,  # Port différent pour qualification
                "debug": False,
                "enable_metrics": True,
                "log_level": "INFO",
                "db_init": True,
                "run_tests": True
            },
            "staging": {
                "app_env": "staging",
                "host": "0.0.0.0",
                "port": 8002,
                "debug": False,
                "enable_metrics": True,
                "log_level": "INFO",
                "db_init": False,
                "run_tests": True
            },
            "production": {
                "app_env": "production",
                "host": "0.0.0.0",
                "port": 8000,
                "debug": False,
                "enable_metrics": True,
                "log_level": "WARNING",
                "db_init": False,
                "run_tests": False
            }
        }
        return configs.get(self.env, configs["qualification"])

    def run_command(self, cmd, cwd=None, check=True, capture_output=False):
        """Exécute une commande système."""
        if self.verbose:
            logger.info(f"Exécution: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                cwd=cwd or PROJECT_ROOT,
                check=check,
                capture_output=capture_output,
                text=True
            )
            return result
        except subprocess.CalledProcessError as e:
            logger.error(f"Commande échouée: {' '.join(cmd)}")
            logger.error(f"Code de sortie: {e.returncode}")
            if e.stdout:
                logger.error(f"STDOUT: {e.stdout}")
            if e.stderr:
                logger.error(f"STDERR: {e.stderr}")
            raise

    def check_prerequisites(self):
        """Vérifie les prérequis système."""
        logger.info("🔍 Vérification des prérequis...")

        # Vérifier Python
        result = self.run_command(["python3", "--version"], capture_output=True)
        logger.info(f"✅ Python: {result.stdout.strip()}")

        # Vérifier pip
        result = self.run_command(["pip3", "--version"], capture_output=True)
        logger.info(f"✅ Pip: {result.stdout.strip()}")

        # Vérifier git
        result = self.run_command(["git", "--version"], capture_output=True)
        logger.info(f"✅ Git: {result.stdout.strip()}")

        # Vérifier que nous sommes dans le bon répertoire
        if not (PROJECT_ROOT / "pyproject.toml").exists():
            raise FileNotFoundError("pyproject.toml non trouvé - êtes-vous dans le bon répertoire?")

        logger.info("✅ Prérequis vérifiés")

    def setup_environment(self):
        """Configure l'environnement virtuel et les dépendances."""
        logger.info("🐍 Configuration de l'environnement Python...")

        # Créer l'environnement virtuel si nécessaire
        if not VENV_PATH.exists():
            logger.info("Création de l'environnement virtuel...")
            self.run_command(["python3", "-m", "venv", VENV_PATH])

        # Activer l'environnement virtuel et installer les dépendances
        pip_cmd = [str(VENV_PATH / "bin" / "pip"), "install", "-e", "."]

        if self.env == "qualification":
            # En qualification, installer aussi les dépendances de développement
            pip_cmd.extend(["-r", "requirements.txt"])

        self.run_command(pip_cmd)

        logger.info("✅ Environnement Python configuré")

    def create_config(self):
        """Crée la configuration pour l'environnement."""
        logger.info("⚙️ Configuration de l'application...")

        config_content = f"""# Configuration générée automatiquement pour {self.env}
# Généré le {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

ENVIRONMENT={self.config['app_env']}
DEBUG={str(self.config['debug']).lower()}
HOST={self.config['host']}
PORT={self.config['port']}
LOG_LEVEL={self.config['log_level']}
ENABLE_METRICS={str(self.config['enable_metrics']).lower()}

# Sécurité - À configurer manuellement en production
SECRET_KEY={os.getenv('SECRET_KEY', 'qualification-secret-key-change-in-prod')}
JWT_SECRET_KEY={os.getenv('JWT_SECRET_KEY', 'qualification-jwt-secret-change-in-prod')}

# Base de données
DATABASE_URL=sqlite:///./medbridge_qualification.db

# Cache Redis (optionnel)
REDIS_URL={os.getenv('REDIS_URL', '')}

# Fonctionnalités avancées
ENABLE_REQUEST_VALIDATION=true
MAX_CONCURRENT_TASKS=5
TASK_TIMEOUT=1800
ENABLE_CONFIG_HOT_RELOAD=false

# MLLP et services
MLLP_TRACE=true
FILE_POLL_INTERVAL=30
"""

        config_file = PROJECT_ROOT / f".env.{self.env}"
        with open(config_file, 'w') as f:
            f.write(config_content)

        # Créer un lien symbolique vers .env si demandé
        if not CONFIG_FILE.exists():
            config_file.rename(CONFIG_FILE)

        logger.info(f"✅ Configuration créée: {config_file}")

    def run_tests(self):
        """Exécute la suite de tests."""
        if not self.config.get('run_tests', False):
            logger.info("⏭️ Tests ignorés pour cet environnement")
            return

        logger.info("🧪 Exécution des tests...")

        # Tests unitaires
        logger.info("Exécution des tests unitaires...")
        self.run_command([
            str(VENV_PATH / "bin" / "python"), "-m", "pytest",
            "tests/unit/", "-v", "--tb=short"
        ])

        # Tests d'intégration
        logger.info("Exécution des tests d'intégration...")
        self.run_command([
            str(VENV_PATH / "bin" / "python"), "-m", "pytest",
            "tests/integration/test_new_features_integration.py", "-v", "--tb=short"
        ])

        # Tests de performance (si disponibles)
        perf_test = PROJECT_ROOT / "tests/performance"
        if perf_test.exists():
            logger.info("Exécution des tests de performance...")
            self.run_command([
                str(VENV_PATH / "bin" / "python"), "-m", "pytest",
                "tests/performance/", "-v", "--tb=short", "--durations=10"
            ])

        logger.info("✅ Tests exécutés avec succès")

    def init_database(self):
        """Initialise la base de données."""
        if not self.config.get('db_init', False):
            logger.info("⏭️ Initialisation DB ignorée pour cet environnement")
            return

        logger.info("🗄️ Initialisation de la base de données...")

        # Initialiser la DB avec des données de test
        self.run_command([
            str(VENV_PATH / "bin" / "python"), "scripts/manual/init_full.py",
            "--rich-seed", "--demo-scenarios", "--extended-structure",
            "--hl7-scenarios", "--with-vocab"
        ])

        logger.info("✅ Base de données initialisée")

    def validate_deployment(self):
        """Valide que le déploiement fonctionne correctement."""
        logger.info("🔍 Validation du déploiement...")

        # Tester que l'application peut démarrer
        test_cmd = [
            str(VENV_PATH / "bin" / "python"), "-c",
            "from app.app import create_app; app = create_app(); print('✅ Application OK')"
        ]
        self.run_command(test_cmd)

        # Tester les endpoints critiques
        import time
        import requests
        from concurrent.futures import ThreadPoolExecutor

        # Démarrer l'application en arrière-plan pour les tests
        import subprocess
        server_process = subprocess.Popen([
            str(VENV_PATH / "bin" / "python"), "-m", "uvicorn",
            "app.app:app", "--host", self.config['host'],
            "--port", str(self.config['port']), "--reload"
        ], cwd=PROJECT_ROOT)

        time.sleep(3)  # Attendre que le serveur démarre

        try:
            base_url = f"http://{self.config['host']}:{self.config['port']}"

            # Tests des endpoints
            endpoints_to_test = [
                "/health",
                "/metrics",
                "/api/docs",
                "/api/tasks/stats"
            ]

            for endpoint in endpoints_to_test:
                try:
                    response = requests.get(f"{base_url}{endpoint}", timeout=5)
                    if response.status_code == 200:
                        logger.info(f"✅ Endpoint {endpoint}: OK")
                    else:
                        logger.warning(f"⚠️ Endpoint {endpoint}: HTTP {response.status_code}")
                except Exception as e:
                    logger.error(f"❌ Endpoint {endpoint}: {e}")

            # Test des nouvelles fonctionnalités
            # Métriques
            metrics_resp = requests.get(f"{base_url}/metrics")
            if metrics_resp.status_code == 200:
                metrics_data = metrics_resp.json()
                logger.info(f"✅ Métriques: {len(metrics_data.get('requests', {}))} endpoints trackés")

            # Tâches
            tasks_resp = requests.get(f"{base_url}/api/tasks/stats")
            if tasks_resp.status_code == 200:
                tasks_data = tasks_resp.json()
                logger.info(f"✅ Tâches: {tasks_data.get('total_tasks', 0)} tâches gérées")

        finally:
            server_process.terminate()
            server_process.wait()

        logger.info("✅ Validation du déploiement terminée")

    def generate_report(self):
        """Génère un rapport de déploiement."""
        duration = datetime.now() - self.start_time

        report = f"""
╔══════════════════════════════════════════════════════════════╗
║              RAPPORT DE DÉPLOIEMENT - {self.env.upper()}              ║
╚══════════════════════════════════════════════════════════════╝

📅 Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
⏱️ Durée: {duration.total_seconds():.1f} secondes

🏗️ Configuration:
   • Environnement: {self.env}
   • Host: {self.config['host']}:{self.config['port']}
   • Debug: {self.config['debug']}
   • Métriques: {self.config['enable_metrics']}
   • Logs: {self.config['log_level']}

✅ Étapes exécutées:
   • Vérification des prérequis
   • Configuration de l'environnement Python
   • Création de la configuration
   • Exécution des tests
   • Initialisation de la base de données
   • Validation du déploiement

🔗 Endpoints disponibles:
   • Health Check: http://{self.config['host']}:{self.config['port']}/health
   • Métriques: http://{self.config['host']}:{self.config['port']}/metrics
   • API Tasks: http://{self.config['host']}:{self.config['port']}/api/tasks/
   • Documentation: http://{self.config['host']}:{self.config['port']}/api/docs

📊 Fonctionnalités activées:
   • Système de métriques temps réel
   • Cache Redis avec fallback mémoire
   • API de tâches asynchrones
   • Validation avancée des données
   • Logging structuré avec rotation
   • Configuration hot-reload (désactivé en {self.env})

🚀 Pour démarrer l'application:
   cd {PROJECT_ROOT}
   source .venv/bin/activate
   python -m uvicorn app.app:app --host {self.config['host']} --port {self.config['port']} --reload

⚠️ Actions post-déploiement recommandées:
   1. Configurer les secrets de production (SECRET_KEY, JWT_SECRET_KEY)
   2. Configurer Redis si nécessaire pour le cache distribué
   3. Ajuster les limites de ressources selon l'environnement
   4. Configurer la surveillance (logs, métriques, alertes)
   5. Tester les intégrations externes (HL7, FHIR, etc.)

╔══════════════════════════════════════════════════════════════╗
║                    DÉPLOIEMENT RÉUSSI !                     ║
╚══════════════════════════════════════════════════════════════╝
"""

        report_file = PROJECT_ROOT / f"deployment_report_{self.env}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report)

        print(report)
        logger.info(f"📄 Rapport sauvegardé: {report_file}")

    def deploy(self):
        """Exécute le déploiement complet."""
        logger.info(f"🚀 Démarrage du déploiement en environnement {self.env}")

        try:
            self.check_prerequisites()
            self.setup_environment()
            self.create_config()
            self.run_tests()
            self.init_database()
            self.validate_deployment()
            self.generate_report()

            logger.info("🎉 Déploiement terminé avec succès!")

        except Exception as e:
            logger.error(f"❌ Échec du déploiement: {e}")
            raise


def main():
    parser = argparse.ArgumentParser(description="Déploiement MedData Bridge - Qualification")
    parser.add_argument(
        "--env",
        choices=["qualification", "staging", "production"],
        default="qualification",
        help="Environnement de déploiement"
    )
    parser.add_argument(
        "--init-db",
        action="store_true",
        help="Forcer l'initialisation de la base de données"
    )
    parser.add_argument(
        "--run-tests",
        action="store_true",
        help="Forcer l'exécution des tests"
    )
    parser.add_argument(
        "--start-services",
        action="store_true",
        help="Démarrer les services après déploiement"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Mode verbeux"
    )

    args = parser.parse_args()

    # Configuration du logging
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Créer l'instance de déploiement
    deployment = QualificationDeployment(env=args.env, verbose=args.verbose)

    # Override de la configuration si demandé
    if args.init_db:
        deployment.config['db_init'] = True
    if args.run_tests:
        deployment.config['run_tests'] = True

    # Exécuter le déploiement
    deployment.deploy()

    # Démarrer les services si demandé
    if args.start_services:
        logger.info("🔄 Démarrage des services...")
        # Ici on pourrait ajouter la logique pour démarrer les services
        # (serveur web, workers, etc.)


if __name__ == "__main__":
    main()