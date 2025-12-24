#!/bin/bash

# Script de déploiement MedBridge
# Utilisation: ./scripts/deploy.sh [environment] [action]
# Exemples:
#   ./scripts/deploy.sh staging build
#   ./scripts/deploy.sh production deploy
#   ./scripts/deploy.sh development test

set -e  # Exit on any error

ENVIRONMENT=${1:-development}
ACTION=${2:-build}

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DOCKER_COMPOSE_FILE="$PROJECT_ROOT/docker/docker-compose.yml"

echo "🚀 MedBridge Deployment Script"
echo "Environment: $ENVIRONMENT"
echo "Action: $ACTION"
echo "Project root: $PROJECT_ROOT"
echo "----------------------------------------"

# Fonction pour vérifier les prérequis
check_prerequisites() {
    echo "📋 Checking prerequisites..."

    # Docker
    if ! command -v docker &> /dev/null; then
        echo "❌ Docker is not installed"
        exit 1
    fi

    # Docker Compose
    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        echo "❌ Docker Compose is not installed"
        exit 1
    fi

    # Python
    if ! command -v python3 &> /dev/null; then
        echo "❌ Python3 is not installed"
        exit 1
    fi

    echo "✅ Prerequisites OK"
}

# Fonction pour exécuter les tests
run_tests() {
    echo "🧪 Running tests..."

    cd "$PROJECT_ROOT"

    # Activer l'environnement virtuel si présent
    if [ -f ".venv/bin/activate" ]; then
        source .venv/bin/activate
    fi

    # Installer les dépendances de test
    pip install -e ".[test]"

    # Exécuter les tests
    python -m pytest tests/ -v --cov=app --cov-report=html --cov-report=term

    # Vérifier la couverture
    COVERAGE=$(python -m pytest tests/ --cov=app --cov-report=term-missing | grep "TOTAL" | awk '{print $4}' | sed 's/%//')
    if (( $(echo "$COVERAGE < 80" | bc -l) )); then
        echo "❌ Code coverage too low: $COVERAGE%"
        exit 1
    fi

    echo "✅ Tests passed with $COVERAGE% coverage"
}

# Fonction pour construire les images Docker
build_docker() {
    echo "🏗️ Building Docker images..."

    cd "$PROJECT_ROOT"

    # Build avec cache
    if [ "$ENVIRONMENT" = "production" ]; then
        docker-compose -f "$DOCKER_COMPOSE_FILE" build --no-cache
    else
        docker-compose -f "$DOCKER_COMPOSE_FILE" build
    fi

    echo "✅ Docker images built"
}

# Fonction pour déployer
deploy() {
    echo "🚀 Deploying to $ENVIRONMENT..."

    cd "$PROJECT_ROOT"

    # Variables d'environnement
    export ENVIRONMENT=$ENVIRONMENT

    # Arrêter les services existants
    docker-compose -f "$DOCKER_COMPOSE_FILE" down || true

    # Démarrer les services
    if [ "$ENVIRONMENT" = "production" ]; then
        docker-compose -f "$DOCKER_COMPOSE_FILE" up -d
    else
        docker-compose -f "$DOCKER_COMPOSE_FILE" up -d postgres redis
        sleep 10  # Attendre que les DB soient prêtes
        docker-compose -f "$DOCKER_COMPOSE_FILE" up -d medbridge
    fi

    # Attendre que l'application soit prête
    echo "⏳ Waiting for application to be ready..."
    for i in {1..30}; do
        if curl -f http://localhost:8000/health &>/dev/null; then
            echo "✅ Application is ready!"
            break
        fi
        sleep 2
    done

    # Vérifier le déploiement
    if curl -f http://localhost:8000/health &>/dev/null; then
        echo "✅ Deployment successful!"
        echo "🌐 Application available at: http://localhost:8000"
    else
        echo "❌ Deployment failed - health check failed"
        exit 1
    fi
}

# Fonction pour les migrations de base de données
run_migrations() {
    echo "🗄️ Running database migrations..."

    cd "$PROJECT_ROOT"

    # Attendre que la DB soit prête
    docker-compose -f "$DOCKER_COMPOSE_FILE" exec -T postgres sh -c 'while ! pg_isready -U medbridge; do sleep 1; done'

    # Exécuter les migrations
    docker-compose -f "$DOCKER_COMPOSE_FILE" exec -T medbridge python -m alembic upgrade head

    echo "✅ Database migrations completed"
}

# Fonction pour nettoyer
cleanup() {
    echo "🧹 Cleaning up..."

    cd "$PROJECT_ROOT"

    # Supprimer les images non utilisées
    docker image prune -f

    # Supprimer les volumes non utilisés (attention!)
    # docker volume prune -f

    echo "✅ Cleanup completed"
}

# Fonction principale
main() {
    case $ACTION in
        "test")
            check_prerequisites
            run_tests
            ;;
        "build")
            check_prerequisites
            run_tests
            build_docker
            ;;
        "deploy")
            check_prerequisites
            run_tests
            build_docker
            deploy
            run_migrations
            ;;
        "migrate")
            run_migrations
            ;;
        "cleanup")
            cleanup
            ;;
        *)
            echo "❌ Unknown action: $ACTION"
            echo "Available actions: test, build, deploy, migrate, cleanup"
            exit 1
            ;;
    esac
}

# Exécuter la fonction principale
main "$@"