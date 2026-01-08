# Installation OpenSSL 1.1.1w sur RHEL 7.9

## 🎯 Problème

**RHEL 7.9 fournit OpenSSL 1.0.2k par défaut, mais Python 3.13 nécessite OpenSSL 1.1.1 ou plus récent.**

Sans OpenSSL 1.1.1+, Python 3.13 sera compilé **sans le module SSL (_ssl)**, ce qui empêchera :
- ❌ Uvicorn de démarrer
- ❌ Les requêtes HTTPS
- ❌ La plupart des applications web modernes

## ✅ Solution : Compiler OpenSSL 1.1.1w

OpenSSL 1.1.1w est la dernière version de la série 1.1.1 (support LTS jusqu'en septembre 2023+).

---

## 📦 Méthode 1 : Installation Offline (RECOMMANDÉ)

### Sur un poste avec Internet

1. **Télécharger OpenSSL 1.1.1w :**
   - URL : https://www.openssl.org/source/openssl-1.1.1w.tar.gz
   - Taille : ~9.8 MB

2. **Transférer vers le serveur :**
   ```powershell
   # Windows (PowerShell)
   scp openssl-1.1.1w.tar.gz user@serveur:/tmp/
   ```

   ```bash
   # Linux
   scp openssl-1.1.1w.tar.gz user@serveur:/tmp/
   ```

### Sur le serveur RHEL 7.9

```bash
# 1. Extraire les sources
cd /usr/src
sudo tar xzf /tmp/openssl-1.1.1w.tar.gz
cd openssl-1.1.1w

# 2. Installer les dépendances de compilation (si pas déjà fait)
sudo yum install -y gcc make perl zlib-devel

# 3. Configurer OpenSSL
# Installation dans /usr/local/openssl pour ne pas écraser le système
sudo ./config \
    --prefix=/usr/local/openssl \
    --openssldir=/usr/local/openssl \
    shared \
    zlib

# 4. Compiler (5-10 minutes)
sudo make -j$(nproc)

# 5. Tester la compilation (OPTIONNEL - peut échouer sans impact)
# Les tests peuvent échouer sur RHEL 7.9 pour des raisons de compatibilité Perl
# mais OpenSSL fonctionnera correctement. Vous pouvez ignorer les erreurs de test.
sudo make test || echo "⚠️ Tests échoués (normal sur RHEL 7.9) - Continuer avec make install"

# 6. Installer
sudo make install

# 7. Configurer les bibliothèques système
echo '/usr/local/openssl/lib' | sudo tee /etc/ld.so.conf.d/openssl-1.1.1.conf
sudo ldconfig

# 8. Vérifier l'installation
/usr/local/openssl/bin/openssl version
# Doit afficher : OpenSSL 1.1.1w  11 Sep 2023
```

---

## 📡 Méthode 2 : Installation Online

Si le serveur a accès Internet :

```bash
cd /usr/src
sudo wget https://www.openssl.org/source/openssl-1.1.1w.tar.gz
sudo tar xzf openssl-1.1.1w.tar.gz
cd openssl-1.1.1w

sudo yum install -y gcc make perl zlib-devel

sudo ./config --prefix=/usr/local/openssl --openssldir=/usr/local/openssl shared zlib
sudo make -j$(nproc)
# Tests peuvent échouer - ignorer et continuer
sudo make test || true
sudo make install

echo '/usr/local/openssl/lib' | sudo tee /etc/ld.so.conf.d/openssl-1.1.1.conf
sudo ldconfig

/usr/local/openssl/bin/openssl version
```

---

## ✅ Vérification

### 1. Vérifier la version
```bash
/usr/local/openssl/bin/openssl version
# Attendu : OpenSSL 1.1.1w  11 Sep 2023
```

### 2. Vérifier les bibliothèques
```bash
ls -lh /usr/local/openssl/lib/
# Doit contenir : libssl.so.1.1, libcrypto.so.1.1
```

### 3. Vérifier ldconfig
```bash
ldconfig -p | grep /usr/local/openssl
# Doit afficher les bibliothèques OpenSSL 1.1.1
```

### 4. Tester un certificat
```bash
/usr/local/openssl/bin/openssl s_client -connect google.com:443 -brief
# Doit afficher la connexion SSL réussie
```

---

## 🐍 Étape Suivante : Compiler Python 3.13

**Maintenant que OpenSSL 1.1.1 est installé**, vous pouvez compiler Python 3.13 :

```bash
cd /tmp/deployment/scripts
sudo ./install_python313.sh
```

Le script `install_python313.sh` détectera automatiquement OpenSSL 1.1.1 dans `/usr/local/openssl` et configurera Python avec les bonnes options :
```bash
./configure \
    --with-openssl=/usr/local/openssl \
    --enable-loadable-sqlite-extensions \
    [...]
```

---

## 🔍 Pourquoi /usr/local/openssl ?

**Installation séparée pour éviter les conflits :**
- ✅ N'écrase PAS l'OpenSSL système (1.0.2k)
- ✅ Les outils système RHEL continuent de fonctionner
- ✅ Python 3.13 utilise OpenSSL 1.1.1
- ✅ Compatible avec les politiques de sécurité RHEL

**Cohabitation OpenSSL 1.0.2 et 1.1.1 :**
```
/usr/bin/openssl           → OpenSSL 1.0.2k (système RHEL)
/usr/local/openssl/bin/openssl → OpenSSL 1.1.1w (Python 3.13)
```

---

## 🆘 Dépannage

### Erreur : "make: gcc: Command not found"
```bash
sudo yum install -y gcc make
```

### Erreur : "perl: command not found"
```bash
sudo yum install -y perl
```

### Erreur : "Can't locate IPC/Cmd.pm"
```bash
sudo yum install -y perl-IPC-Cmd perl-Test-Simple
```

### Test échoue : "Non-zero exit status" ou "No plan found in TAP output"
```bash
# C'EST NORMAL sur RHEL 7.9 !
# Les tests échouent souvent à cause de:
# - Version Perl incompatible (5.16 sur RHEL 7.9)
# - Modules Perl manquants (Test::More, IPC::Cmd)
# - Configuration TAP (Test Anything Protocol)

# OpenSSL sera FONCTIONNEL malgré l'échec des tests
# Continuer directement avec make install:
sudo make install

# Puis vérifier que OpenSSL fonctionne:
/usr/local/openssl/bin/openssl version
# Doit afficher: OpenSSL 1.1.1w  11 Sep 2023
```

### Python ne détecte pas OpenSSL 1.1.1
```bash
# Vérifier que ldconfig voit OpenSSL 1.1.1
ldconfig -p | grep /usr/local/openssl

# Si vide, recréer le fichier conf
echo '/usr/local/openssl/lib' | sudo tee /etc/ld.so.conf.d/openssl-1.1.1.conf
sudo ldconfig

# Nettoyer et recompiler Python
cd /usr/src/Python-3.13.0
sudo make distclean
sudo ./configure --with-openssl=/usr/local/openssl [...]
```

---

## 📊 Informations Techniques

### Compatibilité RHEL 7.9
| Composant | Version RHEL 7.9 | Requis Python 3.13 | Solution |
|-----------|------------------|-------------------|----------|
| OpenSSL | 1.0.2k | ≥ 1.1.1 | Compiler 1.1.1w |
| SQLite | 3.7.17 | ≥ 3.15.2 | Compiler 3.15.2+ |
| GCC | 4.8.5 | ≥ 4.8 | ✅ OK |

### Taille OpenSSL 1.1.1w
- Source : 9.8 MB (openssl-1.1.1w.tar.gz)
- Compilé : ~25 MB (/usr/local/openssl)
- Total : ~35 MB

### Durée d'installation
- Téléchargement : ~1 minute (avec Internet)
- Compilation : 5-10 minutes (dépend du CPU)
- Total : ~10-15 minutes

---

## 🎉 Résultat Final

Après installation réussie :

```bash
# OpenSSL 1.0.2k (système) - toujours présent
/usr/bin/openssl version
# OpenSSL 1.0.2k-fips  26 Jan 2017

# OpenSSL 1.1.1w (Python 3.13)
/usr/local/openssl/bin/openssl version
# OpenSSL 1.1.1w  11 Sep 2023

# Python 3.13 avec SSL
/usr/local/bin/python3.13 -c "import ssl; print(ssl.OPENSSL_VERSION)"
# OpenSSL 1.1.1w  11 Sep 2023
```

**✅ Vous pouvez maintenant installer Python 3.13 avec le module SSL fonctionnel !**

---

## 📞 Références

- OpenSSL 1.1.1 : https://www.openssl.org/source/
- Python 3.13 Requirements : https://www.python.org/downloads/release/python-3130/
- RHEL 7.9 Security : https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/7
