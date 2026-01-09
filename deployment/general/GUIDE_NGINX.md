# Guide d'Installation Nginx pour MedData Bridge

## 🎯 Architecture Recommandée

```text
Internet/Réseau
     ↓
Port 80/443 (Nginx) ← Reverse Proxy
     ↓
Port 8000 (Uvicorn) ← Application FastAPI
     ↓
SQLite (meddata.db)
```

## ✅ Pourquoi Nginx ?

### Avantages

- ✅ **Sécurité** : Pas besoin de lancer uvicorn en root
- ✅ **SSL/TLS** : Support HTTPS avec Let's Encrypt
- ✅ **Performance** : Cache, compression gzip, fichiers statiques
- ✅ **Protection** : Rate limiting, headers de sécurité
- ✅ **Flexibilité** : Plusieurs apps sur le même serveur
- ✅ **Logs** : Séparation logs Nginx / application

### Inconvénients port 80 direct (sans Nginx)

- ❌ Besoin de lancer uvicorn en **root** (risque sécurité)
- ❌ Pas de SSL facile
- ❌ Pas de cache ou compression
- ❌ Performances limitées pour fichiers statiques

---

## 📦 Installation sur le Serveur

### Étape 1 : Installer MedData Bridge

```bash
# Installer l'application d'abord
cd /tmp/deployment/scripts
sudo ./install_on_server.sh
```

### Étape 2 : Installer et Configurer Nginx

```bash
# Script automatique fourni
cd /tmp/deployment/scripts
sudo ./install_nginx.sh
```

Le script vous demandera de choisir :

1. **HTTP simple (port 80)** - Accès immédiat sans SSL
2. **HTTPS (port 443)** - Avec certificats SSL (production)
3. **Accès par IP** - Sans nom de domaine

---

## 🔧 Configuration Manuelle (si nécessaire)

### Installation Nginx

```bash
# Sur Fedora
sudo dnf install nginx

# Démarrer et activer
sudo systemctl enable nginx
sudo systemctl start nginx
```

### Copier la Configuration

```bash
# Copier le fichier fourni
sudo cp /tmp/deployment/config/nginx-meddata-bridge.conf \
       /etc/nginx/conf.d/meddata-bridge.conf

# Tester la configuration
sudo nginx -t

# Recharger Nginx
sudo systemctl reload nginx
```

### Configurer le Firewall

```bash
# Ouvrir le port HTTP
sudo firewall-cmd --permanent --add-service=http

# Ouvrir le port HTTPS (si SSL)
sudo firewall-cmd --permanent --add-service=https

# Appliquer
sudo firewall-cmd --reload
```

### Configurer SELinux (si activé)

```bash
# Autoriser Nginx à se connecter au backend
sudo setsebool -P httpd_can_network_connect 1
```

---

## 🌐 Options de Configuration

### Option 1 : HTTP Simple (port 80)

**Recommandé pour** : Démarrage rapide, réseau interne, tests

La configuration par défaut dans le fichier fourni.

**Accès** :

- `http://IP_SERVEUR/`
- `http://localhost/` (depuis le serveur)

### Option 2 : HTTPS avec Let's Encrypt (port 443)

**Recommandé pour** : Production, accès Internet

```bash
# Installer Certbot
sudo dnf install certbot python3-certbot-nginx

# Obtenir certificat (remplacer le domaine)
sudo certbot --nginx -d meddata.votre-domaine.com

# Certbot configure automatiquement Nginx pour HTTPS
# Renouvellement automatique configuré
```

**Accès** :

- `https://meddata.votre-domaine.com/`

### Option 3 : Certificats Auto-signés (tests SSL)

```bash
# Créer répertoire SSL
sudo mkdir -p /etc/nginx/ssl

# Générer certificat auto-signé
sudo openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout /etc/nginx/ssl/meddata.key \
  -out /etc/nginx/ssl/meddata.crt

# Décommenter la section HTTPS dans la config Nginx
sudo vi /etc/nginx/conf.d/meddata-bridge.conf

# Recharger
sudo nginx -t && sudo systemctl reload nginx
```

⚠️ Le navigateur affichera un avertissement (certificat non reconnu)

---

## 🔍 Vérification de l'Installation

### Test Nginx

```bash
# Statut Nginx
sudo systemctl status nginx

# Test configuration
sudo nginx -t

# Logs en temps réel
sudo tail -f /var/log/nginx/meddata-access.log
```

### Test Application

```bash
# Depuis le serveur
curl http://localhost/

# Depuis un autre poste (remplacer IP)
curl http://192.168.1.100/

# Vérifier uvicorn tourne
sudo systemctl status meddata-bridge
```

### Test Complet

```bash
# HTTP
curl -I http://IP_SERVEUR/

# Devrait retourner:
# HTTP/1.1 200 OK
# Server: nginx
```

---

## 📝 Maintenance

### Recharger la Configuration

```bash
# Après modification config
sudo nginx -t
sudo systemctl reload nginx
```

### Voir les Logs

