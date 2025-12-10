# Checklist de Déploiement - MedDataBridge sur RHEL 7.9

## ✅ Liste de Contrôle Complète

### Étape 0 : Vérifications Préalables (5 minutes)

#### 0.1 Vérifier OpenSSL
```bash
openssl version
```
- ✅ **Si "OpenSSL 1.1.1"** → Passez à l'étape 1
- ❌ **Si "OpenSSL 1.0.2"** → **BLOCKER** : Suivez d'abord `INSTALL_OPENSSL_RHEL79.md`

#### 0.2 Vérifier SQLite
```bash
sqlite3 --version
```
- ✅ **Si >= 3.15.2** → OK
- ❌ **Si 3.7.17** → Le script compilera SQLite 3.15.2 automatiquement

#### 0.3 Vérifier l'espace disque
```bash
df -h /usr/src /opt /tmp
```
- Requis : ~500 MB libres sur chaque partition

#### 0.4 Vérifier les droits
```bash
sudo whoami
# Doit afficher : root
```

---

### Étape 1 : OpenSSL 1.1.1 (10-15 minutes) - **CRITIQUE**

⚠️ **Cette étape est OBLIGATOIRE sur RHEL 7.9**

#### 1.1 Télécharger OpenSSL 1.1.1w
- [ ] Télécharger depuis : https://www.openssl.org/source/openssl-1.1.1w.tar.gz (9.8 MB)
- [ ] Transférer vers `/tmp/` sur le serveur

#### 1.2 Compiler OpenSSL
```bash
cd /usr/src
sudo tar xzf /tmp/openssl-1.1.1w.tar.gz
cd openssl-1.1.1w
sudo yum install -y gcc make perl zlib-devel
sudo ./config --prefix=/usr/local/openssl --openssldir=/usr/local/openssl shared zlib
sudo make -j$(nproc)
sudo make test
sudo make install
echo '/usr/local/openssl/lib' | sudo tee /etc/ld.so.conf.d/openssl-1.1.1.conf
sudo ldconfig
```

#### 1.3 Vérifier OpenSSL
```bash
/usr/local/openssl/bin/openssl version
```
- ✅ **Attendu : "OpenSSL 1.1.1w  11 Sep 2023"**
- ❌ Si erreur → Relire `INSTALL_OPENSSL_RHEL79.md`

---

### Étape 2 : Transférer le Package (2-5 minutes)

#### 2.1 Créer l'archive (sur Windows)
```powershell
cd Deploiement
Compress-Archive -Path * -DestinationPath meddata-bridge-py313-latest.zip -Force
```

#### 2.2 Transférer vers le serveur
```powershell
scp meddata-bridge-py313-latest.zip user@serveur:/tmp/
```

#### 2.3 Extraire sur le serveur
```bash
cd /tmp
unzip meddata-bridge-py313-latest.zip -d /tmp/Deploiement
cd /tmp/Deploiement/scripts
chmod +x *.sh
```

---

### Étape 3 : Installer Python 3.13 (10-15 minutes)

#### 3.1 Lancer le script d'installation
```bash
sudo ./install_python313.sh
```

#### 3.2 Messages à surveiller pendant l'installation

**✅ Messages de succès attendus :**
```
✓ OpenSSL 1.1.1w compatible avec Python 3.13
✓ sqlite-devel 3.7.17 installé
✓ Python 3.13.0 compilé et installé
✓ Module SSL activé: OpenSSL 1.1.1w 11 Sep 2023
✓ SQLite 3.15.2 activé
✓ pip 24.x installé
```

**❌ Erreurs critiques à surveiller :**

1. **"OpenSSL 1.0.2 est trop ancien!"**
   - → Retour à l'étape 1 : Installer OpenSSL 1.1.1w

2. **"Python 3.13 a été compilé mais le module SSL (_ssl) n'est PAS disponible!"**
   - → OpenSSL 1.1.1 non détecté
   - → Vérifier : `ldconfig -p | grep /usr/local/openssl`
   - → Vérifier : `/usr/local/openssl/bin/openssl version`

