#!/bin/bash
#
# Script d'installation sur le serveur RHEL 7.9 (SANS connexion Internet)
# À exécuter sur le serveur de production avec Python 3.13
#
# Prérequis: Python 3.13 installé (via install_python313.sh)
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
DEPS_DIR="${SCRIPT_DIR}/dependencies-py313"
PYTHON_BIN="/usr/local/bin/python3.13"

echo "==================================="
echo "MedData Bridge - Installation sur serveur"
echo "Version Python 3.13"
echo "==================================="
echo ""

# Vérifier Python 3.13
if [ ! -x "${PYTHON_BIN}" ]; then
    echo "❌ Python 3.13 n'est pas installé!"
    echo ""
    echo "Installez d'abord Python 3.13 avec:"
    echo "  cd ${SCRIPT_DIR}/scripts"
    echo "  sudo ./install_python313.sh"
    echo ""
    exit 1
fi

python_version=$(${PYTHON_BIN} --version 2>&1 | awk '{print $2}')
echo "✅ Python détecté: ${python_version}"

# Vérifier SQLite dans Python
echo ""
echo "Vérification du support SQLite..."
if ${PYTHON_BIN} -c "import sqlite3; print(sqlite3.sqlite_version)" >/dev/null 2>&1; then
    sqlite_version=$(${PYTHON_BIN} -c "import sqlite3; print(sqlite3.sqlite_version)" 2>&1)
    echo "✅ SQLite ${sqlite_version} activé"
else
    echo ""
    echo "❌ ERREUR: Python 3.13 a été compilé SANS le support SQLite!"
    echo ""
    echo "SOLUTION: Recompiler Python 3.13 avec SQLite"
    echo ""
    echo "Étapes:"
    echo "  1. Installer sqlite-devel:"
    echo "     sudo yum install sqlite-devel"
    echo ""
    echo "  2. Recompiler Python 3.13:"
    echo "     cd /usr/src/Python-3.13.0"
    echo "     sudo make clean"
    echo "     sudo ./configure --enable-optimizations --enable-loadable-sqlite-extensions"
    echo "     sudo make -j\$(nproc)"
    echo "     sudo make altinstall"
    echo ""
    echo "  3. Vérifier SQLite:"
    echo "     /usr/local/bin/python3.13 -c 'import sqlite3; print(sqlite3.sqlite_version)'"
    echo ""
    echo "  4. Relancer ce script:"
    echo "     sudo ./install_on_server.sh"
    echo ""
    exit 1
fi

# Vérifier que les dépendances Python 3.13 sont présentes
if [ ! -d "${DEPS_DIR}" ] || [ -z "$(ls -A ${DEPS_DIR})" ]; then
    echo "❌ Répertoire dependencies-py313/ vide ou manquant!"
    echo "Les dépendances doivent être présentes dans: ${DEPS_DIR}"
    exit 1
fi

echo "✅ Dépendances Python 3.13 trouvées: $(ls -1 ${DEPS_DIR}/*.whl 2>/dev/null | wc -l) packages"
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
rsync -av "${SCRIPT_DIR}/app/" "${INSTALL_DIR}/app/" 2>/dev/null || cp -r "${SCRIPT_DIR}/app/" "${INSTALL_DIR}/"
rsync -av "${SCRIPT_DIR}/alembic/" "${INSTALL_DIR}/alembic/" 2>/dev/null || cp -r "${SCRIPT_DIR}/alembic/" "${INSTALL_DIR}/"
cp "${SCRIPT_DIR}/alembic.ini" "${INSTALL_DIR}/"
cp "${SCRIPT_DIR}/requirements.txt" "${INSTALL_DIR}/"

# Copier les outils d'initialisation (si présents)
if [ -d "${SCRIPT_DIR}/tools" ]; then
    rsync -av "${SCRIPT_DIR}/tools/" "${INSTALL_DIR}/tools/" 2>/dev/null || cp -r "${SCRIPT_DIR}/tools/" "${INSTALL_DIR}/"
    echo "✅ Outils d'initialisation copiés"
