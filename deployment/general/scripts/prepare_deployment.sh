#!/bin/bash
#
# Script de préparation du package de déploiement complet
# À exécuter sur la machine de développement APRÈS download_dependencies.sh
#
# Usage: ./prepare_deployment.sh
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && cd .. && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
DEPLOY_DIR="${SCRIPT_DIR}"
APP_DIR="${DEPLOY_DIR}/app"

echo "==================================="
echo "MedData Bridge - Préparation du déploiement"
echo "==================================="
echo ""
echo "Projet source: ${PROJECT_ROOT}"
echo "Package déploiement: ${DEPLOY_DIR}"
echo ""

# Nettoyer et recréer le répertoire app
rm -rf "${APP_DIR}"
mkdir -p "${APP_DIR}"

echo "📁 Copie des fichiers de l'application..."

# Copier le code source (exclure les fichiers de dev/test)
rsync -av \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='*.pyo' \
    --exclude='.pytest_cache' \
    --exclude='tests/' \
    --exclude='.git' \
    --exclude='.venv' \
    --exclude='venv' \
    --exclude='*.db' \
    --exclude='*.sqlite' \
    --exclude='*.log' \
    --exclude='.env' \
    --exclude='Deploiement' \
    --exclude='node_modules' \
    --exclude='.mypy_cache' \
    --exclude='.coverage' \
    --exclude='htmlcov' \
    "${PROJECT_ROOT}/app/" \
    "${APP_DIR}/"

# Copier les migrations Alembic
echo "📦 Copie des migrations Alembic..."
mkdir -p "${DEPLOY_DIR}/alembic"
rsync -av \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    "${PROJECT_ROOT}/alembic/" \
    "${DEPLOY_DIR}/alembic/"

# Copier alembic.ini
cp "${PROJECT_ROOT}/alembic.ini" "${DEPLOY_DIR}/"

# Copier init_db.py (nécessaire pour initialiser la base)
echo "📊 Copie du script d'initialisation de la base..."
cp "${PROJECT_ROOT}/init_db.py" "${DEPLOY_DIR}/"

# Copier le dossier tools/ (scripts d'initialisation)
echo "🛠️  Copie des outils d'initialisation..."
mkdir -p "${DEPLOY_DIR}/tools"
rsync -av \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    "${PROJECT_ROOT}/tools/" \
    "${DEPLOY_DIR}/tools/"

# Copier les fichiers de configuration
echo "⚙️  Copie des fichiers de configuration..."
cp "${PROJECT_ROOT}/requirements.txt" "${DEPLOY_DIR}/config/requirements-original.txt"

# Créer un fichier de version
echo "📝 Création du fichier de version..."
cat > "${DEPLOY_DIR}/VERSION.txt" << EOF
MedData Bridge - Package de déploiement
Date: $(date '+%Y-%m-%d %H:%M:%S')
Branche: $(cd "${PROJECT_ROOT}" && git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")
Commit: $(cd "${PROJECT_ROOT}" && git rev-parse --short HEAD 2>/dev/null || echo "unknown")
Python requis: 3.8+
OS cible: Fedora 7.9
EOF

echo ""
echo "✅ Préparation terminée!"
echo ""
echo "📦 Structure du package:"
tree -L 2 "${DEPLOY_DIR}" 2>/dev/null || ls -la "${DEPLOY_DIR}"
echo ""
echo "📝 Prochaine étape: Transférer le répertoire Deploiement/ vers le serveur"
