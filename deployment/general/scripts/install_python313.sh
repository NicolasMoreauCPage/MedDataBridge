#!/bin/bash
#
# Script d'installation de Python 3.13.0 sur RHEL 7.9
# Compatible avec systèmes sans accès Internet
#

set -e

echo "=========================================="
echo "Installation de Python 3.13.0 sur RHEL 7.9"
echo "=========================================="

# Vérifier si Python 3.13 est déjà installé
if [ -x "/usr/local/bin/python3.13" ]; then
    CURRENT_VERSION=$(/usr/local/bin/python3.13 --version 2>&1 | awk '{print $2}')
    echo "✓ Python $CURRENT_VERSION est déjà installé"
    echo "  Emplacement: /usr/local/bin/python3.13"
    exit 0
fi

echo ""
echo "Étape 1: Installation des dépendances de compilation"
echo "------------------------------------------------------"

echo "Installation de Development Tools..."
sudo yum groupinstall -y "Development Tools" || {
    echo "⚠ Erreur lors de l'installation de Development Tools, tentative avec packages individuels..."
    sudo yum install -y gcc gcc-c++ make patch autoconf automake libtool
}

echo "Installation des bibliothèques de développement..."
sudo yum install -y \
    openssl-devel \
    bzip2-devel \
    libffi-devel \
    xz-devel \
    ncurses-devel \
    readline-devel \
    gdbm-devel \
    zlib-devel \
    tk-devel \
    libuuid-devel || {
    echo "❌ Erreur lors de l'installation des dépendances de base"
    exit 1
}

echo ""
echo "⚠️  CRITIQUE: Vérification de la version OpenSSL"
echo "------------------------------------------------------"
if ! rpm -q openssl-devel >/dev/null 2>&1; then
    echo "❌ ERREUR: openssl-devel n'est pas installé!"
    exit 1
fi

OPENSSL_VERSION=$(openssl version | awk '{print $2}')
echo "OpenSSL version installée: ${OPENSSL_VERSION}"

# Python 3.13 requires OpenSSL 1.1.1 or newer
if [[ "${OPENSSL_VERSION}" =~ ^1\.0\. ]]; then
    echo ""
    echo "❌❌❌ ERREUR CRITIQUE ❌❌❌"
    echo ""
    echo "OpenSSL ${OPENSSL_VERSION} est trop ancien!"
    echo "Python 3.13 nécessite OpenSSL 1.1.1 ou plus récent."
    echo ""
    echo "RHEL 7.9 fournit OpenSSL 1.0.2 par défaut."
    echo ""
    echo "SOLUTIONS:"
    echo ""
    echo "Option 1 (RECOMMANDÉ): Compiler OpenSSL 1.1.1 depuis les sources"
    echo "  cd /usr/src"
    echo "  wget https://www.openssl.org/source/openssl-1.1.1w.tar.gz"
    echo "  tar xzf openssl-1.1.1w.tar.gz"
    echo "  cd openssl-1.1.1w"
    echo "  ./config --prefix=/usr/local/openssl --openssldir=/usr/local/openssl shared zlib"
    echo "  make -j\$(nproc)"
    echo "  sudo make install"
    echo "  echo '/usr/local/openssl/lib' | sudo tee /etc/ld.so.conf.d/openssl-1.1.1.conf"
    echo "  sudo ldconfig"
    echo ""
    echo "Option 2: Utiliser Python 3.8 (fourni avec RHEL 7.9)"
    echo "  yum install python38 python38-devel"
    echo ""
    echo "Option 3: Mettre à niveau vers RHEL 8+ (OpenSSL 1.1.1 par défaut)"
    echo ""
    exit 1
fi

echo "✓ OpenSSL ${OPENSSL_VERSION} compatible avec Python 3.13"

echo ""
echo "⚠️  CRITIQUE: Installation de sqlite-devel (requis pour la base de données)"
sudo yum install -y sqlite-devel || {
    echo ""
    echo "❌ ERREUR CRITIQUE: sqlite-devel n'a pas pu être installé!"
    echo ""
    echo "Sans sqlite-devel, Python ne pourra pas utiliser SQLite."
    echo "MedDataBridge nécessite SQLite pour fonctionner."
    echo ""
    echo "Vérifiez votre configuration yum et réessayez."
    exit 1
}

