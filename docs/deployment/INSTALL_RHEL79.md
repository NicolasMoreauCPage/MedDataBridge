# Installation MedDataBridge sur RHEL 7.9 (Offline)

## Prérequis
- RHEL 7.9
- Python 3.8+ installé (confirmé: Python 3.8.18)
- Accès root ou sudo
- 3 fichiers à transférer sur le serveur:
  - `MedDataBridge-linux.zip` (code source)
  - `pip-setuptools-wheel.zip` (pip + outils)
  - `MedDataBridge-packages-complete.zip` (45 dépendances Python pour Linux x86_64)

---

## 1. Transfert des fichiers

Transférer les 3 ZIP sur le serveur (via scp, sftp, USB, etc.) dans `/tmp` ou `/home/votre-utilisateur`:

```bash
# Exemple avec scp (depuis votre machine locale)
scp MedDataBridge-linux.zip user@serveur:/tmp/
scp pip-setuptools-wheel.zip user@serveur:/tmp/
scp MedDataBridge-packages-complete.zip user@serveur:/tmp/
```

---

## 2. Installation sur le serveur RHEL 7.9

### 2.1 Décompression et préparation

```bash
# Se connecter au serveur
ssh user@serveur

# Créer le répertoire d'installation
sudo mkdir -p /opt/meddatabridge
cd /opt/meddatabridge

# Extraire le code source
sudo unzip /tmp/MedDataBridge-linux.zip -d /opt/meddatabridge
cd /opt/meddatabridge

# Créer l'environnement virtuel Python
python3.8 -m venv .venv
source .venv/bin/activate
```

### 2.2 Installation de pip (offline)

```bash
# Extraire et installer pip/setuptools/wheel
cd /tmp
unzip pip-setuptools-wheel.zip -d pip-tools
cd pip-tools

python3.8 -m ensurepip --upgrade || true
python3.8 get-pip.py --no-index --find-links .

# Vérifier
pip --version
```

### 2.3 Installation des dépendances (offline)

```bash
# Extraire les packages Python
mkdir -p /opt/meddatabridge/packages-offline
cd /opt/meddatabridge/packages-offline
unzip /tmp/MedDataBridge-packages-complete.zip

# Activer l'environnement virtuel
cd /opt/meddatabridge
source .venv/bin/activate

# Installer les dépendances depuis les fichiers locaux (45 packages)
pip install --no-index --find-links packages-offline -r requirements-production.txt

# Vérifier l'installation
pip list
python -c "import fastapi, uvicorn, sqlmodel; print('OK')"
```

### 2.4 Configuration de l'application

```bash
cd /opt/meddatabridge

# Créer le fichier de configuration .env
cat > .env << 'EOF'
# Base de données
DATABASE_URL=sqlite:///./meddatabridge.db

# Sécurité (CHANGER LES VALEURS EN PRODUCTION!)
SECRET_KEY=your-very-secret-key-change-me-in-production-min-32-chars
JWT_SECRET_KEY=another-secret-key-for-jwt-tokens-min-32-chars

# JWT Configuration
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Application
APP_NAME=MedDataBridge
APP_VERSION=1.1.0
DEBUG=false
EOF

# Permissions sécurisées pour .env
chmod 600 .env

# Créer le répertoire pour la base de données
mkdir -p data
chmod 750 data
```

### 2.5 Initialisation de la base de données

```bash
# Activer l'environnement virtuel
source .venv/bin/activate

# Initialiser la base de données avec Alembic
python -m alembic upgrade head

# Créer les tables si nécessaire
python init_db.py
```

### 2.6 Test de l'application

```bash
# Test rapide (Ctrl+C pour arrêter)
python -m uvicorn app.app:app --host 0.0.0.0 --port 8000

# Dans un autre terminal, tester:
curl http://localhost:8000
curl http://localhost:8000/health
```

---

## 3. Configuration en production avec systemd

### 3.1 Créer le service systemd

```bash
sudo nano /etc/systemd/system/meddatabridge.service
```

Contenu du fichier:

```ini
[Unit]
Description=MedDataBridge FastAPI Application
After=network.target

[Service]
Type=simple
User=meddatabridge
Group=meddatabridge
WorkingDirectory=/opt/meddatabridge
Environment="PATH=/opt/meddatabridge/.venv/bin"
ExecStart=/opt/meddatabridge/.venv/bin/uvicorn app.app:app --host 0.0.0.0 --port 8000 --workers 4

Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=meddatabridge

[Install]
WantedBy=multi-user.target
```

### 3.2 Créer l'utilisateur système

```bash
# Créer un utilisateur dédié (sans shell)
sudo useradd -r -s /bin/false -d /opt/meddatabridge meddatabridge

# Définir les permissions
sudo chown -R meddatabridge:meddatabridge /opt/meddatabridge
sudo chmod 755 /opt/meddatabridge
```

