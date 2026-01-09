"""
Système de cache Redis pour MedData Bridge.

Fournit un cache distribué pour améliorer les performances des données fréquemment
accessibles (vocabulaires, métadonnées, résultats de requêtes).
"""

import json
import logging
import os
from typing import Any, Optional, Union
from config.settings import settings

logger = logging.getLogger(__name__)

# Cache en mémoire comme fallback si Redis n'est pas disponible
_memory_cache = {}

try:
    import redis
    redis_url = getattr(settings, 'redis_url', None) or os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    redis_client = redis.Redis.from_url(
        redis_url,
        decode_responses=True,
        socket_timeout=5,
        socket_connect_timeout=5,
        retry_on_timeout=True,
        max_connections=20
    )

    # Test de connexion
    redis_client.ping()
    REDIS_AVAILABLE = True
    logger.info("Redis cache initialisé avec succès")

except (ImportError, redis.ConnectionError, redis.TimeoutError) as e:
    logger.warning(f"Redis non disponible, utilisation du cache mémoire: {e}")
    redis_client = None
    REDIS_AVAILABLE = False


class Cache:
    """Gestionnaire de cache unifié (Redis + fallback mémoire)."""

    @staticmethod
    def get(key: str) -> Optional[Any]:
        """Récupère une valeur du cache."""
        if REDIS_AVAILABLE and redis_client:
            try:
                value = redis_client.get(key)
                if value:
                    return json.loads(value)
            except Exception as e:
                logger.warning(f"Erreur Redis GET {key}: {e}")

        # Fallback mémoire
        return _memory_cache.get(key)

    @staticmethod
    def set(key: str, value: Any, ttl: int = None) -> bool:
        """Stocke une valeur dans le cache avec TTL."""
        if ttl is None:
            ttl = getattr(settings, 'cache_ttl', 3600)  # Default 1 hour
        try:
            serialized = json.dumps(value)
        except (TypeError, ValueError) as e:
            logger.warning(f"Impossible de sérialiser {key}: {e}")
            return False

        if REDIS_AVAILABLE and redis_client:
            try:
                return redis_client.setex(key, ttl, serialized)
            except Exception as e:
                logger.warning(f"Erreur Redis SET {key}: {e}")

        # Fallback mémoire (sans TTL réel)
        _memory_cache[key] = value
        return True

    @staticmethod
    def delete(key: str) -> bool:
        """Supprime une clé du cache."""
        if REDIS_AVAILABLE and redis_client:
            try:
                return redis_client.delete(key) > 0
            except Exception as e:
                logger.warning(f"Erreur Redis DELETE {key}: {e}")

        # Fallback mémoire
        return _memory_cache.pop(key, None) is not None

    @staticmethod
    def clear() -> bool:
        """Vide complètement le cache."""
        if REDIS_AVAILABLE and redis_client:
            try:
                return redis_client.flushdb()
            except Exception as e:
                logger.warning(f"Erreur Redis FLUSH: {e}")

        # Fallback mémoire
        _memory_cache.clear()
        return True

    @staticmethod
    def get_stats() -> dict:
        """Retourne les statistiques du cache."""
        stats = {
            "redis_available": REDIS_AVAILABLE,
            "memory_cache_size": len(_memory_cache)
        }

        if REDIS_AVAILABLE and redis_client:
            try:
                info = redis_client.info()
                stats.update({
                    "redis_connected_clients": info.get("connected_clients", 0),
                    "redis_used_memory": info.get("used_memory_human", "unknown"),
                    "redis_total_keys": redis_client.dbsize()
                })
            except Exception as e:
                stats["redis_error"] = str(e)

        return stats


# Instance globale du cache
cache = Cache()


def cached(ttl: int = None):
    """Décorateur pour mettre en cache le résultat d'une fonction."""
    if ttl is None:
        ttl = getattr(settings, 'cache_ttl', 3600)  # Default 1 hour
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Créer une clé de cache basée sur le nom de la fonction et ses arguments
            key = f"{func.__module__}.{func.__name__}:{hash(str(args) + str(kwargs))}"

            # Essayer de récupérer du cache
            result = cache.get(key)
            if result is not None:
                logger.debug(f"Cache hit pour {key}")
                return result

            # Calculer et mettre en cache
            result = func(*args, **kwargs)
            cache.set(key, result, ttl)
            logger.debug(f"Cache miss pour {key}, résultat mis en cache")

            return result
        return wrapper
    return decorator


# Fonctions utilitaires pour les cas d'usage courants
def get_vocabulary_cache_key(system: str, code: Optional[str] = None) -> str:
    """Génère une clé de cache pour les vocabulaires."""
    return f"vocab:{system}:{code or '*'}"

def get_patient_search_cache_key(query: str, limit: int = 50) -> str:
    """Génère une clé de cache pour les recherches de patients."""
    return f"patient_search:{query}:{limit}"

def get_endpoint_cache_key(endpoint_id: int) -> str:
    """Génère une clé de cache pour les endpoints."""
    return f"endpoint:{endpoint_id}"


