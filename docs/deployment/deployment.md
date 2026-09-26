# Déploiement Compose — guide courant

Dernière vérification : 25 septembre 2026.

Ce guide décrit le déploiement maintenu depuis la racine du checkout courant.
Il remplace les procédures qui mentionnent la branche
`production-deployment`, `docker-compose` v1 ou
`scripts/deployment/deploy.sh`.

## Prérequis

- Docker Engine et le plugin `docker compose` v2 ;
- un port local disponible pour l'application (8000 par défaut) ;
- un fichier `.env` contenant les clés de runtime.

Python n'est pas nécessaire pour utiliser Compose : l'image installe les
dépendances runtime verrouillées par `requirements-runtime.lock`.

## Première installation

```bash
git clone <url-du-dépôt>
cd MedData_Bridge
cp .env.example .env
```

Éditer ensuite `.env`. Pour le profil LAN, renseigner au minimum
`POSTGRES_PASSWORD` avec une valeur propre à l'environnement. Les clés JWT ne
sont pas requises tant que la sécurité reste désactivée. PostgreSQL et Redis
utilisent le réseau interne Docker ; Redis n'est volontairement pas publié sur
le poste hôte.

Par défaut, `SECURITY_ENABLED=false` est adapté à une utilisation strictement
LAN : aucun login ni route d'administration JWT ne sont exposés. Avant toute
exposition hors LAN, utiliser obligatoirement le profil `exposed` : il impose
les secrets, un compte administrateur local et l'authentification globale.

Valider la configuration avant de créer des ressources :

```bash
docker compose -f docker/docker-compose.yml config --quiet
```

Cette commande fonctionne également sans `.env` dans un checkout propre ; le
conteneur applicatif, lui, nécessite les secrets du profil `exposed` pour
démarrer hors LAN.

### Profil exposé (hors LAN)

Le proxy TLS et les certificats restent à configurer par l'opérateur. Les
variables suivantes doivent être longues, aléatoires et distinctes :

```bash
export SECRET_KEY="..."
export JWT_SECRET_KEY="..."
export BOOTSTRAP_ADMIN_USERNAME="admin"
export BOOTSTRAP_ADMIN_PASSWORD="..."
export POSTGRES_PASSWORD="..."
docker compose -f docker/docker-compose.yml -f docker/docker-compose.exposed.yml --profile nginx up -d --build --wait
```

Le second fichier Compose échoue volontairement si une variable obligatoire
manque. Ne pas utiliser le profil LAN pour une interface exposée.

## Démarrer et vérifier

```bash
docker compose -f docker/docker-compose.yml up -d --build --wait --wait-timeout 180
curl --fail http://127.0.0.1:8000/health
docker compose -f docker/docker-compose.yml ps
```

Le conteneur applique `alembic upgrade head` avant Uvicorn. Une base PostgreSQL
vide est donc initialisée puis marquée à la révision Alembic courante ; une base
existante reçoit seulement les migrations manquantes.

Pour choisir un autre port hôte :

```bash
MEDBRIDGE_PORT=8002 docker compose -f docker/docker-compose.yml up -d --build --wait
curl --fail http://127.0.0.1:8002/health
```

## Exploitation courante

```bash
# Logs et état
docker compose -f docker/docker-compose.yml logs --follow medbridge
docker compose -f docker/docker-compose.yml ps

# Vérifier la révision du schéma
docker compose -f docker/docker-compose.yml exec medbridge python -m alembic current

# Arrêt sans supprimer les données
docker compose -f docker/docker-compose.yml down

# Arrêt et suppression irréversible des données de la pile
docker compose -f docker/docker-compose.yml down --volumes --remove-orphans
```

Les données applicatives, PostgreSQL, Redis et les fichiers de log sont portés
par des volumes Docker nommés. La dernière commande les supprime : ne l'utiliser
que pour une installation de démonstration ou après une sauvegarde validée.

## Profils optionnels

Nginx et Prometheus ne sont pas démarrés par défaut :

```bash
docker compose -f docker/docker-compose.yml --profile nginx up -d
docker compose -f docker/docker-compose.yml --profile monitoring up -d
```

Le profil Nginx monte `docker/nginx.conf`. Les certificats éventuels doivent
être placés dans `docker/ssl/`, puis la configuration HTTPS doit être activée
dans ce fichier.

## Mettre à niveau

```bash
git pull
docker compose -f docker/docker-compose.yml up -d --build --wait --wait-timeout 180
curl --fail http://127.0.0.1:8000/health
```

Consulter les logs si le healthcheck échoue. Ne pas lancer une migration
manuelle en parallèle du démarrage : l'entrypoint Compose l'exécute déjà.

## Livraison hors ligne

Le bundle est toujours construit depuis les sources canoniques du checkout :

```bash
python3 scripts/build_deployment_bundle.py --output dist/meddata-bridge.zip
python3 scripts/build_deployment_bundle.py --output dist/meddata-bridge-offline.zip --with-wheels
```

Le bundle ne contient pas une seconde copie versionnée de `app/`. Les anciens
guides RHEL et les scripts de déploiement sont conservés pour la traçabilité,
mais ne constituent pas la procédure Compose maintenue.
