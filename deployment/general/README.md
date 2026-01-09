# 📦 IntegraSanté - Package de Déploiement RHEL 7.9

## 👋 Vue d'ensemble

Ce package contient tout le nécessaire pour déployer IntegraSanté sur **RHEL 7.9** avec **Python 3.13**, en mode **offline** (sans accès Internet).

---

## 📚 Documentation Disponible

### 🚀 Installation Rapide
**[INSTALLATION_RAPIDE.md](INSTALLATION_RAPIDE.md)** - Guide d'installation en 3 étapes (~15 min)
- Pour utilisateurs pressés
- Instructions concises
- Commandes prêtes à copier-coller

### ✅ Checklist Complète
**[RHEL79_DEPLOYMENT_CHECKLIST.md](RHEL79_DEPLOYMENT_CHECKLIST.md)** - Checklist détaillée avec vérifications (~30-40 min)
- Pour déploiements en production
- Liste de contrôle étape par étape
- Commandes de vérification après chaque étape
- Dépannage intégré

### 🔐 Installation OpenSSL 1.1.1
**[INSTALL_OPENSSL_RHEL79.md](INSTALL_OPENSSL_RHEL79.md)** - Guide complet OpenSSL 1.1.1w
- **⚠️ CRITIQUE** : Requis sur RHEL 7.9 (OpenSSL 1.0.2 par défaut)
- Installation offline et online
- Vérifications détaillées
- Dépannage complet

---

## 🎯 Quel Guide Choisir ?

### Vous êtes pressé ?
→ **[INSTALLATION_RAPIDE.md](INSTALLATION_RAPIDE.md)**
- 3 étapes simples
- 15 minutes chrono
- Pour environnements de test/dev

### Premier déploiement en production ?
→ **[RHEL79_DEPLOYMENT_CHECKLIST.md](RHEL79_DEPLOYMENT_CHECKLIST.md)**
- Vérifications à chaque étape
- Détection précoce des problèmes
- Commandes de diagnostic

### Erreur "Could not build the ssl module" ?
→ **[INSTALL_OPENSSL_RHEL79.md](INSTALL_OPENSSL_RHEL79.md)**
- Installation OpenSSL 1.1.1w
- Résout les problèmes de module SSL
- Requis pour Python 3.13 sur RHEL 7.9

---

## 📂 Contenu du Package

```
deployment/
├── README.md                          # Ce fichier
├── INSTALLATION_RAPIDE.md             # Guide rapide 3 étapes
├── RHEL79_DEPLOYMENT_CHECKLIST.md     # Checklist complète
├── INSTALL_OPENSSL_RHEL79.md          # Guide OpenSSL 1.1.1w
│
├── dependencies-py313/                # 71 packages Python 3.13 (85 MB)
│   ├── annotated_types-0.7.0-py3-none-any.whl
│   ├── fastapi-0.115.6-py3-none-any.whl
│   ├── uvicorn-0.34.0-py3-none-any.whl
│   ├── uvloop-0.22.1-cp313-cp313-manylinux2014_x86_64.whl
│   └── ... (67 autres packages)
│
├── scripts/
│   ├── install_python313.sh           # Installation Python 3.13
│   ├── install_on_server.sh           # Installation MedDataBridge
│   ├── upgrade_to_python313.sh        # Migration Python 3.8 → 3.13
│   └── install_nginx.sh               # (Optionnel) Nginx reverse proxy
│
├── systemd/
│   └── meddata-bridge.service         # Service systemd
│
└── [À télécharger séparément]
    ├── Python-3.13.0.tgz              # Sources Python 3.13 (26 MB)
    └── openssl-1.1.1w.tar.gz          # Sources OpenSSL 1.1.1w (9.8 MB)
```

---

## ⚠️ Prérequis CRITIQUES

### 1. OpenSSL 1.1.1 ou plus récent

**RHEL 7.9 fournit OpenSSL 1.0.2k par défaut, ce qui est INSUFFISANT pour Python 3.13.**

Vérifier votre version :
```bash
openssl version
```

- ✅ **"OpenSSL 1.1.1"** → OK, passez à l'installation
- ❌ **"OpenSSL 1.0.2"** → **BLOCKER** : Suivez d'abord [INSTALL_OPENSSL_RHEL79.md](INSTALL_OPENSSL_RHEL79.md)

**Sans OpenSSL 1.1.1+, Python 3.13 sera compilé SANS le module SSL (_ssl) !**
→ Uvicorn ne démarrera pas
→ Aucune application web moderne ne fonctionnera

### 2. SQLite 3.15.2 ou plus récent

**RHEL 7.9 fournit SQLite 3.7.17 par défaut, ce qui est INSUFFISANT pour Python 3.13.**

✅ **Le script `install_python313.sh` compile automatiquement SQLite 3.15.2 si nécessaire.**

### 3. Espace Disque

- `/usr/src` : ~150 MB (compilation Python + OpenSSL + SQLite)
- `/opt` : ~300 MB (application + venv + base de données)
- `/tmp` : ~100 MB (fichiers temporaires)

**Total : ~500 MB**

### 4. Accès root (sudo)

Toutes les étapes d'installation nécessitent les droits root.

---

## 🚀 Installation Express (3 Étapes)

### Étape 0 : Vérifier OpenSSL (CRITIQUE)

```bash
openssl version
```

