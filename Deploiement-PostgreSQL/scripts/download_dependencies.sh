#!/bin/bash
#
# Script de téléchargement des dépendances Python pour déploiement hors-ligne
# À exécuter sur une machine avec connexion Internet et Python 3.8
#
# Usage: ./download_dependencies.sh
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
DEPS_DIR="${DEPLOY_DIR}/dependencies"

echo "==================================="
echo "MedData Bridge - Téléchargement des dépendances"
echo "==================================="
echo ""

# Vérifier Python 3.8+
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "Version Python détectée: ${python_version}"

if ! python3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)"; then
    echo "ERREUR: Python 3.8+ requis"
    exit 1
fi

# Créer le répertoire des dépendances
mkdir -p "${DEPS_DIR}"

echo ""
echo "Téléchargement des packages Python pour manylinux (compatible Fedora)..."
echo ""

# Télécharger les packages avec pip
# --platform: cibler manylinux pour compatibilité maximale
# --only-binary: forcer les wheels binaires pré-compilés
# --python-version: cibler Python 3.8
pip3 download \
    --dest "${DEPS_DIR}" \
    --platform manylinux2014_x86_64 \
    --python-version 38 \
    --only-binary=:all: \
    --requirement "${DEPLOY_DIR}/requirements-production.txt" \
    2>&1 || {
        echo ""
        echo "⚠️  Certains packages n'ont pas de wheels binaires."
        echo "Téléchargement avec sources pour compilation sur le serveur..."
        echo ""
        
        # Fallback: télécharger avec sources
        pip3 download \
            --dest "${DEPS_DIR}" \
            --requirement "${DEPLOY_DIR}/requirements-production.txt"
    }

echo ""
echo "✅ Téléchargement terminé!"
echo ""
echo "📦 Packages téléchargés dans: ${DEPS_DIR}"
echo "📊 Nombre de fichiers: $(ls -1 ${DEPS_DIR} | wc -l)"
echo "💾 Taille totale: $(du -sh ${DEPS_DIR} | cut -f1)"
echo ""
echo "📝 Prochaine étape: Exécuter prepare_deployment.sh"
