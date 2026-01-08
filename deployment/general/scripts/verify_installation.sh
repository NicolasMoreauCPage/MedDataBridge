#!/bin/bash
#
# Script de vérification post-installation
# À exécuter sur le serveur après installation
#
# Usage: ./verify_installation.sh
#

set -e

INSTALL_DIR="/opt/meddata-bridge"
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "==================================="
echo "MedData Bridge - Vérification installation"
echo "==================================="
echo ""

check_pass() {
    echo -e "${GREEN}✅ $1${NC}"
}

check_fail() {
    echo -e "${RED}❌ $1${NC}"
}

check_warn() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

# Vérifier Python
echo "🐍 Python..."
if command -v python3 &> /dev/null; then
    python_version=$(python3 --version)
    check_pass "Python installé: ${python_version}"
else
    check_fail "Python 3 non trouvé"
    exit 1
fi

# Vérifier l'installation
echo ""
echo "📁 Installation..."
if [ -d "${INSTALL_DIR}" ]; then
    check_pass "Répertoire d'installation existe: ${INSTALL_DIR}"
else
    check_fail "Répertoire d'installation manquant: ${INSTALL_DIR}"
    exit 1
fi

# Vérifier l'environnement virtuel
if [ -d "${INSTALL_DIR}/venv" ]; then
    check_pass "Environnement virtuel existe"
else
    check_fail "Environnement virtuel manquant"
    exit 1
fi

# Vérifier les dépendances clés
echo ""
echo "📦 Dépendances Python..."
"${INSTALL_DIR}/venv/bin/python3" << 'EOF'
import sys
try:
    import fastapi
    print(f"✅ FastAPI: {fastapi.__version__}")
except ImportError:
    print("❌ FastAPI non installé")
    sys.exit(1)

try:
    import sqlmodel
    print(f"✅ SQLModel: {sqlmodel.__version__}")
except ImportError:
    print("❌ SQLModel non installé")
    sys.exit(1)

try:
    import cryptography
    print(f"✅ Cryptography: {cryptography.__version__}")
except ImportError:
    print("❌ Cryptography non installé")
    sys.exit(1)

try:
    import sqlite3
    print(f"✅ SQLite: {sqlite3.sqlite_version}")
except ImportError:
    print("❌ SQLite non disponible")
    sys.exit(1)
EOF

# Vérifier SQLite
echo ""
echo "🗄️  Base de données..."
if [ -f "${INSTALL_DIR}/data/meddata.db" ]; then
    check_pass "Base de données SQLite existe: ${INSTALL_DIR}/data/meddata.db"
    db_size=$(du -h "${INSTALL_DIR}/data/meddata.db" | cut -f1)
    echo "   Taille: ${db_size}"
else
    check_warn "Base de données SQLite pas encore créée (sera créée au premier démarrage)"
fi

# Vérifier la configuration
echo ""
echo "⚙️  Configuration..."
if [ -f "${INSTALL_DIR}/config/.env" ]; then
    check_pass "Fichier .env existe"
    
    # Vérifier les paramètres critiques
    if grep -q "SECRET_KEY=CHANGEME" "${INSTALL_DIR}/config/.env" 2>/dev/null; then
        check_warn "SECRET_KEY n'a pas été changé! Générer avec: python3 -c 'import secrets; print(secrets.token_hex(32))'"
    fi
    
    if grep -q "JWT_SECRET_KEY=CHANGEME" "${INSTALL_DIR}/config/.env" 2>/dev/null; then
        check_warn "JWT_SECRET_KEY n'a pas été changé! Générer avec: python3 -c 'import secrets; print(secrets.token_hex(32))'"
    fi
else
    check_warn "Fichier .env manquant (utiliser .env.example comme modèle)"
fi

# Vérifier le service systemd
echo ""
echo "🔧 Service systemd..."
if systemctl list-unit-files | grep -q meddata-bridge.service; then
    check_pass "Service systemd configuré"
    
    if systemctl is-enabled --quiet meddata-bridge; then
        check_pass "Service activé au démarrage"
    else
        check_warn "Service non activé au démarrage"
    fi
    
    if systemctl is-active --quiet meddata-bridge; then
        check_pass "Service en cours d'exécution"
    else
        check_warn "Service non démarré"
    fi
else
    check_fail "Service systemd non configuré"
fi

# Vérifier les logs
echo ""
echo "📝 Logs..."
if [ -d "/var/log/meddata-bridge" ]; then
    check_pass "Répertoire de logs existe"
    
    log_count=$(find /var/log/meddata-bridge -type f | wc -l)
    if [ "$log_count" -gt 0 ]; then
        check_pass "Fichiers de logs: ${log_count}"
    fi
else
    check_warn "Répertoire de logs manquant"
fi

# Test de connexion HTTP (si le service tourne)
echo ""
echo "🌐 Connectivité..."
if systemctl is-active --quiet meddata-bridge; then
    if curl -s -o /dev/null -w "%{http_code}" http://localhost:8000 | grep -q "200"; then
        check_pass "Application accessible sur http://localhost:8000"
    else
        check_warn "Application non accessible (vérifier les logs)"
    fi
else
    check_warn "Service non démarré, impossible de tester la connectivité"
fi

# Résumé
echo ""
echo "==================================="
echo "Résumé de la vérification"
echo "==================================="
echo ""

if [ -f "${INSTALL_DIR}/VERSION.txt" ]; then
    echo "📄 Version installée:"
    cat "${INSTALL_DIR}/VERSION.txt" | head -5
    echo ""
fi

echo "📊 Statistiques:"
echo "   Répertoire: ${INSTALL_DIR}"
echo "   Taille: $(du -sh ${INSTALL_DIR} 2>/dev/null | cut -f1)"
echo "   Packages Python: $(${INSTALL_DIR}/venv/bin/pip list 2>/dev/null | wc -l)"

echo ""
echo "Pour voir les logs en temps réel:"
echo "   sudo journalctl -u meddata-bridge -f"
echo ""
echo "Pour redémarrer le service:"
echo "   sudo systemctl restart meddata-bridge"
