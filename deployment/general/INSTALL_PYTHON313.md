# Guide d'Installation Python 3.13 sur RHEL 7.9

## 📋 Vue d'ensemble

Ce guide vous permet d'installer Python 3.13.0 sur RHEL 7.9 et de mettre à jour MedDataBridge pour l'utiliser. Python 3.13 apporte de meilleures performances et supporte toutes les fonctionnalités modernes de Python.

## ✅ Avantages de Python 3.13

- ✅ **Type hints modernes** : Support de `str | None`, `list[str]`, etc.
- ✅ **Performances** : ~15% plus rapide que Python 3.8
- ✅ **Sécurité** : Mises à jour de sécurité jusqu'en 2028
- ✅ **Compatibilité** : Code développé avec Python 3.13 fonctionne sans modification

## 📦 Prérequis

### Option A : Serveur avec accès Internet

Le script téléchargera automatiquement Python 3.13.0 depuis python.org.

### Option B : Serveur sans Internet (OFFLINE)

**Sur votre poste Windows avec Internet :**

1. Téléchargez Python 3.13.0 :
   ```
   https://www.python.org/ftp/python/3.13.0/Python-3.13.0.tgz
   ```

2. Copiez le fichier `Python-3.13.0.tgz` sur le serveur RHEL dans `/tmp/`

**Vérification des fichiers requis :**
```bash
ls -lh /tmp/Python-3.13.0.tgz
ls -lh /tmp/deployment/dependencies-py313/
```

## 🚀 Installation Complète

### Étape 1 : Copier les fichiers sur le serveur

```bash
# Copier le package de déploiement
scp meddata-bridge-py313-*.zip user@serveur:/tmp/

# Se connecter au serveur
ssh user@serveur

# Extraire le package
cd /tmp
unzip meddata-bridge-py313-*.zip
```

### Étape 2 : Installer Python 3.13

```bash
cd /tmp/deployment/scripts

# Rendre le script exécutable
chmod +x install_python313.sh

# Exécuter l'installation
sudo ./install_python313.sh
```

**Durée estimée :** 10-15 minutes (compilation incluse)

**Résultat attendu :**
```
✅ Installation terminée avec succès !
Python installé dans: /usr/local/bin/python3.13
pip installé dans: /usr/local/bin/pip3.13
```

### Étape 3 : Mettre à jour MedDataBridge

```bash
cd /tmp/deployment/scripts

# Rendre le script exécutable
chmod +x upgrade_to_python313.sh

# Exécuter la mise à jour
sudo ./upgrade_to_python313.sh
```

**Résultat attendu :**
```
✅ Mise à jour terminée !
MedDataBridge tourne maintenant avec Python 3.13
✓ Application écoute sur le port 8000
✓ Application répond aux requêtes HTTP
```

### Étape 4 : Vérification

```bash
# Vérifier le service
sudo systemctl status meddata-bridge

# Vérifier le port
sudo netstat -tlnp | grep :8000

# Tester l'application
curl http://localhost:8000/

# Vérifier la version Python utilisée
/opt/meddata-bridge/venv/bin/python3.13 --version
```

## 🔧 Installation Manuelle (si scripts échouent)

### 1. Installer les dépendances

```bash
sudo yum groupinstall -y "Development Tools"
sudo yum install -y openssl-devel bzip2-devel libffi-devel \
    sqlite-devel xz-devel ncurses-devel readline-devel \
    gdbm-devel zlib-devel tk-devel libuuid-devel
```

### 2. Compiler Python 3.13

```bash
cd /usr/src
sudo tar xzf /tmp/Python-3.13.0.tgz
cd Python-3.13.0

sudo ./configure \
    --enable-optimizations \
    --enable-loadable-sqlite-extensions \
    --with-system-ffi \
    --with-ensurepip=install

sudo make -j$(nproc)
sudo make altinstall
```

### 3. Vérifier Python 3.13

```bash
/usr/local/bin/python3.13 --version
# Doit afficher: Python 3.13.0

/usr/local/bin/python3.13 -c "import sqlite3; print(sqlite3.sqlite_version)"
# Doit afficher la version SQLite
```

### 4. Recréer l'environnement virtuel

```bash
cd /opt/meddata-bridge

# Sauvegarder l'ancien
sudo mv venv venv.backup.old

# Créer le nouveau avec Python 3.13
sudo /usr/local/bin/python3.13 -m venv venv

# Installer les dépendances
sudo /opt/meddata-bridge/venv/bin/pip install --upgrade pip setuptools wheel \
    --no-index --find-links=/opt/meddata-bridge/dependencies-py313

sudo /opt/meddata-bridge/venv/bin/pip install \
    --no-index --find-links=/opt/meddata-bridge/dependencies-py313 \
    -r /opt/meddata-bridge/requirements.txt
```

