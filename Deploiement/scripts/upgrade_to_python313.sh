#!/bin/bash
#
# Script de mise à jour de MedDataBridge vers Python 3.13
# À exécuter APRÈS install_python313.sh
#

set -e

echo "=========================================="
echo "Mise à jour de MedDataBridge vers Python 3.13"
echo "=========================================="

# Vérifier que Python 3.13 est installé
if [ ! -x "/usr/local/bin/python3.13" ]; then
    echo "❌ Python 3.13 n'est pas installé"
    echo "Exécutez d'abord: sudo ./install_python313.sh"
    exit 1
fi

PYTHON_VERSION=$(/usr/local/bin/python3.13 --version)
echo "✓ ${PYTHON_VERSION} détecté"

echo ""
echo "Étape 1: Arrêt du service actuel"
echo "------------------------------------------------------"

if systemctl is-active --quiet meddata-bridge 2>/dev/null; then
    echo "Arrêt du service meddata-bridge..."
    sudo systemctl stop meddata-bridge
    echo "✓ Service arrêté"
else
    echo "ℹ Service non actif"
fi

echo ""
echo "Étape 2: Sauvegarde de l'environnement virtuel actuel"
echo "------------------------------------------------------"

if [ -d "/opt/meddata-bridge/venv" ]; then
    echo "Sauvegarde de l'ancien venv..."
    sudo mv /opt/meddata-bridge/venv /opt/meddata-bridge/venv.backup.$(date +%Y%m%d_%H%M%S)
    echo "✓ Ancien venv sauvegardé"
else
    echo "ℹ Pas de venv existant"
fi

echo ""
echo "Étape 3: Création du nouvel environnement virtuel Python 3.13"
echo "------------------------------------------------------"

cd /opt/meddata-bridge
sudo /usr/local/bin/python3.13 -m venv venv
echo "✓ Environnement virtuel créé"

echo ""
echo "Étape 4: Installation des dépendances"
echo "------------------------------------------------------"

# Vérifier si les dépendances Python 3.13 sont présentes
if [ -d "/opt/meddata-bridge/dependencies-py313" ]; then
    DEPS_DIR="/opt/meddata-bridge/dependencies-py313"
elif [ -d "/tmp/Deploiement/dependencies-py313" ]; then
    echo "Copie des dépendances depuis /tmp..."
    sudo cp -r /tmp/Deploiement/dependencies-py313 /opt/meddata-bridge/
    DEPS_DIR="/opt/meddata-bridge/dependencies-py313"
else
    echo "❌ Dépendances Python 3.13 non trouvées"
    echo "Elles devraient être dans: /opt/meddata-bridge/dependencies-py313"
    exit 1
fi

echo "Mise à jour de pip, setuptools, wheel..."
sudo /opt/meddata-bridge/venv/bin/pip install --upgrade pip setuptools wheel --no-index --find-links="${DEPS_DIR}"

echo "Installation des packages depuis ${DEPS_DIR}..."
sudo /opt/meddata-bridge/venv/bin/pip install \
    --no-index \
    --find-links="${DEPS_DIR}" \
    -r /opt/meddata-bridge/requirements.txt

echo "✓ Dépendances installées"

echo ""
echo "Étape 5: Vérification de l'installation"
echo "------------------------------------------------------"

# Test d'import rapide
sudo -u meddata /opt/meddata-bridge/venv/bin/python3.13 -c "
import sys
print(f'Python: {sys.version}')
import fastapi
print(f'FastAPI: {fastapi.__version__}')
import sqlmodel
print('SQLModel: OK')
import uvicorn
print('Uvicorn: OK')
" || {
    echo "❌ Erreur lors de la vérification des imports"
    exit 1
}

echo "✓ Imports principaux validés"

echo ""
echo "Étape 6: Ajustement des permissions"
echo "------------------------------------------------------"

sudo chown -R meddata:meddata /opt/meddata-bridge/venv
sudo chmod -R 755 /opt/meddata-bridge/venv
echo "✓ Permissions ajustées"

echo ""
echo "Étape 7: Mise à jour du service systemd"
echo "------------------------------------------------------"

# Vérifier que le service pointe bien sur le bon venv
SERVICE_FILE="/etc/systemd/system/meddata-bridge.service"
if grep -q "/opt/meddata-bridge/venv/bin" "${SERVICE_FILE}"; then
    echo "✓ Service systemd déjà configuré correctement"
else
    echo "⚠ Configuration du service à vérifier manuellement"
fi

sudo systemctl daemon-reload
echo "✓ systemd rechargé"

echo ""
echo "Étape 8: Démarrage du service"
echo "------------------------------------------------------"

sudo systemctl start meddata-bridge
sleep 3

if systemctl is-active --quiet meddata-bridge; then
    echo "✓ Service meddata-bridge démarré"
else
    echo "❌ Le service n'a pas démarré correctement"
    echo "Consultez les logs: sudo journalctl -u meddata-bridge -n 50"
    exit 1
fi

echo ""
echo "Étape 9: Vérification finale"
echo "------------------------------------------------------"

# Vérifier que le port 8000 écoute
sleep 2
if sudo netstat -tlnp | grep -q ":8000"; then
    echo "✓ Application écoute sur le port 8000"
else
    echo "⚠ Le port 8000 n'est pas ouvert, vérifiez les logs"
fi

# Test HTTP
if command -v curl &> /dev/null; then
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/ || echo "000")
    if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "404" ]; then
        echo "✓ Application répond aux requêtes HTTP"
    else
        echo "⚠ Application ne répond pas (code HTTP: $HTTP_CODE)"
    fi
fi

echo ""
echo "=========================================="
echo "✅ Mise à jour terminée !"
echo "=========================================="
echo ""
echo "MedDataBridge tourne maintenant avec Python 3.13"
echo ""
echo "Commandes utiles:"
echo "  - Voir les logs: sudo journalctl -u meddata-bridge -f"
echo "  - Redémarrer: sudo systemctl restart meddata-bridge"
echo "  - Statut: sudo systemctl status meddata-bridge"
echo ""
echo "Version Python dans le venv:"
/opt/meddata-bridge/venv/bin/python3.13 --version
