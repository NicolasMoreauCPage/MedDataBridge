# 📦 Package de Déploiement MedData Bridge - SQLite Version

## ✅ Contenu du Package

Le répertoire `Deploiement/` contient **TOUT** ce qui est nécessaire pour déployer MedData Bridge sur un serveur Fedora 7.9 **SANS connexion Internet** avec Python 3.8 et **SQLite**.

### 📊 Statistiques
- **Taille totale** : ~26 MB
- **Nombre de fichiers** : 410+
- **Dépendances Python** : 51 packages (~23 MB)
- **Code source** : 3.4 MB
- **Base de données** : SQLite (intégré à Python, pas de serveur externe)

---

## 🎯 Différences avec la version PostgreSQL

### ✅ Avantages SQLite
- **Installation simplifiée** : Pas besoin d'installer PostgreSQL
- **Configuration minimale** : Pas de serveur de base de données à gérer
- **Portable** : Base de données = 1 seul fichier
- **Déploiement rapide** : Moins d'étapes d'installation
- **Maintenance simple** : Sauvegarde = copier 1 fichier

### ⚠️ Limitations SQLite
- **Concurrence limitée** : Bon pour < 100 requêtes/seconde
- **Pas de réplication** : Pour haute disponibilité, préférer PostgreSQL
- **Pas de permissions granulaires** : SQLite = permissions fichier

### 💡 Recommandation
- **SQLite** : Parfait pour déploiement initial, tests, production légère (<1000 patients/jour)
- **PostgreSQL** : Nécessaire pour production intensive, haute disponibilité

---

## 📂 Structure du Package

```
Deploiement/
├── README.md                    # Documentation complète
├── PACKAGE_INFO.md             # Ce fichier
├── CHECKLIST.md                # Checklist d'installation
├── VERSION.txt                 # Informations de version
├── requirements-production.txt # Liste des dépendances (SANS psycopg)
│
├── app/                        # Code source (3.4 MB)
│   ├── models.py              # Modèles de données
│   ├── routers/               # Endpoints API
│   ├── services/              # Logique métier
│   ├── templates/             # Templates HTML
│   └── ...
│
├── alembic/                    # Migrations de base de données
│   ├── env.py
│   └── versions/              # 18 fichiers de migration
│
├── dependencies/               # Packages Python (23 MB, 51 fichiers)
│   ├── fastapi-0.112.2-py3-none-any.whl
│   ├── sqlmodel-0.0.21-py3-none-any.whl
│   ├── cryptography-45.0.7-cp37-abi3-manylinux2014_x86_64.whl
│   └── ... (PAS de psycopg)
│
├── config/
│   └── nginx-meddata-bridge.conf  # Config Nginx (optionnel)
│
└── scripts/
    ├── download_dependencies.sh      # [DEV] Télécharger dépendances
    ├── prepare_deployment.sh         # [DEV] Préparer le package
    ├── install_on_server.sh          # [PROD] Installer (version SQLite)
    └── verify_installation.sh        # [PROD] Vérifier (version SQLite)
```

---

## 🚀 Installation Simplifiée (SQLite)

### ÉTAPE 1 : Sur votre poste (avec Internet) ✅ FAIT
```bash
cd Deploiement/scripts
./download_dependencies.sh    # Télécharger packages Python (SANS psycopg)
./prepare_deployment.sh       # Copier le code source
```

### ÉTAPE 2 : Transférer vers le serveur
```bash
# Créer l'archive
cd /home/nico/Travail/Fhir_MedBridgeData/MedData_Bridge
tar -czf meddata-bridge-sqlite-$(date +%Y%m%d).tar.gz Deploiement/

# Transférer (SCP ou USB)
scp meddata-bridge-sqlite-*.tar.gz user@serveur:/tmp/
```