### 5. Ajuster les permissions

```bash
sudo chown -R meddata:meddata /opt/meddata-bridge/venv
sudo chmod -R 755 /opt/meddata-bridge/venv
```

### 6. Redémarrer le service

```bash
sudo systemctl daemon-reload
sudo systemctl restart meddata-bridge
sudo systemctl status meddata-bridge
```

## 🆘 Dépannage

### Problème : "Development Tools" non disponible

```bash
# Sur RHEL 7.9, utiliser yum-builddep
sudo yum install yum-utils
sudo yum-builddep python3

# Ou installer manuellement les packages
sudo yum install gcc gcc-c++ make patch autoconf automake libtool
```

### Problème : Erreur de compilation "No module named '_sqlite3'"

```bash
# Vérifier que sqlite-devel est installé
sudo yum install sqlite-devel

# Recompiler Python
cd /usr/src/Python-3.13.0
sudo make clean
sudo ./configure --enable-optimizations --enable-loadable-sqlite-extensions
sudo make -j$(nproc)
sudo make altinstall
```

### Problème : pip ne fonctionne pas dans le venv

```bash
# Réinstaller pip manuellement
curl https://bootstrap.pypa.io/get-pip.py -o /tmp/get-pip.py
sudo /opt/meddata-bridge/venv/bin/python3.13 /tmp/get-pip.py
```

### Problème : Dépendances cryptography échouent

```bash
# Vérifier libffi et openssl
sudo yum install libffi-devel openssl-devel

# Si cryptography-46.0.3 échoue, utiliser une version précompilée
sudo /opt/meddata-bridge/venv/bin/pip install \
    --no-index --find-links=/opt/meddata-bridge/dependencies-py313 \
    cryptography
```

### Problème : Le service ne démarre pas

```bash
# Voir les logs détaillés
sudo journalctl -u meddata-bridge -n 100 --no-pager

# Tester manuellement
cd /opt/meddata-bridge
sudo -u meddata /opt/meddata-bridge/venv/bin/uvicorn app.app:app --host 0.0.0.0 --port 8000

# Vérifier les imports Python
sudo -u meddata /opt/meddata-bridge/venv/bin/python3.13 -c "
import fastapi
import sqlmodel
import uvicorn
print('OK')
"
```

## 📊 Comparaison des versions

| Fonctionnalité | Python 3.8 | Python 3.13 |
|----------------|------------|-------------|
| Type hints `str \| None` | ❌ Non | ✅ Oui |
| Type hints `list[str]` | ❌ Non | ✅ Oui |
| Performances | Baseline | +15% |
| Support jusqu'à | 2024 | 2028 |
| SQLite intégré | Oui | Oui |

## 🔄 Retour à Python 3.8 (si nécessaire)

Si vous devez revenir à Python 3.8 :

```bash
# Arrêter le service
sudo systemctl stop meddata-bridge

# Restaurer l'ancien venv
cd /opt/meddata-bridge
sudo rm -rf venv
sudo mv venv.backup.old venv

# Redémarrer
sudo systemctl start meddata-bridge
```

## ✅ Checklist de vérification

Après installation, vérifiez :

- [ ] Python 3.13 installé : `/usr/local/bin/python3.13 --version`
- [ ] SQLite activé : `python3.13 -c "import sqlite3; print('OK')"`
- [ ] Venv créé : `ls -la /opt/meddata-bridge/venv/`
- [ ] Dépendances installées : `/opt/meddata-bridge/venv/bin/pip list`
- [ ] Service actif : `sudo systemctl status meddata-bridge`
- [ ] Port 8000 ouvert : `sudo netstat -tlnp | grep :8000`
- [ ] Application répond : `curl http://localhost:8000/`

## 📝 Notes importantes

1. **Python 3.8 reste installé** : `altinstall` préserve Python 3.8 dans le système
2. **Compatibilité** : Tout le code Python 3.13 fonctionne sans modification
3. **Performance** : L'application sera ~15% plus rapide
4. **Sécurité** : Python 3.13 reçoit des mises à jour jusqu'en octobre 2028

## 🎉 Avantages finaux

- ✅ Plus besoin de modifier les type hints dans le code
- ✅ Code source identique au développement (Python 3.13)
- ✅ Meilleures performances
- ✅ Support long terme (jusqu'en 2028)
- ✅ Prêt pour de futures fonctionnalités Python

---

**Besoin d'aide ?** Consultez les logs : `sudo journalctl -u meddata-bridge -f`