fi

# Copier init_db.py (si présent)
if [ -f "${SCRIPT_DIR}/init_db.py" ]; then
    cp "${SCRIPT_DIR}/init_db.py" "${INSTALL_DIR}/"
    echo "✅ Script d'initialisation de la base de données copié"
fi

# Copier les dépendances Python 3.13
echo ""
echo "📦 Copie des dépendances Python 3.13..."
cp -r "${DEPS_DIR}" "${INSTALL_DIR}/dependencies-py313"

# Créer l'environnement virtuel Python 3.13
echo ""
echo "🐍 Création de l'environnement virtuel Python 3.13..."
${PYTHON_BIN} -m venv "${INSTALL_DIR}/venv"

# Installer les dépendances depuis le cache local
echo ""
echo "📦 Installation des dépendances Python (mode hors-ligne)..."
"${INSTALL_DIR}/venv/bin/pip" install --upgrade pip setuptools wheel --no-index --find-links="${INSTALL_DIR}/dependencies-py313" || true
"${INSTALL_DIR}/venv/bin/pip" install --no-index --find-links="${INSTALL_DIR}/dependencies-py313" -r "${INSTALL_DIR}/requirements.txt"

# Vérifier l'installation
echo ""
echo "✅ Vérification de l'installation..."
"${INSTALL_DIR}/venv/bin/python" -c "import sys; print(f'Python: {sys.version}')"
"${INSTALL_DIR}/venv/bin/python" -c "import fastapi; print(f'FastAPI: {fastapi.__version__}')"
"${INSTALL_DIR}/venv/bin/python" -c "import sqlmodel; print(f'SQLModel: {sqlmodel.__version__}')"
"${INSTALL_DIR}/venv/bin/python" -c "import uvicorn; print(f'Uvicorn: {uvicorn.__version__}')"
"${INSTALL_DIR}/venv/bin/python" -c "import cryptography; print(f'Cryptography: {cryptography.__version__}')"
"${INSTALL_DIR}/venv/bin/python" -c "import sqlite3; print(f'SQLite: {sqlite3.sqlite_version}')"

# Copier le fichier de configuration exemple
echo ""
echo "⚙️  Configuration..."
cat > "${INSTALL_DIR}/.env.example" << 'EOF'
# MedData Bridge - Configuration Production (SQLite)
# Copier ce fichier vers .env et adapter les valeurs

# Database - SQLite (fichier local)
DATABASE_URL=sqlite:///${INSTALL_DIR}/data/meddata.db

# Security - IMPORTANT : Générer des clés aléatoires
SECRET_KEY=CHANGEME_GENERATE_RANDOM_KEY_HERE
JWT_SECRET_KEY=CHANGEME_GENERATE_JWT_SECRET_KEY_HERE

# Logging
LOG_LEVEL=INFO

# Optional: Sentry monitoring
# SENTRY_DSN=https://...
EOF

# Générer automatiquement un fichier .env avec des clés sécurisées
echo ""
echo "🔐 Génération du fichier .env avec clés sécurisées..."
SECRET_KEY=$(${PYTHON_BIN} -c "import secrets; print(secrets.token_hex(32))")
JWT_SECRET_KEY=$(${PYTHON_BIN} -c "import secrets; print(secrets.token_hex(32))")

cat > "${INSTALL_DIR}/.env" << EOF
# MedData Bridge - Configuration Production (SQLite)
# Généré automatiquement le $(date)

# Database - SQLite (fichier local)
DATABASE_URL=sqlite:///${INSTALL_DIR}/data/meddata.db

# Security - Clés générées automatiquement
SECRET_KEY=${SECRET_KEY}
JWT_SECRET_KEY=${JWT_SECRET_KEY}

# Logging
LOG_LEVEL=INFO
EOF

echo "✅ Fichier .env créé avec clés sécurisées"

