#!/bin/bash
#
# Script d'installation et configuration de Nginx
# À exécuter sur le serveur APRÈS install_on_server.sh
#
# Usage: sudo ./install_nginx.sh
#

set -e

if [ "$EUID" -ne 0 ]; then 
    echo "⚠️  Ce script doit être exécuté en tant que root (sudo)"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && cd .. && pwd)"
NGINX_CONF_SOURCE="${SCRIPT_DIR}/config/nginx-meddata-bridge.conf"
NGINX_CONF_DEST="/etc/nginx/conf.d/meddata-bridge.conf"

echo "==================================="
echo "MedData Bridge - Installation Nginx"
echo "==================================="
echo ""

# Vérifier si Nginx est installé
if ! command -v nginx &> /dev/null; then
    echo "📦 Installation de Nginx..."
    dnf install -y nginx
    echo "✅ Nginx installé"
else
    nginx_version=$(nginx -v 2>&1)
    echo "✅ Nginx déjà installé: ${nginx_version}"
fi

# Copier la configuration
echo ""
echo "📝 Installation de la configuration..."
if [ -f "${NGINX_CONF_SOURCE}" ]; then
    cp "${NGINX_CONF_SOURCE}" "${NGINX_CONF_DEST}"
    echo "✅ Configuration copiée vers ${NGINX_CONF_DEST}"
else
    echo "❌ Fichier de configuration source non trouvé: ${NGINX_CONF_SOURCE}"
    exit 1
fi

# Demander le mode de configuration
echo ""
echo "🔧 Choisissez le mode de configuration:"
echo ""
echo "1) HTTP simple (port 80) - Accès immédiat"
echo "2) HTTPS avec certificats (port 443) - Production sécurisée"
echo "3) Accès par IP uniquement (sans nom de domaine)"
echo ""
read -p "Votre choix [1-3]: " mode_choice

case $mode_choice in
    1)
        echo ""
        echo "✅ Mode HTTP simple sélectionné"
        echo "La configuration par défaut est déjà en HTTP (port 80)"
        ;;
    2)
        echo ""
        read -p "Nom de domaine (ex: meddata.example.com): " domain_name
        
        # Remplacer le server_name
        sed -i "s/server_name meddata.example.com;/server_name ${domain_name};/" "${NGINX_CONF_DEST}"
        
        echo ""
        echo "⚠️  Pour activer HTTPS, vous devez:"
        echo "1. Obtenir des certificats SSL (Let's Encrypt recommandé)"
        echo "2. Décommenter la section HTTPS dans ${NGINX_CONF_DEST}"
        echo "3. Mettre à jour les chemins des certificats"
        echo ""
        echo "📚 Guide Let's Encrypt:"
        echo "   dnf install certbot python3-certbot-nginx"
        echo "   certbot --nginx -d ${domain_name}"
        ;;
    3)
        echo ""
        echo "✅ Mode accès par IP sélectionné"
        echo "Décommentez la section 'OPTION 3' dans ${NGINX_CONF_DEST}"
        echo "Et commentez la section 'OPTION 1'"
        ;;
    *)
        echo "❌ Choix invalide"
        exit 1
        ;;
esac

# Tester la configuration
echo ""
echo "🔍 Test de la configuration Nginx..."
nginx -t

if [ $? -ne 0 ]; then
    echo "❌ Erreur dans la configuration Nginx!"
    exit 1
fi

echo "✅ Configuration Nginx valide"

# Configurer SELinux (si activé)
if command -v getenforce &> /dev/null && [ "$(getenforce)" != "Disabled" ]; then
    echo ""
    echo "🔒 Configuration SELinux..."
    setsebool -P httpd_can_network_connect 1
    echo "✅ SELinux configuré pour permettre les connexions réseau"
fi

# Configurer le firewall
echo ""
echo "🔥 Configuration du firewall..."
if command -v firewall-cmd &> /dev/null; then
    firewall-cmd --permanent --add-service=http
    if [ "$mode_choice" == "2" ]; then
        firewall-cmd --permanent --add-service=https
    fi
    firewall-cmd --reload
    echo "✅ Firewall configuré (ports HTTP ouvert)"
else
    echo "⚠️  firewalld non détecté, configuration manuelle nécessaire"
fi

# Démarrer Nginx
echo ""
echo "🚀 Démarrage de Nginx..."
systemctl enable nginx
systemctl restart nginx

if systemctl is-active --quiet nginx; then
    echo "✅ Nginx démarré avec succès"
else
    echo "❌ Erreur au démarrage de Nginx"
    journalctl -u nginx -n 20 --no-pager
    exit 1
fi

# Vérifier que MedData Bridge est actif
echo ""
echo "🔍 Vérification de MedData Bridge..."
if systemctl is-active --quiet meddata-bridge; then
    echo "✅ MedData Bridge est actif"
else
    echo "⚠️  MedData Bridge n'est pas actif!"
    echo "   Démarrez-le avec: systemctl start meddata-bridge"
fi

echo ""
echo "==================================="
echo "✅ Installation Nginx terminée!"
echo "==================================="
echo ""
echo "📋 Informations:"
echo ""
echo "Configuration: ${NGINX_CONF_DEST}"
echo "Logs accès:    /var/log/nginx/meddata-access.log"
echo "Logs erreurs:  /var/log/nginx/meddata-error.log"
echo ""

# Détecter l'IP du serveur
server_ip=$(hostname -I | awk '{print $1}')
echo "🌐 Accès à l'application:"
if [ "$mode_choice" == "2" ]; then
    echo "   https://${domain_name}"
else
    echo "   http://${server_ip}"
    echo "   ou http://localhost (depuis le serveur)"
fi
echo ""

echo "📝 Commandes utiles:"
echo "   systemctl status nginx          # Statut Nginx"
echo "   systemctl reload nginx          # Recharger config"
echo "   nginx -t                        # Tester config"
echo "   tail -f /var/log/nginx/meddata-access.log  # Logs"
echo ""

echo "🔧 Pour modifier la configuration:"
echo "   vi ${NGINX_CONF_DEST}"
echo "   nginx -t && systemctl reload nginx"
echo ""