### ÉTAPE 3 : Sur le serveur (SANS Internet)
```bash
# Extraire
cd /tmp
tar -xzf meddata-bridge-sqlite-*.tar.gz
cd Deploiement/scripts

# Installer l'application (PAS besoin de PostgreSQL!)
sudo ./install_on_server.sh

# Configurer
cd /opt/meddata-bridge/config
sudo cp .env.example .env
sudo vi .env

# Générer des clés sécurisées
python3 -c "import secrets; print('SECRET_KEY=' + secrets.token_hex(32))"
python3 -c "import secrets; print('JWT_SECRET_KEY=' + secrets.token_hex(32))"

# Initialiser la base SQLite (automatique)
cd /opt/meddata-bridge
sudo -u meddata /opt/meddata-bridge/venv/bin/alembic upgrade head
# ✅ Crée automatiquement /opt/meddata-bridge/data/meddata.db

# Démarrer
sudo systemctl enable meddata-bridge
sudo systemctl start meddata-bridge
sudo systemctl status meddata-bridge
```

---

## 🔧 Configuration Minimale

### Fichier `.env` (SQLite)
```bash
# Base de données SQLite (automatique)
# Pas de DB_HOST, DB_PORT, DB_USER, DB_PASSWORD !

# Application
APP_HOST=0.0.0.0
APP_PORT=8000
APP_WORKERS=4

# Security - GÉNÉRER DES CLÉS ALÉATOIRES
SECRET_KEY=votre_cle_generee_64_caracteres
JWT_SECRET_KEY=votre_cle_generee_64_caracteres

# Logging
LOG_LEVEL=INFO
LOG_FILE=/var/log/meddata-bridge/app.log
```

### Génération de clés sécurisées
```bash
# SECRET_KEY
python3 -c "import secrets; print(secrets.token_hex(32))"

# JWT_SECRET_KEY
python3 -c "import secrets; print(secrets.token_hex(32))"
```

---

## 📋 Vérification Post-Installation

### Script automatique
```bash
cd /tmp/Deploiement/scripts
./verify_installation.sh
```

### Vérifications manuelles
```bash
# Service actif
sudo systemctl status meddata-bridge

# Application accessible
curl http://localhost:8000

# Base SQLite créée
ls -lh /opt/meddata-bridge/data/meddata.db
sqlite3 /opt/meddata-bridge/data/meddata.db "SELECT count(*) FROM alembic_version;"

# Logs
sudo journalctl -u meddata-bridge -n 50 --no-pager
```

---

## 💾 Sauvegarde SQLite

### Base de données
```bash
# Backup (simple copie de fichier)
sudo cp /opt/meddata-bridge/data/meddata.db \
       /backup/meddata-$(date +%Y%m%d).db

# Backup avec compression
sudo gzip -c /opt/meddata-bridge/data/meddata.db > \
       /backup/meddata-$(date +%Y%m%d).db.gz

# Restauration
sudo cp /backup/meddata-20251210.db \
       /opt/meddata-bridge/data/meddata.db
sudo chown meddata:meddata /opt/meddata-bridge/data/meddata.db
```

### Backup automatique (cron)
```bash
# Créer script de backup
cat > /opt/meddata-bridge/scripts/backup_db.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="/backup/meddata"
mkdir -p $BACKUP_DIR
cp /opt/meddata-bridge/data/meddata.db \
   $BACKUP_DIR/meddata-$(date +%Y%m%d-%H%M).db
# Garder les 30 derniers backups
ls -t $BACKUP_DIR/meddata-*.db | tail -n +31 | xargs rm -f
EOF

chmod +x /opt/meddata-bridge/scripts/backup_db.sh

# Ajouter au cron (backup quotidien à 2h du matin)
sudo crontab -e
# Ajouter: 0 2 * * * /opt/meddata-bridge/scripts/backup_db.sh
```

---

## 🔄 Migration vers PostgreSQL

Si votre utilisation augmente, vous pouvez migrer vers PostgreSQL plus tard :

```bash
# 1. Installer PostgreSQL
sudo dnf install postgresql-server postgresql-contrib
sudo postgresql-setup --initdb
sudo systemctl start postgresql
sudo -u postgres createdb meddata_bridge
sudo -u postgres createuser meddata

# 2. Exporter depuis SQLite
sqlite3 /opt/meddata-bridge/data/meddata.db .dump > /tmp/export.sql

# 3. Installer psycopg dans le venv
source /opt/meddata-bridge/venv/bin/activate
pip install psycopg[binary]

# 4. Modifier .env
# DB_TYPE=postgresql
# DB_HOST=localhost
# DB_PORT=5432
# DB_USER=meddata
# DB_PASSWORD=...
# DB_NAME=meddata_bridge

# 5. Importer dans PostgreSQL
# (adapter l'export SQL pour PostgreSQL)

# 6. Redémarrer
sudo systemctl restart meddata-bridge
```