# Créer le fichier de service systemd (compatible RHEL 7.9)
echo ""
echo "🔧 Création du service systemd..."
cat > /etc/systemd/system/meddata-bridge.service << EOF
[Unit]
Description=MedData Bridge - HL7 to FHIR Gateway (Python 3.13)
After=network.target

[Service]
# Use simple so systemd doesn't expect sd_notify from uvicorn
Type=simple
User=${SERVICE_USER}
Group=${SERVICE_USER}
WorkingDirectory=${INSTALL_DIR}

# Variables d'environnement
Environment="PATH=${INSTALL_DIR}/venv/bin:/usr/local/bin:/usr/bin"
EnvironmentFile=${INSTALL_DIR}/.env

# Commande de démarrage
ExecStart=${INSTALL_DIR}/venv/bin/uvicorn app.app:app --host 0.0.0.0 --port 8000

# Redémarrages
Restart=always
RestartSec=10
TimeoutStartSec=120
TimeoutStopSec=30

# Logs
StandardOutput=journal
StandardError=journal
SyslogIdentifier=meddata-bridge

# Sécurité (compatible RHEL 7)
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

# Définir les permissions
echo ""
echo "🔒 Configuration des permissions..."
chown -R "${SERVICE_USER}:${SERVICE_USER}" "${INSTALL_DIR}"
chown -R "${SERVICE_USER}:${SERVICE_USER}" /var/log/meddata-bridge
chmod 750 "${INSTALL_DIR}"
chmod 600 "${INSTALL_DIR}/.env"
chmod 644 "${INSTALL_DIR}/.env.example"

# Recharger systemd
systemctl daemon-reload
echo "✅ Service systemd configuré"

# Initialiser la base de données
echo ""
echo "💾 Initialisation de la base de données..."
if [ -f "${INSTALL_DIR}/init_db.py" ]; then
    echo "Exécution de init_db.py..."
    sudo -u "${SERVICE_USER}" "${INSTALL_DIR}/venv/bin/python" "${INSTALL_DIR}/init_db.py" --skip-population || {
        echo "⚠️  Erreur lors de l'initialisation, continuons..."
    }
    
    # Marquer les migrations comme appliquées
    echo "Marquage des migrations Alembic..."
    cd "${INSTALL_DIR}"
    sudo -u "${SERVICE_USER}" "${INSTALL_DIR}/venv/bin/alembic" stamp head || {
        echo "⚠️  Erreur Alembic, continuons..."
    }
    echo "✅ Base de données initialisée"
else
    echo "⚠️  init_db.py non trouvé, initialisation manuelle requise"
fi

echo ""
echo "==================================="
echo "✅ Installation terminée avec succès!"
echo "==================================="
echo ""
echo "📊 Résumé de l'installation:"
echo "   • Application: ${INSTALL_DIR}"
echo "   • Python: ${python_version}"
echo "   • Base de données: ${INSTALL_DIR}/data/meddata.db"
echo "   • Configuration: ${INSTALL_DIR}/.env"
echo "   • Service: meddata-bridge.service"
echo ""
echo "📋 Prochaines étapes:"
echo ""
echo "1. Démarrer le service:"
echo "   sudo systemctl enable meddata-bridge"
echo "   sudo systemctl start meddata-bridge"
echo "   sudo systemctl status meddata-bridge"
echo ""
echo "2. Vérifier que le port 8000 écoute:"
echo "   sudo netstat -tlnp | grep :8000"
echo ""
echo "3. Tester l'application:"
echo "   curl http://localhost:8000/"
echo ""
echo "4. Voir les logs:"
echo "   sudo journalctl -u meddata-bridge -f"
echo ""
echo "5. (Optionnel) Installer Nginx:"
echo "   cd ${SCRIPT_DIR}/scripts"
echo "   sudo ./install_nginx.sh"
echo ""
echo "🔐 Clés de sécurité générées automatiquement dans ${INSTALL_DIR}/.env"
echo "🌐 URL: http://localhost:8000"
echo "📖 Documentation API: http://localhost:8000/docs"
