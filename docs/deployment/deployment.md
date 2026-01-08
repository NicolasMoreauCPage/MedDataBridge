# 🚀 Guide de Déploiement MedBridge

## Vue d'ensemble

Ce guide explique comment déployer l'application MedBridge en production à partir de la branche `production-deployment`.

## 📋 Prérequis

- Docker & Docker Compose
- Python 3.11+
- Git
- Au moins 4GB RAM, 2GB disque

## 🏗️ Structure du projet

```
MedBridge/
├── docker/                 # Configuration Docker
│   ├── Dockerfile         # Image application
│   ├── docker-compose.yml # Services (app, postgres, redis, nginx)
│   └── nginx.conf         # Configuration reverse proxy
├── config/                # Configuration centralisée
│   └── settings.py        # Paramètres d'application
├── scripts/               # Scripts de déploiement
│   └── deploy.sh          # Script principal de déploiement
├── .env.example           # Variables d'environnement
└── PRODUCTION_READINESS.md # Checklist production
```

## 🚀 Déploiement Rapide

### 1. Configuration initiale

```bash
# Cloner le projet
git clone <repository-url>
cd MedBridge

# Basculer sur la branche production
git checkout production-deployment

# Copier la configuration d'environnement
cp .env.example .env

# Éditer .env avec vos valeurs de production
nano .env
```

### 2. Variables d'environnement essentielles

```bash
# .env
ENVIRONMENT=production
SECRET_KEY=votre-cle-secrete-très-longue
JWT_SECRET_KEY=votre-cle-jwt-très-longue
DATABASE_URL=postgresql://user:password@postgres:5432/medbridge
REDIS_URL=redis://redis:6379
```

### 3. Déploiement complet

```bash
# Déploiement complet (tests + build + déploiement)
./scripts/deploy.sh production deploy
```

## 🎯 Commandes de déploiement

### Tests uniquement
```bash
./scripts/deploy.sh development test
```

### Build uniquement
```bash
./scripts/deploy.sh staging build
```

### Déploiement complet
```bash
./scripts/deploy.sh production deploy
```

### Migrations de base de données
```bash
./scripts/deploy.sh production migrate
```

## 🔧 Configuration avancée

### Base de données PostgreSQL

Le `docker-compose.yml` inclut PostgreSQL. Pour une base externe :

```bash
# .env
DATABASE_URL=postgresql://user:password@your-host:5432/medbridge
```

### Cache Redis

Activé automatiquement. Pour un Redis externe :

```bash
# .env
REDIS_URL=redis://your-redis-host:6379
```

### SSL/HTTPS

1. Générer des certificats :
```bash
mkdir -p docker/ssl
openssl req -x509 -newkey rsa:4096 -keyout docker/ssl/key.pem -out docker/ssl/cert.pem -days 365 -nodes
```

2. Activer HTTPS dans `docker/nginx.conf`

3. Démarrer avec nginx :
```bash
docker-compose --profile nginx up -d
```

## 📊 Monitoring

### Métriques de base

L'application expose des métriques sur `/metrics` quand `ENABLE_METRICS=true`.

### Logs

```bash
# Logs application
docker-compose logs medbridge

# Logs base de données
docker-compose logs postgres

# Tous les logs
docker-compose logs
```

## 🔄 Mise à jour

```bash
# Récupérer les dernières modifications
git pull origin production-deployment

# Redéployer
./scripts/deploy.sh production deploy
```

## 🐛 Dépannage

### L'application ne démarre pas

```bash
# Vérifier les logs
docker-compose logs medbridge

# Vérifier la santé
curl http://localhost:8000/health
```

### Problèmes de base de données

```bash
# Vérifier PostgreSQL
docker-compose exec postgres pg_isready -U medbridge

# Réinitialiser la base
docker-compose down -v
docker-compose up -d postgres
```

### Problèmes de cache Redis

```bash
# Vérifier Redis
docker-compose exec redis redis-cli ping

# Redémarrer Redis
docker-compose restart redis
```

## 🔒 Sécurité

### Checklist de sécurité

- [ ] Changer toutes les clés secrètes par défaut
- [ ] Configurer HTTPS en production
- [ ] Restreindre l'accès réseau aux bases de données
- [ ] Activer les logs d'audit
- [ ] Configurer les backups automatiques
- [ ] Mettre à jour régulièrement les images Docker

### Variables sensibles

Ne jamais commiter :
- Clés secrètes
- Mots de passe base de données
- Certificats SSL
- Tokens d'API

Utiliser des secrets Docker ou un gestionnaire de secrets.

## 📈 Performance

### Optimisations incluses

- Multi-stage Docker build
- Uvicorn avec 4 workers
- Connection pooling PostgreSQL
- Cache Redis
- Compression Gzip
- Health checks

### Monitoring des performances

```bash
# Métriques de performance
curl http://localhost:8000/metrics

# Utilisation des ressources
docker stats
```

## 🆘 Support

En cas de problème :
1. Vérifier les logs détaillés
2. Consulter `PRODUCTION_READINESS.md`
3. Tester en environnement de développement
4. Ouvrir une issue avec les logs pertinents

---

*Dernière mise à jour : 20 décembre 2025*