# Checklist de Déploiement MedData Bridge

## ✅ ÉTAPE 1 : Préparation (Machine de développement avec Internet)

### 1.1 Téléchargement des dépendances
```bash
cd Deploiement/scripts
./download_dependencies.sh
```
**Résultat attendu** : ~61 packages dans `Deploiement/dependencies/` (~27 MB)

### 1.2 Préparation du package
```bash
./prepare_deployment.sh
```
**Résultat attendu** : Application copiée dans `Deploiement/app/`

### 1.3 Création de l'archive
```bash
cd ../..
tar -czf meddata-bridge-deploy-$(date +%Y%m%d).tar.gz Deploiement/
```
**Résultat attendu** : Archive `.tar.gz` d'environ 30-40 MB

### 1.4 Transfert vers le serveur
```bash
# Via SCP (si réseau disponible)
scp meddata-bridge-deploy-*.tar.gz user@serveur:/tmp/

# Ou via USB
cp meddata-bridge-deploy-*.tar.gz /media/usb/
```

---

## ✅ ÉTAPE 2 : Installation (Serveur Fedora 7.9 SANS Internet)

### 2.1 Extraction
```bash
cd /tmp
tar -xzf meddata-bridge-deploy-*.tar.gz
cd Deploiement
```

### 2.2 Installation PostgreSQL (si nécessaire)
```bash
sudo dnf install postgresql-server postgresql-contrib
sudo postgresql-setup --initdb
sudo systemctl enable postgresql
sudo systemctl start postgresql
```

### 2.3 Création de la base de données
```bash
sudo -u postgres psql << EOF
CREATE USER meddata WITH PASSWORD 'MotDePasseSecurise';
CREATE DATABASE meddata_bridge OWNER meddata;
GRANT ALL PRIVILEGES ON DATABASE meddata_bridge TO meddata;
\q
EOF
```

### 2.4 Configuration PostgreSQL
Éditer `/var/lib/pgsql/data/pg_hba.conf` :
```
local   meddata_bridge  meddata                                 md5
host    meddata_bridge  meddata         127.0.0.1/32            md5
```

Redémarrer :
```bash
sudo systemctl restart postgresql
```

### 2.5 Installation de l'application
```bash
cd scripts
sudo ./install_on_server.sh
```

**Durée** : 5-10 minutes  
**Résultat** : Application dans `/opt/meddata-bridge/`

### 2.6 Configuration
```bash
cd /opt/meddata-bridge/config
sudo cp .env.example .env
sudo vi .env
```

**Paramètres critiques à modifier** :
- `DB_PASSWORD` : Mot de passe PostgreSQL
- `SECRET_KEY` : Générer avec `python3 -c "import secrets; print(secrets.token_hex(32))"`
- `JWT_SECRET_KEY` : Générer avec `python3 -c "import secrets; print(secrets.token_hex(32))"`

### 2.7 Initialisation de la base
```bash
cd /opt/meddata-bridge
sudo -u meddata ./venv/bin/alembic upgrade head
```

**Résultat attendu** : ~46 tables créées

### 2.8 Démarrage du service
```bash
sudo systemctl enable meddata-bridge
sudo systemctl start meddata-bridge
sudo systemctl status meddata-bridge
```

**État attendu** : `active (running)`

---

## ✅ ÉTAPE 3 : Vérification

### 3.1 Vérification automatique
```bash
cd /tmp/Deploiement/scripts
./verify_installation.sh
```

### 3.2 Tests manuels

#### Test HTTP
```bash
curl http://localhost:8000
```
**Attendu** : Page HTML retournée

#### Test API
```bash
curl http://localhost:8000/api-docs
```
**Attendu** : Documentation Swagger

#### Test base de données
```bash
sudo -u postgres psql meddata_bridge -c "SELECT count(*) FROM alembic_version;"
```
**Attendu** : 1 ligne (version actuelle)

### 3.3 Logs
```bash
# Logs systemd
sudo journalctl -u meddata-bridge -n 50

# Logs application (si configuré)
sudo tail -f /var/log/meddata-bridge/app.log
```

---

## ✅ ÉTAPE 4 : Configuration Firewall (si nécessaire)

```bash
# Ouvrir le port 8000 (accès direct)
sudo firewall-cmd --permanent --add-port=8000/tcp
sudo firewall-cmd --reload

# Ou HTTP/HTTPS (si reverse proxy)
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --permanent --add-service=https
sudo firewall-cmd --reload
```

---

## ✅ ÉTAPE 5 : Configuration Nginx/SSL (optionnel)

Si vous souhaitez un reverse proxy avec SSL :

```bash
# Installer nginx
sudo dnf install nginx

# Copier la config
sudo cp /tmp/Deploiement/config/nginx-meddata-bridge.conf /etc/nginx/conf.d/

# Adapter les certificats SSL dans le fichier
sudo vi /etc/nginx/conf.d/nginx-meddata-bridge.conf

# Tester la config
sudo nginx -t

# Démarrer
sudo systemctl enable nginx
sudo systemctl start nginx
```

---

## 📋 Checklist finale

- [ ] Archive transférée sur le serveur
- [ ] PostgreSQL installé et configuré
- [ ] Base de données `meddata_bridge` créée
- [ ] Utilisateur PostgreSQL `meddata` créé
- [ ] pg_hba.conf configuré
- [ ] Script `install_on_server.sh` exécuté sans erreur
- [ ] Fichier `.env` configuré avec clés sécurisées
- [ ] Migrations Alembic appliquées (46 tables)
- [ ] Service systemd `meddata-bridge` actif
- [ ] Test HTTP réussi (curl localhost:8000)
- [ ] Logs sans erreurs critiques
- [ ] Firewall configuré (si nécessaire)
- [ ] Script `verify_installation.sh` passé avec succès

---

## 🐛 Dépannage rapide

### Service ne démarre pas
```bash
sudo journalctl -u meddata-bridge -n 50 --no-pager
```

### Erreur PostgreSQL
```bash
sudo tail -f /var/lib/pgsql/data/log/postgresql-*.log
```

### Problème de dépendances
```bash
/opt/meddata-bridge/venv/bin/pip list
cd /tmp/Deploiement
/opt/meddata-bridge/venv/bin/pip install --no-index --find-links=dependencies -r requirements-production.txt --force-reinstall
```

### Cryptography ne compile pas
```bash
sudo dnf install gcc python3-devel libffi-devel openssl-devel
cd /tmp/Deploiement/dependencies
/opt/meddata-bridge/venv/bin/pip install --no-index --find-links=. cryptography
```

---

## 📞 Support

**Documentation complète** : `Deploiement/README.md`

**Fichiers importants** :
- Installation : `/opt/meddata-bridge/`
- Configuration : `/opt/meddata-bridge/config/.env`
- Logs : `/var/log/meddata-bridge/`
- Service : `/etc/systemd/system/meddata-bridge.service`
- Version : `/opt/meddata-bridge/VERSION.txt`

**Commandes utiles** :
```bash
# Redémarrer
sudo systemctl restart meddata-bridge

# Voir les logs en direct
sudo journalctl -u meddata-bridge -f

# Status détaillé
sudo systemctl status meddata-bridge -l

# Tester la connexion DB
sudo -u meddata /opt/meddata-bridge/venv/bin/python3 -c "from app.db import get_engine; print('DB OK')"
```

---

**✅ Déploiement réussi si tous les éléments de la checklist sont validés !**