# Décorateurs spécialisés pour les requêtes DB
def cached_db_query(ttl: int = None, key_prefix: str = "db"):
    """
    Décorateur pour mettre en cache les résultats de requêtes DB.

    Utilise le temps d'exécution de la requête pour les métriques.
    """
    if ttl is None:
        ttl = getattr(settings, 'cache_ttl', 3600)  # Default 1 hour
    def decorator(func):
        async def wrapper(*args, **kwargs):
            import time
            from app.metrics import record_db_metrics

            # Créer une clé de cache
            key = f"{key_prefix}:{func.__name__}:{hash(str(args) + str(kwargs))}"

            # Essayer le cache d'abord
            result = cache.get(key)
            if result is not None:
                logger.debug(f"DB cache hit pour {key}")
                return result

            # Exécuter la requête et mesurer le temps
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                duration = time.time() - start_time

                # Enregistrer les métriques
                record_db_metrics(duration)

                # Mettre en cache si la requête a réussi
                if result is not None:
                    cache.set(key, result, ttl)
                    logger.debug(f"DB cache miss pour {key}, résultat mis en cache (durée: {duration:.3f}s)")

                return result

            except Exception as e:
                duration = time.time() - start_time
                record_db_metrics(duration)
                logger.warning(f"Erreur DB pour {key}: {e} (durée: {duration:.3f}s)")
                raise

        # Pour les fonctions synchrones aussi
        def sync_wrapper(*args, **kwargs):
            import time
            from app.metrics import record_db_metrics

            key = f"{key_prefix}:{func.__name__}:{hash(str(args) + str(kwargs))}"

            result = cache.get(key)
            if result is not None:
                logger.debug(f"DB cache hit pour {key}")
                return result

            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                record_db_metrics(duration)

                if result is not None:
                    cache.set(key, result, ttl)
                    logger.debug(f"DB cache miss pour {key}, résultat mis en cache (durée: {duration:.3f}s)")

                return result

            except Exception as e:
                duration = time.time() - start_time
                record_db_metrics(duration)
                logger.warning(f"Erreur DB pour {key}: {e} (durée: {duration:.3f}s)")
                raise

        # Détecter si la fonction est async
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return wrapper
        else:
            return sync_wrapper

    return decorator


def invalidate_cache_pattern(pattern: str):
    """
    Invalide toutes les clés de cache correspondant à un pattern.

    Utile pour invalider le cache après des modifications DB.
    """
    if REDIS_AVAILABLE and redis_client:
        try:
            # Utiliser SCAN pour trouver les clés matching le pattern
            keys_to_delete = []
            cursor = 0
            while True:
                cursor, keys = redis_client.scan(cursor, match=pattern)
                keys_to_delete.extend(keys)
                if cursor == 0:
                    break

            if keys_to_delete:
                redis_client.delete(*keys_to_delete)
                logger.debug(f"Invalidé {len(keys_to_delete)} clés de cache pour pattern {pattern}")

        except Exception as e:
            logger.warning(f"Erreur lors de l'invalidation du cache pattern {pattern}: {e}")

    else:
        # Pour le cache mémoire, on ne peut pas faire de pattern matching facilement
        # On clear tout le cache mémoire
        _memory_cache.clear()
        logger.debug(f"Cache mémoire vidé pour pattern {pattern}")


# Fonctions utilitaires pour l'invalidation de cache par domaine
def invalidate_vocabulary_cache(system: str = "*"):
    """Invalide le cache des vocabulaires."""
    pattern = f"vocab:{system}:*"
    invalidate_cache_pattern(pattern)

def invalidate_patient_cache():
    """Invalide le cache des patients."""
    invalidate_cache_pattern("patient_search:*")

def invalidate_endpoint_cache(endpoint_id: int = None):
    """Invalide le cache des endpoints."""
    if endpoint_id:
        cache.delete(f"endpoint:{endpoint_id}")
    else:
        invalidate_cache_pattern("endpoint:*")

def invalidate_db_cache(table_name: str = None):
    """Invalide le cache DB pour une table spécifique ou tout le cache DB."""
    if table_name:
        invalidate_cache_pattern(f"db:*:{table_name}:*")
    else:
        invalidate_cache_pattern("db:*")


def get_redis_stats() -> dict:
    """
    Retourne les statistiques détaillées du cache Redis.
    
    Returns:
        dict: Dictionnaire contenant les métriques du cache:
            - connected: bool - État de la connexion Redis
            - hit_rate: float - Taux de cache hit (0.0 à 1.0)
            - total_keys: int - Nombre total de clés en cache
            - memory_used_human: str - Mémoire utilisée (format lisible)
            - uptime_seconds: int - Temps de fonctionnement Redis
    """
    if not REDIS_AVAILABLE or not redis_client:
        return {
            "connected": False,
            "hit_rate": 0.0,
            "total_keys": len(_memory_cache),
            "memory_used_human": "N/A",
            "uptime_seconds": 0
        }
    
    try:
        info = redis_client.info()
        stats = redis_client.info("stats")
        
        # Calculer le hit rate
        hits = stats.get("keyspace_hits", 0)
        misses = stats.get("keyspace_misses", 0)
        total = hits + misses
        hit_rate = hits / total if total > 0 else 0.0
        
        return {
            "connected": True,
            "hit_rate": hit_rate,
            "total_keys": redis_client.dbsize(),
            "memory_used_human": info.get("used_memory_human", "0B"),
            "uptime_seconds": info.get("uptime_in_seconds", 0)
        }
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des stats Redis: {e}")
        return {
            "connected": False,
            "hit_rate": 0.0,
            "total_keys": 0,
            "memory_used_human": "Error",
            "uptime_seconds": 0,
            "error": str(e)
        }