- ❌ **Si "OpenSSL 1.0.2"** → Installer OpenSSL 1.1.1w d'abord :
  1. Télécharger : https://www.openssl.org/source/openssl-1.1.1w.tar.gz
  2. Suivre : [INSTALL_OPENSSL_RHEL79.md](INSTALL_OPENSSL_RHEL79.md)

### Étape 1 : Transférer le Package

```powershell
# Sur Windows
scp meddata-bridge-py313-latest.zip user@serveur:/tmp/
```

```bash
# Sur le serveur
cd /tmp
unzip meddata-bridge-py313-latest.zip
cd deployment/scripts
chmod +x *.sh
```

### Étape 2 : Installer Python 3.13

```bash
sudo ./install_python313.sh
```

**Durée : 10-15 minutes**

### Étape 3 : Installer MedDataBridge

```bash
sudo ./install_on_server.sh
```

**Durée : 3-5 minutes**

### Étape 4 : Démarrer le Service

```bash
sudo systemctl enable meddata-bridge
sudo systemctl start meddata-bridge
sudo systemctl status meddata-bridge
```

### Étape 5 : Tester

```bash
curl http://localhost:8000/
curl http://localhost:8000/docs
```

---

## 📊 Compatibilité RHEL 7.9

| Composant | Version RHEL 7.9 | Requis Python 3.13 | Solution |
|-----------|------------------|-------------------|----------|
| **OpenSSL** | 1.0.2k | ≥ 1.1.1 | ❌ **Compiler 1.1.1w** |
| **SQLite** | 3.7.17 | ≥ 3.15.2 | ✅ Script auto |
| GCC | 4.8.5 | ≥ 4.8 | ✅ OK |
| Python | 2.7/3.6 | 3.13 | ✅ Compile |

---

## 🆘 Dépannage Rapide

### Erreur : "Could not build the ssl module!"
```bash
# Cause : OpenSSL 1.0.2 détecté (incompatible)
# Solution : Installer OpenSSL 1.1.1w
```
→ Suivre [INSTALL_OPENSSL_RHEL79.md](INSTALL_OPENSSL_RHEL79.md)

### Erreur : "ModuleNotFoundError: No module named '_ssl'"
```bash
# Cause : Python compilé sans OpenSSL 1.1.1
# Solution : Recompiler Python avec --with-openssl=/usr/local/openssl
cd /usr/src/Python-3.13.0
sudo make distclean
sudo ./configure --with-openssl=/usr/local/openssl --enable-loadable-sqlite-extensions
sudo make -j$(nproc)
sudo make altinstall
```

### Erreur : "ModuleNotFoundError: No module named '_sqlite3'"
```bash
# Cause : SQLite 3.15.2+ non détecté
# Solution : Compiler SQLite puis recompiler Python
```
→ Le script `install_python313.sh` gère cela automatiquement

### Service ne démarre pas
```bash
# Voir les logs
sudo journalctl -u meddata-bridge -n 100 --no-pager

# Tester manuellement
cd /opt/meddata-bridge
sudo -u meddata ./venv/bin/uvicorn app.app:app --host 0.0.0.0 --port 8000
```

---

## 📞 Support & Ressources

### Documentation
- [INSTALLATION_RAPIDE.md](INSTALLATION_RAPIDE.md) - Guide rapide
- [RHEL79_DEPLOYMENT_CHECKLIST.md](RHEL79_DEPLOYMENT_CHECKLIST.md) - Checklist complète
- [INSTALL_OPENSSL_RHEL79.md](INSTALL_OPENSSL_RHEL79.md) - OpenSSL 1.1.1w

### Commandes Utiles
```bash
# Vérifier Python 3.13
/usr/local/bin/python3.13 --version
/usr/local/bin/python3.13 -c "import ssl; print(ssl.OPENSSL_VERSION)"
/usr/local/bin/python3.13 -c "import sqlite3; print(sqlite3.sqlite_version)"

# Vérifier le service
sudo systemctl status meddata-bridge
sudo journalctl -u meddata-bridge -f

# Vérifier l'application
curl http://localhost:8000/
curl http://localhost:8000/docs
sudo netstat -tlnp | grep :8000
```

### Fichiers Importants
- Configuration : `/opt/meddata-bridge/.env`
- Base de données : `/opt/meddata-bridge/data/meddata.db`
- Service : `/etc/systemd/system/meddata-bridge.service`
- Logs : `sudo journalctl -u meddata-bridge`

---

## ✨ Avantages Python 3.13

- ✅ **Type hints modernes** : `str | None` fonctionne nativement
- ✅ **Performances** : +15% plus rapide que Python 3.8
- ✅ **Compatibilité** : Code identique au développement
- ✅ **Support LTS** : Mises à jour jusqu'en 2028
- ✅ **Stabilité** : Version finale, pas de release candidate

---

## 🎉 Installation Réussie

**Temps total estimé : 30-40 minutes**
- OpenSSL 1.1.1 : 10-15 min (si nécessaire)
- Python 3.13 : 10-15 min
- MedDataBridge : 3-5 min
- Tests : 2-5 min

**URLs disponibles :**
- Application : `http://[serveur]:8000/`
- API Docs : `http://[serveur]:8000/docs`
- Admin : `http://[serveur]:8000/admin`

---

**MedDataBridge - Plateforme d'Intégration HL7 FHIR** 🚀
