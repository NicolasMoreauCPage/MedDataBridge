#!/bin/bash
#
# Script d'installation sur le serveur Fedora 7.9 (SANS connexion Internet)
# À exécuter sur le serveur de production
#
# Prérequis: Python 3.8+ installé
#
# Usage: sudo ./install_on_server.sh
#

set -e

if [ "$EUID" -ne 0 ]; then 
    echo "⚠️  Ce script doit être exécuté en tant que root (sudo)"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && cd .. && pwd)"
INSTALL_DIR="/opt/meddata-bridge"
SERVICE_USER="meddata"
DEPS_DIR="${SCRIPT_DIR}/dependencies"

echo "==================================="
echo "MedData Bridge - Installation sur serveur"
echo "==================================="
echo ""

# Vérifier Python 3.8+
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 n'est pas installé!"
    echo "Installation: sudo dnf install python38"
    exit 1
fi

python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "✅ Python détecté: ${python_version}"

# Vérifier que les dépendances sont présentes
if [ ! -d "${DEPS_DIR}" ] || [ -z "$(ls -A ${DEPS_DIR})" ]; then
    echo "❌ Répertoire dependencies/ vide ou manquant!"
    echo "Exécutez d'abord download_dependencies.sh sur une machine avec Internet"
    exit 1
fi

echo "✅ Dépendances trouvées: $(ls -1 ${DEPS_DIR} | wc -l) packages"
echo ""

# Créer l'utilisateur système
echo "👤 Création de l'utilisateur ${SERVICE_USER}..."
if ! id "${SERVICE_USER}" &>/dev/null; then
    useradd --system --home-dir "${INSTALL_DIR}" --shell /bin/bash "${SERVICE_USER}"
    echo "✅ Utilisateur ${SERVICE_USER} créé"
else
    echo "ℹ️  Utilisateur ${SERVICE_USER} existe déjà"
fi

# Créer les répertoires
echo ""
echo "📁 Création des répertoires..."
mkdir -p "${INSTALL_DIR}"/{app,logs,data,config}
mkdir -p /var/log/meddata-bridge

# Copier l'application
echo ""
echo "📦 Installation de l'application..."
rsync -av "${SCRIPT_DIR}/app/" "${INSTALL_DIR}/app/"
rsync -av "${SCRIPT_DIR}/alembic/" "${INSTALL_DIR}/alembic/"
cp "${SCRIPT_DIR}/alembic.ini" "${INSTALL_DIR}/"

# Créer l'environnement virtuel Python
echo ""
echo "🐍 Création de l'environnement virtuel Python..."
python3 -m venv "${INSTALL_DIR}/venv"

# Activer le venv
source "${INSTALL_DIR}/venv/bin/activate"

# Installer les dépendances depuis le cache local
echo ""
echo "📦 Installation des dépendances Python (mode hors-ligne)..."
pip install --upgrade pip --no-index --find-links="${DEPS_DIR}" || true
pip install --no-index --find-links="${DEPS_DIR}" -r "${SCRIPT_DIR}/requirements-production.txt"

# Vérifier l'installation
echo ""
echo "✅ Vérification de l'installation..."
python3 -c "import fastapi; print(f'FastAPI: {fastapi.__version__}')"
python3 -c "import sqlmodel; print(f'SQLModel: {sqlmodel.__version__}')"
python3 -c "import cryptography; print(f'Cryptography: {cryptography.__version__}')"
python3 -c "import sqlite3; print(f'SQLite: {sqlite3.sqlite_version}')"

# Copier le fichier de configuration exemple
echo ""
echo "⚙️  Configuration..."
cat > "${INSTALL_DIR}/config/.env.example" << 'EOF'
# MedData Bridge - Configuration Production (SQLite)
# Copier ce fichier vers .env et adapter les valeurs

# Database - SQLite (fichier local)
# La base de données sera créée automatiquement dans data/meddata.db

# Application
APP_HOST=0.0.0.0
APP_PORT=8000
APP_WORKERS=4

# Security - IMPORTANT : Générer des clés aléatoires
SECRET_KEY=CHANGEME_GENERATE_RANDOM_KEY
JWT_SECRET_KEY=CHANGEME_GENERATE_RANDOM_KEY

# Logging
LOG_LEVEL=INFO
LOG_FILE=/var/log/meddata-bridge/app.log

# Optional: Sentry monitoring
# SENTRY_DSN=https://...
EOF

# Créer le fichier de service systemd
echo ""
echo "🔧 Création du service systemd..."
cat > /etc/systemd/system/meddata-bridge.service << EOF
[Unit]
Description=MedData Bridge - Healthcare Interoperability Platform (SQLite)
After=network.target

[Service]
Type=notify
User=${SERVICE_USER}
Group=${SERVICE_USER}
WorkingDirectory=${INSTALL_DIR}
Environment="PATH=${INSTALL_DIR}/venv/bin"
EnvironmentFile=${INSTALL_DIR}/config/.env
ExecStart=${INSTALL_DIR}/venv/bin/uvicorn app.app:app --host \${APP_HOST} --port \${APP_PORT} --workers \${APP_WORKERS}
Restart=always
RestartSec=10

# Security
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=${INSTALL_DIR}/logs /var/log/meddata-bridge ${INSTALL_DIR}/data

[Install]
WantedBy=multi-user.target
EOF

# Définir les permissions
echo ""
echo "🔒 Configuration des permissions..."
chown -R "${SERVICE_USER}:${SERVICE_USER}" "${INSTALL_DIR}"
chown -R "${SERVICE_USER}:${SERVICE_USER}" /var/log/meddata-bridge
chmod 750 "${INSTALL_DIR}"
chmod 640 "${INSTALL_DIR}/config/.env.example"

# Recharger systemd
systemctl daemon-reload

echo ""
echo "==================================="
echo "✅ Installation terminée avec succès!"
echo "==================================="
echo ""
echo "📋 Prochaines étapes:"
echo ""
echo "1. Configurer l'application:"
echo "   cd ${INSTALL_DIR}/config"
echo "   cp .env.example .env"
echo "   vi .env  # Générer des clés sécurisées (SECRET_KEY, JWT_SECRET_KEY)"
echo ""
echo "   💡 Pour générer des clés sécurisées:"
echo "   python3 -c 'import secrets; print(secrets.token_hex(32))'"
echo ""
echo "2. Initialiser la base de données SQLite:"
echo "   cd ${INSTALL_DIR}"
echo "   sudo -u ${SERVICE_USER} ${INSTALL_DIR}/venv/bin/alembic upgrade head"
echo "   ✅ La base sera créée automatiquement dans ${INSTALL_DIR}/data/meddata.db"
echo ""
echo "3. Démarrer le service:"
echo "   sudo systemctl enable meddata-bridge"
echo "   sudo systemctl start meddata-bridge"
echo "   sudo systemctl status meddata-bridge"
echo ""
echo "4. Vérifier les logs:"
echo "   sudo journalctl -u meddata-bridge -f"
echo ""
echo "📊 Application installée dans: ${INSTALL_DIR}"
echo "📝 Logs: /var/log/meddata-bridge/"
echo "🌐 URL (après démarrage): http://localhost:8000"
