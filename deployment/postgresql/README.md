# IntegraSanté - Guide de Déploiement Production
## Serveur Fedora 7.9 sans connexion Internet

---

## 📋 Vue d'ensemble

Ce package contient tout le nécessaire pour déployer IntegraSanté sur un serveur Fedora 7.9 **sans connexion Internet** avec Python 3.8.

### Prérequis serveur
- ✅ Fedora 7.9
- ✅ Python 3.8+ installé
- ✅ PostgreSQL 12+ (recommandé) ou SQLite
- ✅ Accès root (sudo)

---

## 🚀 Procédure de déploiement

### ÉTAPE 1 : Sur la machine de développement (avec Internet)

#### 1.1 Télécharger les dépendances Python

```bash
cd deployment/scripts
./download_dependencies.sh
```

Ce script va télécharger tous les packages Python (wheels + sources) dans `deployment/dependencies/`.

⚠️ **Important pour les dépendances crypto** : Le script télécharge les wheels `manylinux` qui sont compatibles avec Fedora. Si certains packages n'ont pas de wheels, les sources seront téléchargées pour compilation sur le serveur.

#### 1.2 Préparer le package complet

```bash
./prepare_deployment.sh
```

Cela va :
- Copier le code de l'application (sans tests/dev)
- Copier les migrations Alembic
- Créer un fichier VERSION.txt
- Exclure tous les fichiers inutiles (.git, .venv, *.pyc, etc.)

#### 1.3 Créer l'archive de déploiement

```bash
cd ../..
tar -czf meddata-bridge-deploy.tar.gz deployment/
```

#### 1.4 Transférer vers le serveur

```bash
# Via SCP
scp meddata-bridge-deploy.tar.gz user@serveur-fedora:/tmp/

# Ou via clé USB si pas de réseau
cp meddata-bridge-deploy.tar.gz /media/usb/
```

---

### ÉTAPE 2 : Sur le serveur Fedora (sans Internet)

#### 2.1 Extraire l'archive

```bash
cd /tmp
tar -xzf meddata-bridge-deploy.tar.gz
cd deployment
```

#### 2.2 Installer PostgreSQL (si pas déjà fait)

```bash
sudo dnf install postgresql-server postgresql-contrib
sudo postgresql-setup --initdb
sudo systemctl enable postgresql
sudo systemctl start postgresql
```

#### 2.3 Créer la base de données

```bash
sudo -u postgres psql << EOF
CREATE USER meddata WITH PASSWORD 'VotreMotDePasseSecurise';
CREATE DATABASE meddata_bridge OWNER meddata;
GRANT ALL PRIVILEGES ON DATABASE meddata_bridge TO meddata;
\q
EOF
```

#### 2.4 Configurer PostgreSQL pour connexions locales

Éditer `/var/lib/pgsql/data/pg_hba.conf` :

```bash
sudo vi /var/lib/pgsql/data/pg_hba.conf
```

Ajouter/modifier :
```
# TYPE  DATABASE        USER            ADDRESS                 METHOD
local   meddata_bridge  meddata                                 md5
host    meddata_bridge  meddata         127.0.0.1/32            md5
host    meddata_bridge  meddata         ::1/128                 md5
```

Redémarrer PostgreSQL :
```bash
sudo systemctl restart postgresql
```

#### 2.5 Lancer l'installation

```bash
cd scripts
sudo ./install_on_server.sh
```

Ce script va :
- ✅ Créer l'utilisateur système `meddata`
- ✅ Installer l'application dans `/opt/meddata-bridge/`
- ✅ Créer un environnement virtuel Python
- ✅ Installer TOUTES les dépendances en mode hors-ligne
- ✅ Créer le service systemd
- ✅ Configurer les permissions

#### 2.6 Configurer l'application

```bash
cd /opt/meddata-bridge/config
sudo cp .env.example .env
sudo vi .env
```

Exemple de configuration `.env` :

```bash
# Database
DB_TYPE=postgresql
DB_HOST=localhost
DB_PORT=5432
DB_USER=meddata
DB_PASSWORD=VotreMotDePasseSecurise
DB_NAME=meddata_bridge

# Application
APP_HOST=0.0.0.0
APP_PORT=8000
APP_WORKERS=4

# Security (générer des clés aléatoires!)
SECRET_KEY=$(openssl rand -hex 32)
JWT_SECRET_KEY=$(openssl rand -hex 32)

# Logging
LOG_LEVEL=INFO
LOG_FILE=/var/log/meddata-bridge/app.log
```

**Générer des clés sécurisées** :
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

#### 2.7 Initialiser la base de données

```bash
cd /opt/meddata-bridge
sudo -u meddata ./venv/bin/alembic upgrade head
```

#### 2.8 Démarrer le service

```bash
sudo systemctl enable meddata-bridge
sudo systemctl start meddata-bridge
sudo systemctl status meddata-bridge
```

#### 2.9 Vérifier les logs

```bash
# Logs systemd
sudo journalctl -u meddata-bridge -f

# Logs application
sudo tail -f /var/log/meddata-bridge/app.log
```

---