```bash
# Logs Nginx
sudo tail -f /var/log/nginx/meddata-access.log
sudo tail -f /var/log/nginx/meddata-error.log

# Logs application (uvicorn)
sudo journalctl -u meddata-bridge -f
```

### Redémarrer les Services

```bash
# Redémarrer Nginx
sudo systemctl restart nginx

# Redémarrer MedData Bridge
sudo systemctl restart meddata-bridge

# Redémarrer les deux
sudo systemctl restart nginx meddata-bridge
```

---

## 🔒 Sécurité Avancée

### Rate Limiting (anti-DDoS)

Ajouter dans `/etc/nginx/conf.d/meddata-bridge.conf` :

```nginx
# En haut du fichier
limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;

# Dans le bloc server
location /api/ {
    limit_req zone=api_limit burst=20 nodelay;
    proxy_pass http://127.0.0.1:8000;
    # ... autres directives proxy
}
```

### Filtrage par IP

```nginx
# Autoriser seulement certaines IP
location /admin/ {
    allow 192.168.1.0/24;
    deny all;
    proxy_pass http://127.0.0.1:8000;
}
```

### Headers de Sécurité Complets

Déjà inclus dans la configuration fournie :

- `X-Frame-Options` : Protection clickjacking
- `X-Content-Type-Options` : Protection MIME sniffing
- `X-XSS-Protection` : Protection XSS
- `Strict-Transport-Security` : Force HTTPS (si SSL)

---

## 🆘 Dépannage

### Problème : Nginx ne démarre pas

```bash
# Vérifier la configuration
sudo nginx -t

# Voir les erreurs
sudo journalctl -u nginx -n 50

# Vérifier que le port 80 n'est pas déjà utilisé
sudo netstat -tlnp | grep :80
```

### Problème : 502 Bad Gateway

**Cause** : Nginx ne peut pas joindre uvicorn (port 8000)

```bash
# Vérifier que meddata-bridge tourne
sudo systemctl status meddata-bridge

# Vérifier que le port 8000 écoute
sudo netstat -tlnp | grep :8000

# Vérifier SELinux
sudo setsebool -P httpd_can_network_connect 1
```

### Problème : 404 sur fichiers statiques

```bash
# Vérifier le chemin dans la config
cat /etc/nginx/conf.d/meddata-bridge.conf | grep static

# Vérifier que les fichiers existent
ls -la /opt/meddata-bridge/app/static/

# Vérifier les permissions
sudo chmod -R 755 /opt/meddata-bridge/app/static/
```

### Problème : Certificat SSL expiré

```bash
# Vérifier expiration
sudo certbot certificates

# Renouveler manuellement
sudo certbot renew

# Test de renouvellement
sudo certbot renew --dry-run
```

---

## 📊 Performance

### Activer le Cache

Ajouter dans la config Nginx :

```nginx
# En haut du fichier
proxy_cache_path /var/cache/nginx/meddata levels=1:2 keys_zone=meddata_cache:10m max_size=100m;

# Dans location /
location / {
    proxy_cache meddata_cache;
    proxy_cache_valid 200 5m;
    proxy_cache_use_stale error timeout updating;
    add_header X-Cache-Status $upstream_cache_status;
    
    proxy_pass http://127.0.0.1:8000;
    # ... autres directives
}
```

### Monitoring

```bash
# Activer stub_status dans /etc/nginx/nginx.conf
server {
    listen 127.0.0.1:8080;
    location /nginx_status {
        stub_status on;
        access_log off;
    }
}

# Consulter les stats
curl http://127.0.0.1:8080/nginx_status
```

---

## ✅ Checklist Installation Nginx

- [ ] MedData Bridge installé et fonctionnel (port 8000)
- [ ] Nginx installé (`dnf install nginx`)
- [ ] Configuration copiée (`/etc/nginx/conf.d/meddata-bridge.conf`)
- [ ] Configuration testée (`nginx -t`)
- [ ] SELinux configuré (`httpd_can_network_connect`)
- [ ] Firewall ouvert (port 80 ou 443)
- [ ] Nginx démarré (`systemctl start nginx`)
- [ ] Test HTTP réussi (`curl http://IP_SERVEUR/`)
- [ ] Certificats SSL installés (si HTTPS)
- [ ] Logs accessibles et surveillés

---

## 🎉 Résultat Final

Après installation complète :

```text
✅ Nginx écoute sur le port 80 (HTTP) ou 443 (HTTPS)
✅ Uvicorn tourne en arrière-plan sur le port 8000
✅ Les requêtes externes passent par Nginx
✅ Fichiers statiques servis directement par Nginx
✅ SSL/TLS géré par Nginx (si configuré)
✅ Headers de sécurité appliqués
✅ Compression gzip active
✅ Logs séparés Nginx / Application

🌐 Application accessible :
   - Depuis l'extérieur : http://IP_SERVEUR/
   - Avec SSL : https://votre-domaine.com/
   - API : http://IP_SERVEUR/api/...
   - Documentation : http://IP_SERVEUR/docs
```

**Installation professionnelle et sécurisée !** 🚀