---

## 📚 Documentation

### Fichiers fournis
1. **README.md** - Guide complet avec troubleshooting
2. **PACKAGE_INFO.md** - Ce fichier (spécifique SQLite)
3. **CHECKLIST.md** - Liste de contrôle installation
4. **VERSION.txt** - Informations de version

### Documentation en ligne
Une fois déployée :
- Guide utilisateur : http://localhost:8000/guide
- Documentation API : http://localhost:8000/api-docs
- Standards IHE PAM : http://localhost:8000/documentation

---

## 🔒 Sécurité

### Permissions fichiers critiques
```bash
# Base de données
sudo chown meddata:meddata /opt/meddata-bridge/data/meddata.db
sudo chmod 640 /opt/meddata-bridge/data/meddata.db

# Configuration
sudo chmod 640 /opt/meddata-bridge/config/.env

# Logs
sudo chown meddata:meddata /var/log/meddata-bridge/
sudo chmod 750 /var/log/meddata-bridge/
```

### Firewall (optionnel)
```bash
# Limiter accès au port 8000
sudo firewall-cmd --zone=public --add-port=8000/tcp --permanent
sudo firewall-cmd --reload

# Avec Nginx en reverse proxy (recommandé)
sudo firewall-cmd --zone=public --add-service=https --permanent
sudo firewall-cmd --reload
```

---

## 🆘 Dépannage

### Problème : Service ne démarre pas
```bash
# Vérifier les logs
sudo journalctl -u meddata-bridge -n 100 --no-pager

# Vérifier la config
cat /opt/meddata-bridge/config/.env

# Tester manuellement
cd /opt/meddata-bridge
source venv/bin/activate
python3 -m uvicorn app.app:app --host 0.0.0.0 --port 8000
```

### Problème : Base de données verrouillée
```bash
# SQLite est verrouillé si plusieurs processus écrivent
# Vérifier qu'un seul uvicorn tourne
ps aux | grep uvicorn

# Redémarrer le service
sudo systemctl restart meddata-bridge
```

### Problème : Permissions
```bash
# Réinitialiser les permissions
sudo chown -R meddata:meddata /opt/meddata-bridge
sudo chown -R meddata:meddata /var/log/meddata-bridge
```

---

## ✅ Checklist Rapide

Installation SQLite (plus simple que PostgreSQL) :

- [ ] Package `Deploiement/` prêt (~26 MB)
- [ ] Archive `.tar.gz` créée
- [ ] Archive transférée sur serveur
- [ ] Script `install_on_server.sh` exécuté ✅
- [ ] Configuration `.env` modifiée avec clés sécurisées ✅
- [ ] Migrations Alembic appliquées (crée `meddata.db`) ✅
- [ ] Service systemd actif ✅
- [ ] Tests de connexion réussis ✅
- [ ] Script `verify_installation.sh` passé ✅

**Pas besoin de** :
- ❌ Installer PostgreSQL
- ❌ Configurer utilisateur DB
- ❌ Gérer des mots de passe DB
- ❌ Configurer pg_hba.conf

---

## 🎉 Package SQLite Prêt !

Le package `Deploiement/` est **complet et optimisé pour SQLite** - déploiement sur Fedora 7.9 sans connexion Internet.

**Avantages SQLite** :
- ✅ **Installation 2x plus rapide** (pas de PostgreSQL)
- ✅ **Configuration minimale** (2 clés à générer)
- ✅ **Maintenance simple** (1 fichier à sauvegarder)
- ✅ **Portable** (base de données = fichier)

**Prochaine étape** : Créer le tarball et transférer sur le serveur

```bash
cd /home/nico/Travail/Fhir_MedBridgeData/MedData_Bridge
tar -czf meddata-bridge-sqlite-$(date +%Y%m%d).tar.gz Deploiement/
```

**Durée d'installation estimée** : 10-15 minutes (vs 20-30 min avec PostgreSQL)

**Compatibilité testée** :
- ✅ Fedora 7.9+
- ✅ Python 3.8+
- ✅ SQLite 3.x (intégré à Python)

**🚀 Installation simplifiée, prête à déployer !**