# Vérifier que sqlite-devel est bien installé
if rpm -q sqlite-devel >/dev/null 2>&1; then
    SQLITE_VERSION=$(rpm -q --queryformat '%{VERSION}' sqlite-devel)
    echo "✓ sqlite-devel ${SQLITE_VERSION} installé"
else
    echo "❌ sqlite-devel non trouvé après installation!"
    exit 1
fi

echo "✓ Toutes les dépendances installées"

echo ""
echo "Étape 2: Vérification de la source Python 3.13.0"
echo "------------------------------------------------------"

PYTHON_VERSION="3.13.9"
PYTHON_TAR="Python-${PYTHON_VERSION}.tgz"
PYTHON_DIR="Python-${PYTHON_VERSION}"

# Vérifier si le fichier existe dans le répertoire courant ou /tmp
if [ -f "${PYTHON_TAR}" ]; then
    PYTHON_SOURCE="${PYTHON_TAR}"
elif [ -f "/tmp/${PYTHON_TAR}" ]; then
    PYTHON_SOURCE="/tmp/${PYTHON_TAR}"
elif [ -f "/tmp/Deploiement/${PYTHON_TAR}" ]; then
    PYTHON_SOURCE="/tmp/Deploiement/${PYTHON_TAR}"
else
    echo "⚠ ${PYTHON_TAR} non trouvé localement"
    echo "Tentative de téléchargement depuis python.org..."
    
    cd /tmp
    wget https://www.python.org/ftp/python/${PYTHON_VERSION}/${PYTHON_TAR} || {
        echo ""
        echo "❌ Impossible de télécharger Python ${PYTHON_VERSION}"
        echo ""
        echo "SOLUTION: Téléchargez manuellement le fichier depuis un poste avec Internet:"
        echo "  URL: https://www.python.org/ftp/python/${PYTHON_VERSION}/${PYTHON_TAR}"
        echo "  Puis copiez-le dans /tmp/ sur ce serveur"
        exit 1
    }
    PYTHON_SOURCE="/tmp/${PYTHON_TAR}"
fi

echo "✓ Source trouvée: ${PYTHON_SOURCE}"

echo ""
echo "Étape 3: Extraction et compilation de Python ${PYTHON_VERSION}"
echo "------------------------------------------------------"

cd /usr/src
sudo tar xzf "${PYTHON_SOURCE}"
cd "${PYTHON_DIR}"

echo "Configuration..."
# Détecter si OpenSSL 1.1.1 est dans /usr/local/openssl
if [ -d "/usr/local/openssl" ]; then
    echo "✓ OpenSSL 1.1.1 détecté dans /usr/local/openssl"
    OPENSSL_FLAGS="--with-openssl=/usr/local/openssl"
    export LDFLAGS="-L/usr/local/openssl/lib -Wl,-rpath,/usr/local/openssl/lib"
    export CPPFLAGS="-I/usr/local/openssl/include"
    export PKG_CONFIG_PATH="/usr/local/openssl/lib/pkgconfig:${PKG_CONFIG_PATH}"
else
    echo "✓ Utilisation d'OpenSSL système"
    OPENSSL_FLAGS="--with-openssl=/usr"
fi

# Détecter si SQLite est dans /usr/local
if [ -f "/usr/local/lib/pkgconfig/sqlite3.pc" ]; then
    echo "✓ SQLite personnalisé détecté dans /usr/local"
    export LDFLAGS="${LDFLAGS} -L/usr/local/lib -Wl,-rpath,/usr/local/lib"
    export CPPFLAGS="${CPPFLAGS} -I/usr/local/include"
    export PKG_CONFIG_PATH="/usr/local/lib/pkgconfig:${PKG_CONFIG_PATH}"
fi