## 🧪 Vérification du déploiement

### Test de connexion

```bash
curl http://localhost:8000
```

Devrait retourner la page d'accueil HTML.

### Test API

```bash
curl http://localhost:8000/api-docs
```

### Test base de données

```bash
sudo -u meddata /opt/meddata-bridge/venv/bin/python3 << 'EOF'
from app.db import get_engine
engine = get_engine()
with engine.connect() as conn:
    result = conn.execute("SELECT COUNT(*) FROM alembic_version")
    print(f"✅ Base de données accessible - version Alembic: {result.scalar()}")
EOF
```

---

## 🔥 Configuration Firewall (si nécessaire)

```bash
# Ouvrir le port 8000
sudo firewall-cmd --permanent --add-port=8000/tcp
sudo firewall-cmd --reload

# Ou pour accès externe via proxy (nginx)
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --permanent --add-service=https
sudo firewall-cmd --reload
```

---

## 🔄 Mise à jour de l'application

Pour mettre à jour l'application :

1. Sur la machine de dev : préparer un nouveau package
2. Transférer sur le serveur
3. Exécuter :

```bash
sudo systemctl stop meddata-bridge

cd /opt/meddata-bridge
sudo -u meddata ./venv/bin/pip install --no-index --find-links=/tmp/deployment/dependencies --upgrade -r /tmp/deployment/requirements-production.txt

# Copier les nouveaux fichiers
sudo rsync -av /tmp/deployment/app/ /opt/meddata-bridge/app/
sudo rsync -av /tmp/deployment/alembic/ /opt/meddata-bridge/alembic/

# Migrations
sudo -u meddata ./venv/bin/alembic upgrade head

sudo systemctl start meddata-bridge
```

---

## 🐛 Dépannage

### Service ne démarre pas

```bash
# Vérifier les erreurs
sudo journalctl -u meddata-bridge -n 50 --no-pager

# Vérifier les permissions
ls -la /opt/meddata-bridge/

# Tester manuellement
sudo -u meddata /opt/meddata-bridge/venv/bin/python3 -m app.app
```

### Erreur de connexion PostgreSQL

```bash
# Tester la connexion
sudo -u meddata psql -h localhost -U meddata -d meddata_bridge

# Vérifier pg_hba.conf
sudo cat /var/lib/pgsql/data/pg_hba.conf | grep meddata

# Voir les logs PostgreSQL
sudo tail -f /var/lib/pgsql/data/log/postgresql-*.log
```

### Problème de dépendances Python

```bash
# Lister les packages installés
/opt/meddata-bridge/venv/bin/pip list

# Réinstaller depuis le cache
cd /tmp/deployment
/opt/meddata-bridge/venv/bin/pip install --no-index --find-links=dependencies -r requirements-production.txt --force-reinstall
```

### Erreur cryptography

Si `cryptography` ne s'installe pas :

```bash
# Installer les outils de compilation
sudo dnf install gcc python3-devel libffi-devel openssl-devel

# Réinstaller cryptography depuis les sources
cd /tmp/deployment/dependencies
/opt/meddata-bridge/venv/bin/pip install --no-index --find-links=. cryptography
```

---

## 📊 Monitoring

### Vérifier l'état du service

```bash
sudo systemctl status meddata-bridge
```

### Logs en temps réel

```bash
sudo journalctl -u meddata-bridge -f
```

### Statistiques système

```bash
# CPU et mémoire
ps aux | grep uvicorn

# Connexions réseau
sudo ss -tlnp | grep :8000
```

---

## 🔒 Sécurité

### Recommandations production

1. **Firewall** : Limiter l'accès au port 8000 (ou utiliser un reverse proxy)
2. **SELinux** : Vérifier la configuration SELinux si activé
3. **Certificats SSL** : Utiliser nginx/Apache avec Let's Encrypt
4. **Sauvegardes** : Configurer des sauvegardes automatiques PostgreSQL
5. **Monitoring** : Installer Sentry pour le tracking d'erreurs

### Sauvegarde de la base

```bash
# Backup quotidien
sudo -u postgres pg_dump meddata_bridge > /backup/meddata_$(date +%Y%m%d).sql

# Restauration
sudo -u postgres psql meddata_bridge < /backup/meddata_20251210.sql
```

---

## 📞 Support

En cas de problème, vérifier :
1. `VERSION.txt` pour la version déployée
2. Logs dans `/var/log/meddata-bridge/`
3. Journaux systemd : `journalctl -u meddata-bridge`
4. Configuration : `/opt/meddata-bridge/config/.env`

---

## ✅ Checklist de déploiement

- [ ] PostgreSQL installé et configuré
- [ ] Base de données créée
- [ ] Package transféré sur le serveur
- [ ] Script `install_on_server.sh` exécuté
- [ ] Fichier `.env` configuré avec mots de passe sécurisés
- [ ] Migrations Alembic appliquées
- [ ] Service systemd activé et démarré
- [ ] Firewall configuré si nécessaire
- [ ] Tests de connexion réussis
- [ ] Logs sans erreurs

**✅ Déploiement terminé !**