3. **"Python 3.13 a été compilé mais SQLite n'est PAS disponible!"**
   - → SQLite 3.15.2+ non détecté
   - → Le script doit compiler SQLite automatiquement

#### 3.3 Vérifications Post-Installation
```bash
# Python version
/usr/local/bin/python3.13 --version
# Attendu : Python 3.13.0

# Module SSL (CRITIQUE)
/usr/local/bin/python3.13 -c "import ssl; print(ssl.OPENSSL_VERSION)"
# Attendu : OpenSSL 1.1.1w 11 Sep 2023

# Module SQLite (CRITIQUE)
/usr/local/bin/python3.13 -c "import sqlite3; print(sqlite3.sqlite_version)"
# Attendu : 3.15.2 ou plus

# Module pip
/usr/local/bin/python3.13 -m pip --version
# Attendu : pip 24.x
```

---

### Étape 4 : Installer MedDataBridge (3-5 minutes)

#### 4.1 Lancer le script d'installation
```bash
cd /tmp/Deploiement/scripts
sudo ./install_on_server.sh
```

#### 4.2 Messages à surveiller

**✅ Succès attendu :**
```
✓ Utilisateur meddata créé
✓ Création du répertoire /opt/meddata-bridge
✓ Environnement virtuel créé
✓ Installation des dépendances (70 packages)
✓ Fichier .env généré
✓ Base de données initialisée
✓ Service systemd configuré
✅ Installation terminée avec succès!
```

#### 4.3 Vérifications Post-Installation
```bash
# Structure des fichiers
ls -la /opt/meddata-bridge/
# Doit contenir : app/, venv/, data/, .env, requirements.txt

# Droits utilisateur
ls -l /opt/meddata-bridge/ | head -1
# Doit afficher : drwxr-xr-x meddata meddata

# Environnement virtuel Python
/opt/meddata-bridge/venv/bin/python --version
# Doit afficher : Python 3.13.0

# Configuration .env
cat /opt/meddata-bridge/.env
# Doit contenir : DATABASE_URL, SECRET_KEY, JWT_SECRET_KEY

# Base de données
ls -lh /opt/meddata-bridge/data/meddata.db
# Doit exister avec ~200-500 KB
```

---

### Étape 5 : Démarrer le Service (1 minute)

#### 5.1 Activer le service
```bash
sudo systemctl enable meddata-bridge
sudo systemctl start meddata-bridge
```

#### 5.2 Vérifier le statut
```bash
sudo systemctl status meddata-bridge
```

**✅ Succès attendu :**
```
● meddata-bridge.service - MedData Bridge
   Loaded: loaded (/etc/systemd/system/meddata-bridge.service)
   Active: active (running) since ...
   Main PID: xxxx (python)
```

**❌ Erreurs courantes :**

1. **"Active: failed (Result: exit-code)"**
   ```bash
   # Voir les logs détaillés
   sudo journalctl -u meddata-bridge -n 100 --no-pager
   ```

2. **"ModuleNotFoundError: No module named '_ssl'"**
   - → Python compilé sans OpenSSL 1.1.1
   - → Retour à l'étape 3 : Recompiler Python avec `--with-openssl=/usr/local/openssl`

3. **"ModuleNotFoundError: No module named '_sqlite3'"**
   - → Python compilé sans SQLite 3.15.2+
   - → Retour à l'étape 3 : Compiler SQLite puis recompiler Python

#### 5.3 Vérifier le port
```bash
sudo netstat -tlnp | grep :8000
```
**Attendu :** `LISTEN` sur `0.0.0.0:8000`