sudo -E ./configure \
    --enable-optimizations \
    --enable-loadable-sqlite-extensions \
    --with-system-ffi \
    --with-ensurepip=install \
    ${OPENSSL_FLAGS} || {
    echo "❌ Erreur lors de la configuration"
    exit 1
}

echo "Compilation (cela peut prendre 10-15 minutes)..."
sudo make -j$(nproc) || {
    echo "❌ Erreur lors de la compilation"
    exit 1
}

echo "Installation..."
sudo make altinstall || {
    echo "❌ Erreur lors de l'installation"
    exit 1
}

echo "✓ Python ${PYTHON_VERSION} compilé et installé"

echo ""
echo "Étape 4: Vérification de l'installation"
echo "------------------------------------------------------"

INSTALLED_VERSION=$(/usr/local/bin/python3.13 --version 2>&1)
echo "✓ ${INSTALLED_VERSION} installé avec succès"

# Vérifier SSL (CRITIQUE)
echo ""
echo "Vérification CRITIQUE du module SSL..."
if /usr/local/bin/python3.13 -c "import ssl; print(ssl.OPENSSL_VERSION)" >/dev/null 2>&1; then
    OPENSSL_VERSION=$(/usr/local/bin/python3.13 -c "import ssl; print(ssl.OPENSSL_VERSION)" 2>&1)
    echo "✓ Module SSL activé: ${OPENSSL_VERSION}"
else
    echo ""
    echo "❌❌❌ ERREUR CRITIQUE ❌❌❌"
    echo ""
    echo "Python 3.13 a été compilé mais le module SSL (_ssl) n'est PAS disponible!"
    echo ""
    echo "Cela signifie qu'OpenSSL 1.1.1+ n'était pas détectable lors de la compilation."
    echo "Uvicorn et la plupart des applications web nécessitent SSL."
    echo ""
    echo "SOLUTION:"
    echo "  1. Installer ou compiler OpenSSL 1.1.1+"
    echo "  2. Nettoyer et recompiler Python:"
    echo "     cd /usr/src/Python-${PYTHON_VERSION}"
    echo "     sudo make distclean"
    echo "     sudo ./configure --with-openssl=/usr/local/openssl [...autres flags]"
    echo "     sudo make -j\$(nproc)"
    echo "     sudo make altinstall"
    echo ""
    exit 1
fi

# Vérifier SQLite (CRITIQUE)
echo ""
echo "Vérification CRITIQUE du support SQLite..."
if /usr/local/bin/python3.13 -c "import sqlite3; print(sqlite3.sqlite_version)" >/dev/null 2>&1; then
    SQLITE_VERSION=$(/usr/local/bin/python3.13 -c "import sqlite3; print(sqlite3.sqlite_version)" 2>&1)
    echo "✓ SQLite ${SQLITE_VERSION} activé"
else
    echo ""
    echo "❌❌❌ ERREUR CRITIQUE ❌❌❌"
    echo ""
    echo "Python 3.13 a été compilé mais SQLite n'est PAS disponible!"
    echo ""
    echo "Cela signifie que SQLite 3.15.2+ n'était pas détectable lors de la compilation."
    echo ""
    echo "SOLUTION:"
    echo "  1. Vérifier SQLite >= 3.15.2 est disponible"
    echo "  2. Nettoyer et recompiler Python:"
    echo "     cd /usr/src/Python-${PYTHON_VERSION}"
    echo "     sudo make distclean"
    echo "     sudo ./configure --enable-loadable-sqlite-extensions [...autres flags]"
    echo "     sudo make -j\$(nproc)"
    echo "     sudo make altinstall"
    echo ""
    exit 1
fi

# Vérifier pip
PIP_VERSION=$(/usr/local/bin/python3.13 -m pip --version 2>&1 | awk '{print $2}')
echo "✓ pip ${PIP_VERSION} installé"

echo ""
echo "=========================================="
echo "✅ Installation terminée avec succès !"
echo "=========================================="
echo ""
echo "Python installé dans: /usr/local/bin/python3.13"
echo "pip installé dans: /usr/local/bin/pip3.13"
echo ""
echo "Prochaine étape: Réinstaller MedDataBridge avec Python 3.13"