### 3.3 Démarrer le service

```bash
# Recharger systemd
sudo systemctl daemon-reload

# Activer le service au démarrage
sudo systemctl enable meddatabridge

# Démarrer le service
sudo systemctl start meddatabridge

# Vérifier le statut
sudo systemctl status meddatabridge

# Voir les logs
sudo journalctl -u meddatabridge -f
```

---

## 4. Configuration du pare-feu

```bash
# Ouvrir le port 8000 (si firewalld est actif)
sudo firewall-cmd --permanent --add-port=8000/tcp
sudo firewall-cmd --reload

# Ou avec iptables
sudo iptables -A INPUT -p tcp --dport 8000 -j ACCEPT
sudo service iptables save
```

---

## 5. Configuration Nginx (reverse proxy - optionnel)

### 5.1 Installer Nginx

```bash
# Si disponible dans les repos RHEL ou via EPEL
sudo yum install nginx

# Ou via EPEL
sudo yum install epel-release
sudo yum install nginx
```

### 5.2 Configuration Nginx

```bash
sudo nano /etc/nginx/conf.d/meddatabridge.conf
```

Contenu:

```nginx
server {
    listen 80;
    server_name votre-domaine.com;

    client_max_body_size 100M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```bash
# Tester la configuration
sudo nginx -t

# Démarrer Nginx
sudo systemctl enable nginx
sudo systemctl start nginx
```

---

## 6. Commandes de gestion

### Gestion du service

```bash
# Démarrer
sudo systemctl start meddatabridge

# Arrêter
sudo systemctl stop meddatabridge

# Redémarrer
sudo systemctl restart meddatabridge

# Statut
sudo systemctl status meddatabridge

# Logs en temps réel
sudo journalctl -u meddatabridge -f

# Logs des dernières 100 lignes
sudo journalctl -u meddatabridge -n 100
```

### Mise à jour de l'application

```bash
# Arrêter le service
sudo systemctl stop meddatabridge

# Sauvegarder la base de données
sudo -u meddatabridge cp /opt/meddatabridge/meddatabridge.db /opt/meddatabridge/meddatabridge.db.backup

# Transférer le nouveau ZIP et extraire
sudo unzip /tmp/MedDataBridge-linux-nouveau.zip -d /opt/meddatabridge-new
sudo rsync -av /opt/meddatabridge-new/ /opt/meddatabridge/

# Mettre à jour la base de données si nécessaire
cd /opt/meddatabridge
source .venv/bin/activate
python -m alembic upgrade head

# Redémarrer
sudo systemctl start meddatabridge
```

---

## 7. Vérification de l'installation

### Tests de base

```bash
# Test local
curl http://localhost:8000

# Test depuis une autre machine
curl http://adresse-serveur:8000

# Test des endpoints
curl http://localhost:8000/health
curl http://localhost:8000/docs  # Documentation Swagger
```

### Vérification des logs

```bash
# Logs systemd
sudo journalctl -u meddatabridge -f

# Logs applicatifs (si configurés)
tail -f /opt/meddatabridge/logs/app.log
```

---

## 8. Dépannage

### L'application ne démarre pas

```bash
# Vérifier les logs
sudo journalctl -u meddatabridge -n 100

# Tester manuellement
cd /opt/meddatabridge
source .venv/bin/activate
python -m uvicorn app.app:app --host 0.0.0.0 --port 8000

# Vérifier les permissions
ls -la /opt/meddatabridge
ls -la /opt/meddatabridge/.env
```

### Erreurs de dépendances

```bash
# Vérifier les packages installés
source .venv/bin/activate
pip list

# Réinstaller si nécessaire
pip install --no-index --find-links packages-offline -r requirements-production.txt --force-reinstall
```

### Erreurs de base de données

```bash
# Vérifier la base de données
cd /opt/meddatabridge
source .venv/bin/activate
python -c "from sqlmodel import create_engine; engine = create_engine('sqlite:///./meddatabridge.db'); print('DB OK')"

# Réinitialiser (ATTENTION: efface les données!)
rm meddatabridge.db
python -m alembic upgrade head
python init_db.py
```

---

## 9. Checklist de sécurité

- [ ] Changer les clés secrètes dans `.env`
- [ ] Permissions `.env` à 600
- [ ] Utilisateur système dédié créé
- [ ] Pare-feu configuré
- [ ] DEBUG=false dans `.env`
- [ ] Base de données sauvegardée régulièrement
- [ ] Logs surveillés
- [ ] Nginx HTTPS configuré (optionnel mais recommandé)

---

## Support

Pour plus d'informations:
- Documentation FastAPI: https://fastapi.tiangolo.com/
- Documentation Uvicorn: https://www.uvicorn.org/
- Logs: `sudo journalctl -u meddatabridge -f`
