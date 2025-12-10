# Installation Rapide - MedDataBridge Python 3.13 sur RHEL 7.9

## 🎯 Déploiement Complet en 3 Étapes

### Prérequis
- Serveur RHEL 7.9 (sans accès Internet OK)
- Accès root (sudo)
- ~500 MB d'espace disque
- **⚠️ CRITIQUE: OpenSSL 1.1.1 ou plus récent requis** (voir ci-dessous)

---

## 📦 Étape 1 : Transférer le package

**Sur votre poste Windows :**
```powershell
# Transférer l'archive vers le serveur
scp meddata-bridge-py313-20251210.zip user@serveur:/tmp/
```

**Sur le serveur RHEL :**
```bash
cd /tmp
unzip meddata-bridge-py313-20251210.zip
cd Deploiement/scripts
chmod +x *.sh
```

---

## ⚠️ IMPORTANT : Vérification OpenSSL (RHEL 7.9)

**RHEL 7.9 fournit OpenSSL 1.0.2 par défaut, mais Python 3.13 nécessite OpenSSL 1.1.1+**

Vérifier votre version OpenSSL :
```bash
openssl version
# Si vous voyez "OpenSSL 1.0.2" → vous devez compiler OpenSSL 1.1.1
# Si vous voyez "OpenSSL 1.1.1" → OK, passez à l'étape 2
```

### Si OpenSSL 1.0.2 détecté → Compiler OpenSSL 1.1.1w

**Sans accès Internet (RECOMMANDÉ)** - Téléchargez depuis un poste avec Internet :
```bash
# Sur votre poste Windows avec Internet :
# Télécharger : https://www.openssl.org/source/openssl-1.1.1w.tar.gz
# Transférer vers le serveur :
scp openssl-1.1.1w.tar.gz user@serveur:/tmp/
```

**Sur le serveur RHEL 7.9 :**
```bash
cd /usr/src
sudo tar xzf /tmp/openssl-1.1.1w.tar.gz
cd openssl-1.1.1w

# Configuration
sudo ./config --prefix=/usr/local/openssl --openssldir=/usr/local/openssl shared zlib

# Compilation (5-10 minutes)
sudo make -j$(nproc)

# Installation
sudo make install

# Ajouter aux bibliothèques système
echo '/usr/local/openssl/lib' | sudo tee /etc/ld.so.conf.d/openssl-1.1.1.conf
sudo ldconfig

# Vérifier
/usr/local/openssl/bin/openssl version
# Doit afficher : OpenSSL 1.1.1w
```

**✅ OpenSSL 1.1.1 installé** → Vous pouvez maintenant installer Python 3.13

---

## 🐍 Étape 2 : Installer Python 3.13

```bash
sudo ./install_python313.sh
```

⚠️ **Le script détectera automatiquement si OpenSSL 1.1.1 est présent et configurera Python en conséquence.**

**Durée : 10-15 minutes** (compilation incluse)

**Résultat attendu :**
```
✅ Installation terminée avec succès !
Python installé dans: /usr/local/bin/python3.13
```

---

## 🚀 Étape 3 : Installer MedDataBridge

```bash
sudo ./install_on_server.sh
```

**Durée : 3-5 minutes**

**Résultat attendu :**
```
✅ Installation terminée avec succès!
   • Application: /opt/meddata-bridge
   • Python: 3.13.0
   • Base de données: /opt/meddata-bridge/data/meddata.db
```

Le script :
- ✅ Crée l'utilisateur `meddata`
- ✅ Installe l'application dans `/opt/meddata-bridge`
- ✅ Crée l'environnement virtuel Python 3.13
- ✅ Installe les 70 dépendances (mode offline)
- ✅ Génère automatiquement les clés de sécurité
- ✅ Initialise la base de données SQLite
- ✅ Configure le service systemd

---

## ✅ Démarrage

```bash
# Activer le service au démarrage
sudo systemctl enable meddata-bridge

# Démarrer l'application
sudo systemctl start meddata-bridge

# Vérifier le statut
sudo systemctl status meddata-bridge

# Vérifier que le port 8000 écoute
sudo netstat -tlnp | grep :8000

# Tester l'application
curl http://localhost:8000/
```

**Résultat attendu :**
```
● meddata-bridge.service - MedData Bridge
   Loaded: loaded
   Active: active (running)
```

---

## 🌐 (Optionnel) Installer Nginx

Pour exposer l'application sur le port 80 :

```bash
cd /tmp/Deploiement/scripts
sudo ./install_nginx.sh
```

Choisir l'option 1 (HTTP simple)

Tester : `curl http://localhost/`

---

## 📊 Vérifications

```bash
# Version Python utilisée
/opt/meddata-bridge/venv/bin/python --version
# Doit afficher: Python 3.13.0

# Logs en temps réel
sudo journalctl -u meddata-bridge -f

# Tester l'API
curl http://localhost:8000/docs
# Documentation interactive Swagger

# Vérifier la base de données
ls -lh /opt/meddata-bridge/data/meddata.db
```

---

## 🆘 Dépannage Express

### Service ne démarre pas
```bash
# Voir les erreurs
sudo journalctl -u meddata-bridge -n 100 --no-pager

# Tester manuellement
cd /opt/meddata-bridge
sudo -u meddata ./venv/bin/uvicorn app.app:app --host 0.0.0.0 --port 8000
```

### Python 3.13 non trouvé
```bash
# Vérifier l'installation
/usr/local/bin/python3.13 --version

# Si absent, réinstaller
cd /tmp/Deploiement/scripts
sudo ./install_python313.sh
```

### Port 8000 déjà utilisé
```bash
# Trouver le processus
sudo netstat -tlnp | grep :8000

# Arrêter l'ancien service
sudo systemctl stop meddata-bridge
```

---

## 📝 Fichiers Importants

| Fichier | Description |
|---------|-------------|
| `/opt/meddata-bridge/.env` | Configuration (clés auto-générées) |
| `/opt/meddata-bridge/data/meddata.db` | Base de données SQLite |
| `/etc/systemd/system/meddata-bridge.service` | Service systemd |
| `/var/log/messages` | Logs système |

---

## ✨ Avantages Python 3.13

- ✅ **Type hints modernes** : `str \| None` fonctionne nativement
- ✅ **Performances** : +15% plus rapide que Python 3.8
- ✅ **Compatibilité** : Code identique au développement
- ✅ **Support long terme** : Mises à jour jusqu'en 2028

---

## 🎉 Installation Terminée

**URLs disponibles :**
- Application : `http://serveur:8000/`
- API Docs : `http://serveur:8000/docs`
- Admin UI : `http://serveur:8000/admin`

**Avec Nginx (si installé) :**
- Application : `http://serveur/`
- API Docs : `http://serveur/docs`

---

## 📞 Support

En cas de problème :
1. Vérifier les logs : `sudo journalctl -u meddata-bridge -f`
2. Tester manuellement : `sudo -u meddata /opt/meddata-bridge/venv/bin/uvicorn app.app:app`
3. Vérifier Python 3.13 : `/usr/local/bin/python3.13 --version`

**Commandes utiles :**
```bash
# Redémarrer le service
sudo systemctl restart meddata-bridge

# Voir le statut
sudo systemctl status meddata-bridge

# Recharger la config
sudo systemctl daemon-reload
```

---

**Installation complète en ~15 minutes !** 🚀
