# Configuration du Cache Redis

## Installation Redis

### Sur Linux (Ubuntu/Debian)

```bash

# Installer Redis

sudo apt-get update
sudo apt-get install redis-server

# Démarrer Redis

sudo systemctl start redis-server
sudo systemctl enable redis-server

# Vérifier le statut

sudo systemctl status redis-server

# Tester la connexion

redis-cli ping

# Devrait retourner: PONG

```

### Sur macOS

```bash

# Installer Redis via Homebrew

brew install redis

# Démarrer Redis

brew services start redis

# Tester la connexion

redis-cli ping
```

### Sur Windows

```powershell

# Installer via Chocolatey

choco install redis-64

# Ou télécharger depuis: https://github.com/microsoftarchive/redis/releases

# Démarrer Redis

redis-server
```

### Avec Docker

```bash

# Lancer Redis en conteneur

docker run -d -p 6379:6379 --name redis redis:7-alpine

# Vérifier

docker ps | grep redis
```

## Configuration de l'Application

### Variables d'Environnement

Créer un fichier `.env` à la racine du projet :

```bash

# Redis Configuration

REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=  # Optionnel
CACHE_TTL=3600    # TTL par défaut en secondes (1h)
```

### Configuration par Type d'Export

Les TTL sont configurés automatiquement selon le type de données :

- **Structure** : 3600s (1 heure) - change rarement

- **Patients** : 600s (10 minutes) - change occasionnellement  

- **Venues** : 300s (5 minutes) - change fréquemment (mouvements en temps réel)

## Utilisation

### Désactivation du Cache

Si Redis n'est pas disponible, l'application fonctionne normalement avec un fallback automatique (mode dégradé sans cache).

Pour désactiver explicitement le cache même si Redis est disponible :

```python

# Dans le code

export_service = FHIRExportService(session, base_url, enable_cache=False)
```

### API de Gestion du Cache

#### Statistiques du Cache

```bash
curl http://localhost:8000/api/cache/stats
```

Retourne :
```json
{
  "enabled": true,
  "used_memory": "1.23M",
  "total_connections": 42,
  "total_commands": 1337,
  "keyspace_hits": 850,
  "keyspace_misses": 150,
  "hit_rate": 85.0
}
```

#### Invalider le Cache

```bash

# Invalider tous les exports FHIR

curl -X POST "http://localhost:8000/api/cache/invalidate?pattern=fhir:export:*"

# Invalider uniquement les venues

curl -X POST "http://localhost:8000/api/cache/invalidate?pattern=fhir:export:venues:*"

# Invalider pour un établissement spécifique

curl -X POST "http://localhost:8000/api/cache/invalidate?pattern=fhir:export:*:ej:1"
```

#### Vider Complètement le Cache (⚠️)

```bash
curl -X POST http://localhost:8000/api/cache/flush
```

#### Vérifier la Santé

```bash
curl http://localhost:8000/api/cache/health
```

## Monitoring

### Métriques Disponibles

Le service de cache expose des métriques Prometheus :

- `fhir.export.duration` : Durée d'export (avec label `cache: hit/miss`)

- `cache.hit_rate` : Taux de succès du cache (%)

- `cache.operations` : Nombre d'opérations (get/set/delete)

### Logs

Les logs du cache incluent :

- ✅ Connexion Redis réussie

- ⚠️  Avertissement si Redis indisponible (fallback automatique)

- 🗑️ Invalidations de cache

- 🔍 Opérations de cache (niveau DEBUG)

Activer les logs DEBUG :
```bash
export LOG_LEVEL=DEBUG
```

## Clés de Cache

### Format des Clés

```
fhir:export:{type}:ej:{ej_id}
```

Exemples :

- `fhir:export:structure:ej:1` - Structure de l'EJ 1

- `fhir:export:patients:ej:1` - Patients de l'EJ 1

- `fhir:export:venues:ej:1` - Venues de l'EJ 1

### Invalidation Automatique

Le cache est automatiquement invalidé lors de :

- Création/modification/suppression de mouvements → invalide `venues:*`

- Modification de structure → invalide `structure:ej:{id}`

- Import FHIR → invalide tous les caches concernés

## Performance

### Gains de Performance Attendus

Sans cache (mesures typiques) :

- Export structure : ~500ms

- Export patients : ~300ms

- Export venues : ~800ms (avec mouvements)

Avec cache (hit) :

- Export structure : ~20ms (96% plus rapide)

- Export patients : ~15ms (95% plus rapide)

- Export venues : ~25ms (97% plus rapide)

### Mémoire Redis

Estimation de mémoire pour 1000 patients :

- Structure : ~50KB par EJ

- Patients : ~100KB par EJ (1000 patients)

- Venues : ~200KB par EJ (1000 venues avec mouvements)

Total : ~350KB par établissement

Pour 10 établissements : ~3.5MB (négligeable)

## Dépannage

### Redis refuse la connexion

```bash

# Vérifier que Redis tourne

redis-cli ping

# Si erreur "Connection refused"

sudo systemctl start redis-server

# Vérifier les logs Redis

sudo journalctl -u redis-server -f
```

### Cache non invalidé après modification

```bash

# Invalider manuellement

curl -X POST "http://localhost:8000/api/cache/invalidate?pattern=fhir:*"

# Vérifier les logs de l'app

tail -f logs/app.log | grep cache
```

### Performance dégradée

```bash

# Vérifier les stats Redis

redis-cli info stats

# Si trop de clés, vider le cache

redis-cli flushdb
```

### Erreur "Redis timeout"

```bash

# Augmenter les timeouts dans cache_service.py

socket_connect_timeout=5  # au lieu de 2
socket_timeout=5          # au lieu de 2
```

## Tests

```bash

# Tester le service de cache

pytest tests/test_cache_service.py -v

# Tester avec Redis

# (nécessite Redis en cours d'exécution)

pytest tests/test_cache_service.py -v -k "not disabled"

# Tester le fallback sans Redis

pytest tests/test_cache_service.py::test_cache_disabled_fallback -v
```