#### 5.4 Tester l'application
```bash
curl http://localhost:8000/
```
**Attendu :** Réponse HTML ou JSON (pas d'erreur de connexion)

---

### Étape 6 : Vérifications Finales (2 minutes)

#### 6.1 Tester les endpoints
```bash
# Page d'accueil
curl -I http://localhost:8000/
# Attendu : HTTP/1.1 200 OK

# API Documentation
curl -I http://localhost:8000/docs
# Attendu : HTTP/1.1 200 OK

# Health check
curl http://localhost:8000/health 2>/dev/null || echo "Endpoint /health non disponible (OK si app démarre)"
```

#### 6.2 Vérifier les logs
```bash
# Logs en temps réel
sudo journalctl -u meddata-bridge -f
# Doit afficher : "Application startup complete" ou "Uvicorn running"
```

#### 6.3 Tester depuis un navigateur (si possible)
- Ouvrir : http://[ip-serveur]:8000/
- Ouvrir : http://[ip-serveur]:8000/docs

---

## 📊 Résumé des Composants

| Composant | Version | Emplacement | Statut |
|-----------|---------|-------------|---------|
| OpenSSL | 1.1.1w | /usr/local/openssl | ✅ Requis |
| SQLite | 3.15.2+ | /usr/local | ✅ Requis |
| Python | 3.13.0 | /usr/local/bin/python3.13 | ✅ Requis |
| MedDataBridge | Latest | /opt/meddata-bridge | ✅ App |
| Service | systemd | /etc/systemd/system/meddata-bridge.service | ✅ Auto |

---

## 🆘 Dépannage Express

### Service ne démarre pas
```bash
# 1. Voir les erreurs détaillées
sudo journalctl -u meddata-bridge -n 200 --no-pager

# 2. Tester manuellement
cd /opt/meddata-bridge
sudo -u meddata ./venv/bin/uvicorn app.app:app --host 0.0.0.0 --port 8000

# 3. Vérifier les modules Python
./venv/bin/python -c "import ssl; import sqlite3; print('OK')"
```

### Port 8000 déjà utilisé
```bash
# Trouver le processus
sudo netstat -tlnp | grep :8000

# Arrêter l'ancien service
sudo systemctl stop meddata-bridge
# ou
sudo kill -9 [PID]
```

### Erreur "No module named '_ssl'"
```bash
# Vérifier que Python utilise OpenSSL 1.1.1
/usr/local/bin/python3.13 -c "import ssl; print(ssl.OPENSSL_VERSION)"

# Si échec → Recompiler Python avec OpenSSL 1.1.1
cd /usr/src/Python-3.13.0
sudo make distclean
sudo ./configure --with-openssl=/usr/local/openssl --enable-loadable-sqlite-extensions
sudo make -j$(nproc)
sudo make altinstall
```

---

## 📞 Commandes Utiles

```bash
# Redémarrer le service
sudo systemctl restart meddata-bridge

# Arrêter le service
sudo systemctl stop meddata-bridge

# Voir les logs
sudo journalctl -u meddata-bridge -f

# Recharger la configuration systemd
sudo systemctl daemon-reload

# Vérifier la configuration .env
cat /opt/meddata-bridge/.env

# Recréer la base de données
cd /opt/meddata-bridge
sudo -u meddata rm data/meddata.db
sudo -u meddata ./venv/bin/python init_db.py
```

---

## ✨ Installation Réussie

Si toutes les étapes sont ✅ :

**URLs disponibles :**
- Application : `http://[serveur]:8000/`
- API Docs : `http://[serveur]:8000/docs`
- Admin : `http://[serveur]:8000/admin` (si activé)

**Fichiers importants :**
- Config : `/opt/meddata-bridge/.env`
- Base : `/opt/meddata-bridge/data/meddata.db`
- Logs : `sudo journalctl -u meddata-bridge`
- Service : `/etc/systemd/system/meddata-bridge.service`

---

## 🎉 Félicitations !

MedDataBridge est maintenant déployé sur RHEL 7.9 avec Python 3.13 ! 🚀

**Temps total estimé : 30-40 minutes**
- OpenSSL 1.1.1 : 10-15 min
- Python 3.13 : 10-15 min
- MedDataBridge : 3-5 min
- Tests : 2-5 min
